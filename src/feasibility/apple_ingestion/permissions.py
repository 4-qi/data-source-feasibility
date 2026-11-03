"""Explicit, deployment-specific grants; importing this module changes nothing.

Use a migration/maintenance connection in a disposable database first. This
module never creates roles or transfers object ownership. apply_permissions
checks existing role attributes, memberships and ownership before executing its
plan in the caller's transaction. The caller commits or rolls back. Do not use
on a shared/production database without separate operational authorization.
"""
from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.engine import Connection

from .models import Base

RUNTIME_UPDATE_COLUMNS = {
    "collection_run": ("finished_at", "execution_status", "coverage_status", "stop_reason", "anomalies"),
    "fetch_attempt": ("finished_at", "http_status", "parsing_status", "persistence_status", "entry_count", "response_bytes", "error_codes", "anomalies"),
    "review": ("current_version_id", "last_observed_at"),
    "review_observation": ("occurrence_count", "conflict_count"),
}
IDENTITY_TABLES = ("application", "collection_target", "fetch_attempt", "review", "review_version")
TABLES = tuple(Base.metadata.tables)


def _identifier(value: str) -> str:
    if not isinstance(value, str) or not value or "\x00" in value or len(value.encode("utf-8")) > 63:
        raise ValueError("Expected a nonempty PostgreSQL identifier of at most 63 UTF-8 bytes")
    return '"' + value.replace('"', '""') + '"'


@dataclass(frozen=True)
class RoleConfig:
    runtime_role: str
    maintenance_role: str
    report_role: str
    schema: str = "public"

    def __post_init__(self):
        for value in (self.runtime_role, self.maintenance_role, self.report_role, self.schema):
            _identifier(value)
        roles = (self.runtime_role, self.maintenance_role, self.report_role)
        if len(set(roles)) != 3 or any(role.lower() == "public" for role in roles):
            raise ValueError("Use three distinct actual roles; PUBLIC is not an actual role")


def permission_sql(config: RoleConfig) -> tuple[str, ...]:
    """Return reviewable SQL without connecting or creating/changing roles.

    Revokes are scoped to this schema's seven ingestion tables, their identity
    sequences, the guard function, and schema CREATE. Existing PUBLIC access to
    these objects is removed. Existing column grants are cleared as well as
    table grants. Runtime version rows consequently remain append-only.
    """
    schema = _identifier(config.schema)
    runtime = _identifier(config.runtime_role)
    report = _identifier(config.report_role)
    maintenance = _identifier(config.maintenance_role)
    consumers = f"PUBLIC, {runtime}, {report}"
    statements = [
        f"REVOKE CREATE ON SCHEMA {schema} FROM {consumers}",
        f"GRANT USAGE ON SCHEMA {schema} TO {runtime}, {report}",
        f"GRANT USAGE, CREATE ON SCHEMA {schema} TO {maintenance}",
    ]
    for name in TABLES:
        table = f"{schema}.{_identifier(name)}"
        columns = ", ".join(_identifier(column.name) for column in Base.metadata.tables[name].columns)
        statements.extend((
            f"REVOKE ALL PRIVILEGES ON TABLE {table} FROM {consumers}",
            f"REVOKE ALL PRIVILEGES ({columns}) ON TABLE {table} FROM {consumers}",
            f"GRANT SELECT, INSERT ON TABLE {table} TO {runtime}",
            f"GRANT SELECT ON TABLE {table} TO {report}",
        ))
        if name in RUNTIME_UPDATE_COLUMNS:
            updates = ", ".join(_identifier(column) for column in RUNTIME_UPDATE_COLUMNS[name])
            statements.append(f"GRANT UPDATE ({updates}) ON TABLE {table} TO {runtime}")
    for name in IDENTITY_TABLES:
        sequence = f"{schema}.{_identifier(name + '_id_seq')}"
        statements.extend((
            f"REVOKE ALL PRIVILEGES ON SEQUENCE {sequence} FROM {consumers}",
            f"GRANT USAGE ON SEQUENCE {sequence} TO {runtime}",
        ))
    statements.append(f"REVOKE ALL PRIVILEGES ON FUNCTION {schema}.guard_collection_run_identity() FROM {consumers}")
    return tuple(statements)


def _validate_roles(connection: Connection, config: RoleConfig) -> None:
    if connection.dialect.name != "postgresql":
        raise ValueError("Permissions require PostgreSQL")
    # Reject memberships rather than assuming an inherited or SET ROLE route is
    # harmless. Direct object revokes cannot neutralize those routes.
    for role in (config.runtime_role, config.report_role):
        row = connection.execute(text("""
            SELECT oid, rolsuper, rolcreaterole, rolcreatedb, rolreplication, rolbypassrls
            FROM pg_roles WHERE rolname = :role
        """), {"role": role}).mappings().one_or_none()
        if row is None or any(row[key] for key in ("rolsuper", "rolcreaterole", "rolcreatedb", "rolreplication", "rolbypassrls")):
            raise ValueError("Runtime/report roles must exist and have no administrative attributes")
        if connection.scalar(text("SELECT datdba = :oid FROM pg_database WHERE datname = current_database()"), {"oid": row["oid"]}):
            raise ValueError("Runtime/report roles must not own the database")
        memberships = connection.scalar(text("SELECT count(*) FROM pg_auth_members WHERE member = :oid"), {"oid": row["oid"]})
        if memberships:
            raise ValueError("Runtime/report roles must have no role memberships")
    owner = connection.scalar(text("SELECT oid FROM pg_roles WHERE rolname = :role"), {"role": config.maintenance_role})
    if owner is None:
        raise ValueError("Maintenance role must already exist")
    for name in (*TABLES, *(table + "_id_seq" for table in IDENTITY_TABLES)):
        object_owner = connection.scalar(text("""
            SELECT c.relowner FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE n.nspname = :schema AND c.relname = :name
        """), {"schema": config.schema, "name": name})
        if object_owner != owner:
            raise ValueError("All ingestion tables and sequences must be owned by the maintenance role")
    function_owner = connection.scalar(text("""
        SELECT p.proowner FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace
        WHERE n.nspname = :schema AND p.proname = 'guard_collection_run_identity'
          AND p.pronargs = 0
    """), {"schema": config.schema})
    if function_owner != owner:
        raise ValueError("Guard function must be owned by the maintenance role")
    schema_owner = connection.scalar(text("SELECT nspowner FROM pg_namespace WHERE nspname = :schema"), {"schema": config.schema})
    # PostgreSQL 15+ commonly owns public through pg_database_owner; membership
    # is valid for maintenance, never for either consumer role.
    if not connection.scalar(text("SELECT pg_has_role(:owner, :schema_owner, 'USAGE')"), {"owner": owner, "schema_owner": schema_owner}):
        raise ValueError("Maintenance role must own or control the schema owner role")


def apply_permissions(connection: Connection, config: RoleConfig) -> None:
    """Apply only after explicit operator invocation, within their transaction.

    No commit is issued. The caller must use a transaction (e.g. engine.begin),
    preventing a partially applied plan from being persisted after failure.
    """
    if not connection.in_transaction():
        raise ValueError("Apply permissions inside an explicit transaction")
    if (connection.get_execution_options().get("isolation_level") == "AUTOCOMMIT"
            or getattr(connection.connection.driver_connection, "autocommit", False)):
        raise ValueError("Permission changes require transactional execution")
    _validate_roles(connection, config)
    for statement in permission_sql(config):
        connection.exec_driver_sql(statement)


__all__ = ["RoleConfig", "RUNTIME_UPDATE_COLUMNS", "permission_sql", "apply_permissions"]

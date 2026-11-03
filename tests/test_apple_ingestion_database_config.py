"""Pure connection/configuration checks: no database or Apple traffic."""
import importlib
from types import SimpleNamespace

import pytest

pytest.importorskip("sqlalchemy")
from sqlalchemy.engine import URL

from feasibility.apple_ingestion import db, permissions


def forbidden_io(*args, **kwargs):
    pytest.fail("Pure configuration must not open a database connection")


def test_missing_ingestion_url_has_no_ambient_database_or_credential_default(monkeypatch):
    monkeypatch.delenv(db.DATABASE_URL_ENV, raising=False)
    monkeypatch.setenv("DATABASE_URL", "postgresql://ambient:ambient-secret@invalid/ambient")
    monkeypatch.setenv("PGHOST", "ambient.invalid")
    monkeypatch.setenv("PGUSER", "ambient-user")
    monkeypatch.setenv("PGPASSWORD", "ambient-secret")
    monkeypatch.setattr(db, "create_engine", forbidden_io)
    with pytest.raises(ValueError, match=db.DATABASE_URL_ENV) as caught:
        db.create_db_engine()
    assert "ambient-secret" not in str(caught.value)
    assert "ambient.invalid" not in str(caught.value)


def test_explicit_url_overrides_environment_and_does_not_add_credentials(monkeypatch):
    monkeypatch.setenv(db.DATABASE_URL_ENV, "postgresql://ambient:secret@invalid/ambient")
    resolved = db.database_url("postgresql://localhost/synthetic")
    assert resolved.drivername == "postgresql+psycopg"
    assert resolved.database == "synthetic"
    assert resolved.username is None and resolved.password is None
    assert resolved.query == {}


def test_only_ingestion_environment_is_used_when_no_url_is_supplied(monkeypatch):
    monkeypatch.setenv(db.DATABASE_URL_ENV, "postgresql+psycopg://fixture@localhost/synthetic")
    resolved = db.database_url()
    assert resolved.username == "fixture"
    assert resolved.database == "synthetic"
    assert resolved.password is None


@pytest.mark.parametrize("supplied", [
    "sqlite:///:memory:",
    "postgresql+psycopg2://fixture:sentinel-secret@invalid/synthetic",
    "postgresql+asyncpg://fixture:sentinel-secret@invalid/synthetic",
    "postgresql+psycopg://fixture:sentinel-secret@invalid/synthetic?options=-c%20timezone=EST",
    "postgresql+psycopg://fixture:sentinel-secret@invalid/synthetic?service=ambient",
    "postgresql+psycopg://fixture:sentinel-secret@invalid/synthetic?servicefile=/private/file",
    "not-a-url-sentinel-secret",
])
def test_rejected_url_errors_do_not_echo_credentials_or_chained_parser_error(supplied):
    with pytest.raises(ValueError) as caught:
        db.database_url(supplied)
    assert "sentinel-secret" not in str(caught.value)
    assert caught.value.__suppress_context__


def test_empty_explicit_url_does_not_fall_back_to_environment(monkeypatch):
    monkeypatch.setenv(db.DATABASE_URL_ENV, "postgresql://localhost/environment")
    with pytest.raises(ValueError):
        db.database_url("")


def test_url_object_preserves_percent_and_unicode_password_without_interpolation():
    original = URL.create("postgresql+psycopg", username="fixture", password="synthetic%密@:/",
                          host="localhost", database="synthetic")
    assert db.database_url(original) == original


def test_engine_creation_is_lazy_and_disables_parameter_logging(monkeypatch):
    psycopg = pytest.importorskip("psycopg")
    monkeypatch.setattr(psycopg, "connect", forbidden_io)
    engine = db.create_db_engine("postgresql+psycopg://localhost/synthetic")
    try:
        assert engine.dialect.driver == "psycopg"
        assert engine.echo is False
        assert engine.hide_parameters is True
        assert engine.pool.checkedout() == 0
    finally:
        engine.dispose()


def test_module_imports_do_not_create_engines_or_provision_permissions(monkeypatch):
    import sqlalchemy
    with monkeypatch.context() as scoped:
        scoped.setattr(sqlalchemy, "create_engine", forbidden_io)
        importlib.reload(db)
        importlib.reload(permissions)
    # Restore the imported factory reference after the patched import.
    importlib.reload(db)


@pytest.mark.parametrize("runtime,maintenance,report", [
    ("same", "same", "reader"),
    ("writer", "same", "same"),
    ("same", "owner", "same"),
    ("PUBLIC", "owner", "reader"),
    ("writer", "Public", "reader"),
    ("writer", "owner", "public"),
])
def test_roles_must_be_distinct_actual_roles(runtime, maintenance, report):
    with pytest.raises(ValueError):
        permissions.RoleConfig(runtime, maintenance, report)


@pytest.mark.parametrize("field,invalid", [
    ("runtime_role", ""),
    ("maintenance_role", "nul\x00suffix"),
    ("report_role", "x" * 64),
    ("schema", "界" * 22),
])
def test_invalid_identifiers_are_rejected_before_planning(field, invalid):
    values = dict(runtime_role="writer", maintenance_role="owner", report_role="reader", schema="pilot")
    values[field] = invalid
    with pytest.raises(ValueError):
        permissions.RoleConfig(**values)


def test_permission_plan_quotes_identifiers_and_does_not_execute(monkeypatch):
    monkeypatch.setattr(db, "create_db_engine", forbidden_io)
    config = permissions.RoleConfig('writer"; DROP ROLE owner; --', "owner", "reader", schema='pilot"schema')
    first = permissions.permission_sql(config)
    assert first == permissions.permission_sql(config)
    assert isinstance(first, tuple)
    assert 'REVOKE CREATE ON SCHEMA "pilot""schema" FROM PUBLIC, "writer""; DROP ROLE owner; --", "reader"' in first
    assert not any(statement.startswith(("CREATE ROLE", "ALTER ROLE", "DROP ROLE")) for statement in first)


def test_runtime_and_report_plan_preserves_append_only_and_immutable_fields():
    plan = permissions.permission_sql(permissions.RoleConfig("writer", "owner", "reader", "pilot"))
    table_grants = [statement for statement in plan if statement.startswith("GRANT") and " ON TABLE " in statement]
    assert len([statement for statement in table_grants if statement.startswith("GRANT SELECT, INSERT")]) == 7
    assert len([statement for statement in table_grants if statement.endswith('TO "reader"')]) == 7
    assert all(statement.startswith("GRANT SELECT ON TABLE") for statement in table_grants if statement.endswith('TO "reader"'))
    assert not any("DELETE" in statement or "TRUNCATE" in statement or "ALL PRIVILEGES" in statement for statement in table_grants)
    updates = [statement for statement in table_grants if statement.startswith("GRANT UPDATE")]
    assert len(updates) == 4
    assert all('"review_version"' not in statement for statement in updates)
    assert all('"config_snapshot"' not in statement and '"reference_run_id"' not in statement for statement in updates)
    # Clearing old column-level grants matters: table REVOKE alone leaves them.
    assert any(statement.startswith("REVOKE ALL PRIVILEGES (") and '"review_version"' in statement for statement in plan)


def test_permissions_refuse_missing_transaction_before_any_query():
    connection = SimpleNamespace(in_transaction=lambda: False, execute=forbidden_io, exec_driver_sql=forbidden_io)
    with pytest.raises(ValueError, match="explicit transaction"):
        permissions.apply_permissions(connection, permissions.RoleConfig("writer", "owner", "reader"))


@pytest.mark.parametrize("execution_options,driver_autocommit", [({"isolation_level": "AUTOCOMMIT"}, False), ({}, True)])
def test_permissions_refuse_autocommit_before_any_query(execution_options, driver_autocommit):
    connection = SimpleNamespace(
        in_transaction=lambda: True,
        get_execution_options=lambda: execution_options,
        connection=SimpleNamespace(driver_connection=SimpleNamespace(autocommit=driver_autocommit)),
        execute=forbidden_io,
        exec_driver_sql=forbidden_io,
    )
    with pytest.raises(ValueError, match="transactional execution"):
        permissions.apply_permissions(connection, permissions.RoleConfig("writer", "owner", "reader"))

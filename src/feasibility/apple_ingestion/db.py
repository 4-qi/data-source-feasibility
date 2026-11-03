"""Explicit PostgreSQL connection factory; no database is contacted at import."""
import os

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine, URL, make_url

DATABASE_URL_ENV = "APPLE_INGESTION_DATABASE_URL"


def database_url(value: str | URL | None = None) -> URL:
    """Resolve only an explicit URL or the ingestion-specific environment value.

    Errors intentionally omit the supplied URL. Do not log URL objects or driver
    exceptions in routine diagnostics; even a redacted URL contains deployment
    identity. PostgreSQL's psycopg3 driver is mandatory for this package.
    """
    supplied = value if value is not None else os.environ.get(DATABASE_URL_ENV)
    if not supplied:
        raise ValueError(f"Set {DATABASE_URL_ENV} or supply a PostgreSQL URL")
    try:
        url = make_url(supplied)
        if url.drivername in {"postgresql", "postgres"}:
            url = url.set(drivername="postgresql+psycopg")
        if url.drivername != "postgresql+psycopg":
            raise ValueError
        if "options" in url.query or "service" in url.query or "servicefile" in url.query:
            raise ValueError
    except Exception:
        raise ValueError("Expected a PostgreSQL psycopg3 URL without session options or service indirection") from None
    return url


def create_db_engine(url: str | URL | None = None) -> Engine:
    """Create an engine without connecting, with UTC sessions and hidden values.

    Explicit caller-provided connections used by Alembic remain caller-owned.
    The engine does not create roles, schemas, tables, or run migrations.
    """
    engine = create_engine(
        database_url(url), echo=False, hide_parameters=True,
        connect_args={"options": "-c timezone=UTC"},
    )

    @event.listens_for(engine, "connect")
    def _utc_connection(dbapi_connection, _connection_record):
        # autocommit avoids leaving a driver transaction open before Alembic
        # begins its explicit transactional DDL scope.
        previous = dbapi_connection.autocommit
        dbapi_connection.autocommit = True
        try:
            with dbapi_connection.cursor() as cursor:
                cursor.execute("SET TIME ZONE 'UTC'")
        finally:
            dbapi_connection.autocommit = previous

    return engine


__all__ = ["DATABASE_URL_ENV", "database_url", "create_db_engine"]

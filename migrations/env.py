"""Alembic environment: PostgreSQL only, no URL/config logging."""
from alembic import context
from sqlalchemy.engine import Connection

from feasibility.apple_ingestion.db import create_db_engine
from feasibility.apple_ingestion.models import Base

config = context.config
target_metadata = Base.metadata


def configure(connection=None):
    options = dict(
        target_metadata=target_metadata,
        compare_type=True,
        transactional_ddl=True,
    )
    if connection is None:
        context.configure(dialect_name="postgresql", literal_binds=True,
                          dialect_opts={"paramstyle": "named"}, **options)
    else:
        if not isinstance(connection, Connection) or connection.dialect.name != "postgresql":
            raise ValueError("Alembic requires a PostgreSQL SQLAlchemy Connection")
        context.configure(connection=connection, **options)
    with context.begin_transaction():
        context.run_migrations()


if context.is_offline_mode():
    configure()
else:
    supplied = config.attributes.get("connection")
    if supplied is not None:
        configure(supplied)
    else:
        engine = create_db_engine()
        try:
            with engine.connect() as connection:
                configure(connection)
        finally:
            engine.dispose()

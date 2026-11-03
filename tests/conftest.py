"""Shared synthetic Apple tests; never select an ambient or shared database."""
import os
from pathlib import Path
import socket
from uuid import uuid4

import pytest


@pytest.fixture(autouse=True)
def _deny_internet_sockets(monkeypatch):
    """Fail accidental Python TCP connects; retain local PostgreSQL sockets."""
    original_connect=socket.socket.connect
    original_connect_ex=socket.socket.connect_ex

    def blocked_connect(sock,address):
        if sock.family in (socket.AF_INET,socket.AF_INET6):
            raise AssertionError('Tests must use synthetic transport; Internet socket connections are disabled')
        return original_connect(sock,address)

    def blocked_connect_ex(sock,address):
        if sock.family in (socket.AF_INET,socket.AF_INET6):
            raise AssertionError('Tests must use synthetic transport; Internet socket connections are disabled')
        return original_connect_ex(sock,address)

    monkeypatch.setattr(socket.socket,'connect',blocked_connect)
    monkeypatch.setattr(socket.socket,'connect_ex',blocked_connect_ex)


@pytest.fixture
def apple_database():
    """Yield a migrated SQLAlchemy Engine for one test's private database.

    The runner supplies an explicitly disposable bootstrap DSN. Each invocation
    creates its own database on that cluster so committed test writes and Phase
    A's migration rollback cannot interfere. Callers may commit transactions;
    teardown disposes the engine and drops only this fixture-created database.
    No long-lived transaction wraps the test: page-level commits stay real.
    """
    dsn=os.environ.get('APPLE_INGESTION_TEST_DSN')
    if not dsn or os.environ.get('APPLE_INGESTION_DISPOSABLE') != '1':
        pytest.skip('requires explicit disposable PostgreSQL; use scripts/test_apple_ingestion_postgres.sh --full-suite')
    psycopg=pytest.importorskip('psycopg',reason='PostgreSQL tests require psycopg3')
    pytest.importorskip('sqlalchemy')
    pytest.importorskip('alembic')
    from psycopg import sql
    from sqlalchemy import URL
    from alembic import command
    from alembic.config import Config
    from feasibility.apple_ingestion.db import create_db_engine

    database_name='apple_phase_a_fixture_'+uuid4().hex
    engine=None
    created=False
    with psycopg.connect(dsn,autocommit=True) as admin:
        bootstrap=admin.execute('SELECT current_database()').fetchone()[0]
        if not bootstrap.startswith('apple_phase_a_'):
            pytest.fail('refusing database creation outside an apple_phase_a_ disposable bootstrap')
        try:
            admin.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(database_name)))
            created=True
            params=psycopg.conninfo.conninfo_to_dict(dsn)
            url=URL.create('postgresql+psycopg',username=params.get('user'),
                password=params.get('password'),database=database_name,
                query={k:v for k,v in params.items() if k not in {'user','password','dbname'}})
            engine=create_db_engine(url)
            root=Path(__file__).resolve().parents[1]
            cfg=Config(str(root/'alembic.ini'))
            cfg.set_main_option('script_location',str(root/'migrations'))
            with engine.connect() as connection:
                cfg.attributes['connection']=connection
                command.upgrade(cfg,'head')
            yield engine
        finally:
            if engine is not None:
                engine.dispose()
            if created:
                # Only the unique database created above can be dropped here.
                admin.execute(sql.SQL('DROP DATABASE {} WITH (FORCE)').format(sql.Identifier(database_name)))

"""Real PostgreSQL acceptance tests; run scripts/test_apple_ingestion_postgres.sh.

No ambient DATABASE_URL is consumed. Missing opt-in environment is a skip, never
evidence of database acceptance. All content below is synthetic.
"""
import os
from pathlib import Path
from uuid import uuid4

import pytest

from apple_ingestion_db_helpers import (
    NOW, TABLES, application, attempt, observation, review, run, target, version,
)

psycopg = pytest.importorskip('psycopg', reason='PostgreSQL tests require psycopg3')
alembic_command = pytest.importorskip('alembic.command')
from alembic.config import Config

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope='module')
def database():
    dsn = os.environ.get('APPLE_INGESTION_TEST_DSN')
    if not dsn or os.environ.get('APPLE_INGESTION_DISPOSABLE') != '1':
        pytest.skip('requires explicit disposable PostgreSQL; use scripts/test_apple_ingestion_postgres.sh')
    with psycopg.connect(dsn, autocommit=True) as conn:
        name = conn.execute('SELECT current_database()').fetchone()[0]
        if not name.startswith('apple_phase_a_'):
            pytest.fail('refusing migration outside an apple_phase_a_ disposable database')
    from sqlalchemy import URL, create_engine
    params = psycopg.conninfo.conninfo_to_dict(dsn)
    url = URL.create('postgresql+psycopg', username=params.get('user'),
                     password=params.get('password'), database=params['dbname'],
                     query={k:v for k,v in params.items() if k not in {'user','password','dbname'}})
    engine = create_engine(url)
    cfg = Config(str(ROOT / 'alembic.ini'))
    cfg.set_main_option('script_location', str(ROOT / 'migrations'))
    cfg.set_main_option('sqlalchemy.url', url.render_as_string(hide_password=False).replace('%','%%'))
    with engine.connect() as connection:
        cfg.attributes['connection'] = connection
        alembic_command.upgrade(cfg, 'head')
    yield dsn, cfg, engine
    engine.dispose()


@pytest.fixture
def conn(database):
    with psycopg.connect(database[0]) as connection:
        connection.execute("SET TIME ZONE 'UTC'")
        yield connection
        connection.rollback()


@pytest.fixture
def seed(conn):
    app = application(conn)
    target_id = target(conn, app)
    run_id = run(conn, app, target_id)
    return app, target_id, run_id


def reject(conn, statement, params=(), state='23514'):
    with pytest.raises(psycopg.Error) as caught:
        with conn.transaction():
            conn.execute(statement, params)
    assert caught.value.sqlstate == state


def test_00_upgrade_downgrade_reupgrade(database):
    dsn,cfg,engine = database
    with engine.connect() as connection:
        cfg.attributes['connection'] = connection
        alembic_command.downgrade(cfg, 'base')
    with psycopg.connect(dsn) as c:
        assert set(r[0] for r in c.execute("SELECT tablename FROM pg_tables WHERE schemaname='public'")) <= {'alembic_version'}
        assert c.execute("SELECT count(*) FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace WHERE n.nspname='public' AND p.proname='guard_collection_run_identity'").fetchone()[0] == 0
    with engine.connect() as connection:
        cfg.attributes['connection'] = connection
        alembic_command.upgrade(cfg, 'head')


def test_exact_seven_tables_metadata_and_deferred_fk(conn):
    from feasibility.apple_ingestion.models import Base
    assert set(Base.metadata.tables) == TABLES
    assert set(r[0] for r in conn.execute("SELECT tablename FROM pg_tables WHERE schemaname='public'")) == TABLES | {'alembic_version'}
    assert conn.execute("SELECT condeferrable,condeferred FROM pg_constraint WHERE conname='current_version_belongs_to_review'").fetchone() == (True, True)


def test_migration_matches_metadata_and_engine_sets_utc(database):
    from alembic.autogenerate import compare_metadata
    from alembic.migration import MigrationContext
    from feasibility.apple_ingestion.db import create_db_engine
    from feasibility.apple_ingestion.models import Base
    engine=create_db_engine(database[2].url)
    try:
        with engine.connect() as c:
            assert c.exec_driver_sql("SELECT current_setting('TimeZone')").scalar_one()=='UTC'
            assert compare_metadata(MigrationContext.configure(c),Base.metadata)==[]
    finally:
        engine.dispose()


def test_unicode_fulltext_circular_commit_and_utc(database):
    body = ('汉字🙂 e\u0301\r\nline &amp;\n' * 20000) + 'END'
    with psycopg.connect(database[0]) as c:
        c.execute("SET TIME ZONE 'UTC'")
        app = application(c, str(uuid4()))
        rid = run(c, app, target(c,app))
        review_id, vid = review(c, app, rid, body=body,title=body)
        observation(c, app, rid, review_id, vid)
    with psycopg.connect(database[0]) as c:
        value, title, instant = c.execute('SELECT body,title,first_observed_at FROM review_version WHERE id=%s',(vid,)).fetchone()
        assert value == title == body
        assert instant == NOW and instant.utcoffset().total_seconds() == 0
        c.execute('DELETE FROM review_observation WHERE review_id=%s',(review_id,))
        c.execute('DELETE FROM review_version WHERE id=%s',(vid,))
        c.execute('DELETE FROM review WHERE id=%s',(review_id,))
        c.execute('DELETE FROM collection_run WHERE id=%s',(rid,))
        c.execute('DELETE FROM collection_target WHERE application_id=%s',(app,))
        c.execute('DELETE FROM application WHERE id=%s',(app,))


def test_missing_reserved_version_fails_at_commit(database):
    c = psycopg.connect(database[0])
    try:
        app = application(c, str(uuid4()))
        c.execute("INSERT INTO review(application_id,source_review_id,current_version_id,first_observed_at,last_observed_at) VALUES (%s,'missing',9223372036854775800,%s,%s)",(app,NOW,NOW))
        # INSERT succeeded: the failure must occur on COMMIT.
        with pytest.raises(psycopg.errors.ForeignKeyViolation):
            c.commit()
        c.rollback()
    finally:
        c.close()


def test_owned_current_pointer_rejects_other_review(conn, seed):
    app,_,rid=seed
    a,av=review(conn,app,rid)
    b,bv=review(conn,app,rid,source_id='other')
    with pytest.raises(psycopg.errors.ForeignKeyViolation):
        with conn.transaction():
            conn.execute('UPDATE review SET current_version_id=%s WHERE id=%s',(bv,a))
            conn.execute('SET CONSTRAINTS current_version_belongs_to_review IMMEDIATE')


def test_identity_uniqueness_and_opaque_ids(conn,seed):
    app,_,rid=seed
    review(conn,app,rid,source_id='000ABC/汉字')
    with pytest.raises(psycopg.errors.UniqueViolation):
        with conn.transaction():
            review(conn,app,rid,source_id='000ABC/汉字')
    other=application(conn,'second')
    rr=run(conn,other,target(conn,other))
    review(conn,other,rr,source_id='000ABC/汉字')
    assert conn.execute("SELECT count(*) FROM review WHERE source_review_id='000ABC/汉字'").fetchone()[0] == 2


def test_version_observation_uniqueness_and_historical_hashes(conn,seed):
    app,_,rid=seed
    r,v=review(conn,app,rid)
    with pytest.raises(psycopg.errors.UniqueViolation):
        with conn.transaction(): version(conn,r,app,rid)
    version(conn,r,app,rid,number=2)
    version(conn,r,app,rid,number=3)  # repeated fingerprints are deliberately legal
    observation(conn,app,rid,r,v)
    with pytest.raises(psycopg.errors.UniqueViolation):
        with conn.transaction(): observation(conn,app,rid,r,v)


@pytest.mark.parametrize('kind',['observed_version','observation_app','detecting_run','reference_target','run_target'])
def test_cross_ownership_rejected(conn,seed,kind):
    app,tid,rid=seed
    a,av=review(conn,app,rid)
    b,bv=review(conn,app,rid,source_id='other')
    other=application(conn,'other')
    ot=target(conn,other)
    rr=run(conn,other,ot)
    with pytest.raises(psycopg.errors.ForeignKeyViolation):
        with conn.transaction():
            if kind=='observed_version': observation(conn,app,rid,a,bv)
            elif kind=='observation_app': observation(conn,other,rr,a,av)
            elif kind=='detecting_run': version(conn,a,app,rr,number=2)
            elif kind=='reference_target': run(conn,app,tid,reference=rr)
            else: run(conn,other,tid)


@pytest.mark.parametrize('field,value',[
    ('id',str(uuid4())),('target_id',99999999),('application_id',99999999),
    ('batch_id',str(uuid4())),('started_at','2026-11-02T12:00:00Z'),
    ('reference_run_id',str(uuid4())),('config_snapshot','{"changed":true}'),
])
def test_run_identity_snapshot_trigger(conn,seed,field,value):
    reject(conn,f'UPDATE collection_run SET {field}=%s WHERE id=%s',(value,seed[2]))
    conn.execute('UPDATE collection_run SET config_snapshot=config_snapshot WHERE id=%s',(seed[2],))


@pytest.mark.parametrize('table,assignment',[
    ('collection_target','min_pages=0'),('collection_target','max_pages=1'),
    ('collection_target','min_overlap_ratio=1.1'),('collection_target','max_http_requests=0'),
    ('collection_run',"execution_status='invalid'"),('collection_run',"coverage_status='invalid'"),
    ('collection_run',"config_snapshot='[]'"),('collection_run',"anomalies='{}'"),
    ('collection_run',"finished_at=NULL"),
])
def test_checks(conn,seed,table,assignment):
    # config_snapshot's trigger and check both use check_violation.
    reject(conn,f'UPDATE {table} SET {assignment} WHERE id=%s',
           (seed[1] if table=='collection_target' else seed[2],))


def test_partial_unique_indexes_and_attempt_checks(conn,seed):
    app,tid,rid=seed
    run(conn,app,tid,running=True)
    with pytest.raises(psycopg.errors.UniqueViolation):
        with conn.transaction(): run(conn,app,tid,running=True)
    aid=attempt(conn,rid,committed=True)
    with pytest.raises(psycopg.errors.UniqueViolation) as caught:
        with conn.transaction(): attempt(conn,rid,request=2,committed=True,format='xml')
    assert caught.value.diag.constraint_name == 'one_committed_response_per_page'
    for assignment in ["format='bad'",'request_number=0','page_number=0','response_bytes=-1',
                       'http_status=600',"parsing_status='pending'",'entry_count=NULL',"error_codes='{}'"]:
        reject(conn,f'UPDATE fetch_attempt SET {assignment} WHERE id=%s',(aid,))
    indexes={r[0] for r in conn.execute("SELECT indexname FROM pg_indexes WHERE schemaname='public'")}
    assert {'one_running_run_per_target','one_committed_response_per_page',
            'collection_run_reference_lookup','collection_run_batch_lookup',
            'review_observation_review_history'} <= indexes


def test_version_and_observation_checks(conn,seed):
    app,_,rid=seed
    r,v=review(conn,app,rid)
    observation(conn,app,rid,r,v)
    for assignment in ['rating=0','version_number=0',"content_hash='short'::bytea", "metadata_hash='short'::bytea"]:
        reject(conn,f'UPDATE review_version SET {assignment} WHERE id=%s',(v,))
    for assignment in ['first_observed_page=0','first_observed_position=0','occurrence_count=0',
                       'conflict_count=1',"first_action='invalid'"]:
        reject(conn,f'UPDATE review_observation SET {assignment} WHERE review_id=%s',(r,))


def test_seed_idempotent_disabled_and_preserves_settings(database):
    from feasibility.apple_ingestion.seed import seed_defaults
    engine=database[2]
    with engine.connect() as c:
        transaction=c.begin()
        try:
            first=seed_defaults(c,ROOT/'results/mainstream/app_sample_manifest.json')
            assert len(first.application_ids)==len(first.target_ids)==8
            rows=c.exec_driver_sql('SELECT enabled FROM collection_target WHERE id = ANY(%s)',(list(first.target_ids),)).all()
            assert len(rows)==8 and not any(row[0] for row in rows)
            c.exec_driver_sql('UPDATE collection_target SET enabled=true,max_http_requests=7 WHERE id=%s',(first.target_ids[0],))
            assert seed_defaults(c,ROOT/'results/mainstream/app_sample_manifest.json') == first
            assert c.exec_driver_sql('SELECT enabled,max_http_requests FROM collection_target WHERE id=%s',(first.target_ids[0],)).one()==(True,7)
        finally:
            transaction.rollback()


def test_actual_nonowner_runtime_and_report_permissions(database):
    from feasibility.apple_ingestion.permissions import RoleConfig,apply_permissions
    from psycopg import sql
    dsn,_,engine=database
    runtime='apple_runtime_'+uuid4().hex[:12]
    reporter='apple_report_'+uuid4().hex[:12]
    with engine.begin() as c:
        owner=c.exec_driver_sql('SELECT current_user').scalar_one()
        for role in (runtime,reporter):
            c.exec_driver_sql(f'CREATE ROLE "{role}" LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOREPLICATION NOBYPASSRLS')
        apply_permissions(c,RoleConfig(runtime,owner,reporter))
    # Actual authenticated connection, rather than SET ROLE under a superuser.
    with psycopg.connect(dsn,user=runtime) as c:
        assert c.execute('SELECT current_user,session_user').fetchone()==(runtime,runtime)
        assert c.execute('SELECT rolsuper FROM pg_roles WHERE rolname=current_user').fetchone()==(False,)
        assert c.execute("SELECT count(*) FROM pg_tables WHERE schemaname='public' AND tableowner=current_user").fetchone()==(0,)
        app=application(c,str(uuid4()))
        tid=target(c,app)
        rid=run(c,app,tid)
        r,v=review(c,app,rid)
        observation(c,app,rid,r,v)
        aid=attempt(c,rid)
        c.execute('UPDATE review SET last_observed_at=last_observed_at,current_version_id=current_version_id WHERE id=%s',(r,))
        c.execute('UPDATE review_observation SET occurrence_count=2,conflict_count=1 WHERE review_id=%s',(r,))
        c.execute('UPDATE collection_run SET anomalies=\'[]\' WHERE id=%s',(rid,))
        c.execute('UPDATE fetch_attempt SET response_bytes=123 WHERE id=%s',(aid,))
        denied=[('UPDATE review_version SET body=body WHERE id=%s',(v,)),
                ('DELETE FROM review_version WHERE id=%s',(v,)),
                ('UPDATE application SET name=name WHERE id=%s',(app,)),
                ('UPDATE collection_target SET enabled=true WHERE id=%s',(tid,)),
                ('UPDATE review SET source_review_id=source_review_id WHERE id=%s',(r,)),
                ('UPDATE review_observation SET first_action=first_action WHERE review_id=%s',(r,)),
                ('UPDATE collection_run SET config_snapshot=config_snapshot WHERE id=%s',(rid,)),
                ('CREATE TABLE forbidden_runtime_table(id integer)',()),
                ('ALTER TABLE review_version ADD COLUMN forbidden integer',()),
                ('CREATE OR REPLACE FUNCTION guard_collection_run_identity() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RETURN NEW; END; $$',())]
        denied += [(sql.SQL('DELETE FROM {} WHERE false').format(sql.Identifier(table)),()) for table in TABLES]
        for statement,params in denied:
            reject(c,statement,params,state='42501')
        c.execute('SET CONSTRAINTS ALL IMMEDIATE')
        c.rollback()
    with psycopg.connect(dsn,user=reporter) as c:
        for table in TABLES:
            c.execute(sql.SQL('SELECT * FROM {} LIMIT 0').format(sql.Identifier(table)))
        reject(c,"INSERT INTO application(source,source_application_id,name,analytical_category) VALUES ('apple_app_store','forbidden','x','education')",state='42501')
        c.rollback()

"""Deployment preparation on private PostgreSQL; no host deployment or real HTTP."""
from dataclasses import replace
from datetime import datetime,timezone
import json
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import event,text

from feasibility.apple_ingestion.deployment import (
    DatabaseConfig,DeploymentConfig,DeploymentError,DiagnosticsConfig,RetentionConfig,
    deployment_engine,diagnostics_probe,grant_permissions,initialize_database,
    initialization_plan,load_config,preflight,
)
from feasibility.apple_ingestion.permissions import RoleConfig

ROOT=Path(__file__).resolve().parents[1]


def template():
    return load_config(ROOT/'deploy/apple_ingestion/unix.example.json')


def test_templates_pending_no_credentials_no_implicit_authorization():
    for name in ('unix.example.json','tls.example.json','long-term-retention.example.json'):
        path=ROOT/'deploy/apple_ingestion'/name
        cfg=load_config(path)
        assert cfg.retention.duration_days is None
        assert cfg.retention.complete is (cfg.retention.mode=='long_term')
        assert cfg.retention.owner is cfg.retention.policy_ref is None
        encoded=json.dumps(cfg.to_dict())
        assert 'postgresql://' not in encoded and 'password' not in encoded.lower()
        assert 'arrangement_confirmed' not in cfg.to_dict()['retention']
        assert DeploymentConfig.from_dict(cfg.to_dict())==cfg


def test_legacy_finite_retention_without_new_fields_remains_valid():
    data=template().to_dict()
    data['retention']={'state':'documented','owner':'synthetic-operator','duration_days':7,
        'policy_ref':'synthetic-finite','backup_handling_ref':'synthetic-backups',
        'export_handling_ref':'synthetic-exports','expiry_review_ref':'synthetic-expiry'}
    config=DeploymentConfig.from_dict(data)
    assert config.retention.mode=='finite_days' and config.retention.complete
    assert not config.retention.arrangement_confirmed


@pytest.mark.parametrize('confirmed',[False,True])
def test_explicit_long_term_has_no_duration_or_automatic_authorization(confirmed):
    retention=RetentionConfig('documented','synthetic-operator',None,'synthetic-long-term',
        'synthetic-backups','synthetic-exports','synthetic-periodic-review',
        mode='long_term',arrangement_confirmed=confirmed)
    assert retention.technical_complete and retention.complete
    cfg=replace(template(),retention=retention)
    assert DeploymentConfig.from_dict(cfg.to_dict())==cfg
    assert cfg.to_dict()['retention']['duration_days'] is None
    assert 'arrangement_confirmed' not in cfg.to_dict()['retention']


def test_retention_accepts_mode_only_and_legacy_confirmation_is_semantically_ignored():
    data=template().to_dict()
    data['retention']={'mode':'long_term','duration_days':None}
    minimal=DeploymentConfig.from_dict(data)
    assert minimal.retention.complete and minimal.retention.owner is None
    for confirmed in (False,True,None,'legacy-not-an-approval',{'uninterpreted':True},[]):
        legacy={**data,'retention':{**data['retention'],'arrangement_confirmed':confirmed}}
        restored=DeploymentConfig.from_dict(legacy)
        assert restored==minimal
        assert restored.to_dict()==minimal.to_dict()


@pytest.mark.parametrize('change',[
    {'mode':'long_term','duration_days':7}, {'mode':'unknown'},
])
def test_invalid_or_ambiguous_long_term_configuration_is_rejected(change):
    data=template().to_dict()
    data['retention'].update(change)
    with pytest.raises(DeploymentError):
        DeploymentConfig.from_dict(data)


@pytest.mark.parametrize('change',[
    {'duration_days':0},{'duration_days':True},{'duration_days':-1},
    {'state':'approved'},{'state':'documented'},
])
def test_retention_pending_or_invalid_cannot_be_guessed_ready(change):
    data=template().to_dict()
    data['retention'].update(change)
    with pytest.raises(DeploymentError):
        DeploymentConfig.from_dict(data)


def test_review_plan_is_offline_and_mutations_default_to_review(monkeypatch):
    cfg=template()
    monkeypatch.setattr('sqlalchemy.engine.Engine.connect',lambda *args:pytest.fail('plan contacted database'))
    plan=initialization_plan(cfg)
    assert plan['execution']=='review_only' and not plan['live_authorized']
    assert plan['revision']=='0001_apple_ingestion'
    assert 'CREATE TABLE review_version' in plan['migration_sql']
    assert plan['migration_sql'].count('CREATE TABLE ')==8  # seven core + Alembic version
    assert all('NOSUPERUSER' in sql and 'PASSWORD' not in sql for sql in plan['administrator_role_sql'])
    assert initialize_database(None,cfg)==plan
    assert grant_permissions(None,cfg)==tuple(plan['permission_sql'])


@pytest.mark.parametrize('supplied',[
    'postgresql://PRIVATE_SECRET@remote/shared',
    'postgresql+psycopg://apple_ingestion_owner@remote/db',
    'postgresql+psycopg://apple_ingestion_owner/db?host=/tmp/pg&service=shared',
    'postgresql+psycopg://apple_ingestion_owner/db?host=/tmp/pg&hostaddr=198.51.100.2',
])
def test_unsafe_unix_role_urls_reject_without_echo_or_connection(supplied):
    with pytest.raises(DeploymentError) as failure:
        deployment_engine(template(),'owner',environ={'APPLE_INGESTION_OWNER_URL':supplied})
    assert 'PRIVATE_SECRET' not in str(failure.value)
    assert 'postgresql' not in str(failure.value)


def test_environment_reference_is_explicit_and_tls_requires_verify_full(tmp_path):
    cfg=template()
    with pytest.raises(DeploymentError,match='EXPLICIT_ROLE'):
        deployment_engine(cfg,'owner',environ={'DATABASE_URL':'ignored'})
    cert=tmp_path/'root.crt'
    cert.write_text('configuration-only placeholder, not a tested TLS certificate')
    tls=replace(cfg,database=replace(cfg.database,transport='tls_verify_full',tls_root_cert_env='TEST_ROOT_CERT'))
    env={'APPLE_INGESTION_OWNER_URL':'postgresql+psycopg://apple_ingestion_owner@db.example.invalid/fixture',
         'TEST_ROOT_CERT':str(cert)}
    engine=deployment_engine(tls,'owner',environ=env)
    try:
        assert engine.url.query['sslmode']=='verify-full' and engine.url.query['sslrootcert']==str(cert)
        assert engine.hide_parameters and not engine.echo
    finally:
        engine.dispose()
    env['APPLE_INGESTION_OWNER_URL']+='?sslmode=require'
    with pytest.raises(DeploymentError):
        deployment_engine(tls,'owner',environ=env)


def test_diagnostics_default_read_only_and_explicit_probe_is_private(tmp_path):
    cfg=replace(template(),diagnostics=DiagnosticsConfig('TEST_DIAGNOSTIC_PATH','synthetic-test-operator'))
    env={'TEST_DIAGNOSTIC_PATH':str(tmp_path/'diagnostics.jsonl')}
    before=set(tmp_path.iterdir())
    assert diagnostics_probe(cfg,environ=env)['ready']
    assert set(tmp_path.iterdir())==before
    probe=diagnostics_probe(cfg,environ=env,execute=True)
    assert probe['write_probe_executed'] and not probe['durability_guaranteed']
    assert set(tmp_path.iterdir())==before  # no fictitious spool event left behind
    bad=tmp_path/'diagnostics.jsonl'
    bad.write_text('PRIVATE_DIAGNOSTIC_PLACEHOLDER')
    bad.chmod(0o644)
    assert not diagnostics_probe(cfg,environ=env)['ready']


@pytest.fixture(params=['database_owner','schema_owner'])
def deployed_roles(apple_database,tmp_path,request):
    """Admin only provisions a fresh test DB/roles; owner performs all schema work."""
    import psycopg
    from psycopg import sql
    from feasibility.apple_ingestion.db import create_db_engine
    token=uuid4().hex[:12]
    roles=RoleConfig('runtime_'+token,'owner_'+token,'report_'+token)
    database='apple_phase_a_deploy_'+token
    admin_url=apple_database.url
    config=replace(template(),roles=roles,
        diagnostics=DiagnosticsConfig('TEST_DEPLOYMENT_SPOOL','synthetic-test-operator'))
    environment={'TEST_DEPLOYMENT_SPOOL':str(tmp_path/'diagnostics.jsonl')}
    engines={}
    admin=create_db_engine(admin_url)
    with admin.connect().execution_options(isolation_level='AUTOCOMMIT') as c:
        for name in (roles.maintenance_role,roles.runtime_role,roles.report_role):
            c.exec_driver_sql(f'CREATE ROLE "{name}" LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOREPLICATION NOBYPASSRLS')
        c.exec_driver_sql(f'CREATE DATABASE "{database}"')
        if request.param=='database_owner':
            c.exec_driver_sql(f'ALTER DATABASE "{database}" OWNER TO "{roles.maintenance_role}"')
    setup_admin=create_db_engine(admin_url.set(database=database))
    try:
        if request.param=='schema_owner':
            with setup_admin.begin() as c:
                c.exec_driver_sql(f'ALTER SCHEMA public OWNER TO "{roles.maintenance_role}"')
        for kind,name,reference in [('owner',roles.maintenance_role,config.database.owner_url_env),
                ('runtime',roles.runtime_role,config.database.runtime_url_env),
                ('report',roles.report_role,config.database.report_url_env)]:
            environment[reference]=admin_url.set(database=database,username=name,password=None).render_as_string(hide_password=False)
            engines[kind]=deployment_engine(config,kind,environ=environment)
        yield config,engines,environment
    finally:
        for engine in engines.values():
            engine.dispose()
        setup_admin.dispose()
        with admin.connect().execution_options(isolation_level='AUTOCOMMIT') as c:
            c.exec_driver_sql(f'DROP DATABASE "{database}" WITH (FORCE)')
            for name in (roles.runtime_role,roles.report_role,roles.maintenance_role):
                c.exec_driver_sql(f'DROP ROLE "{name}"')
        admin.dispose()


def provision(config,engines):
    with engines['owner'].begin() as c:
        first=initialize_database(c,config,execute=True)
        assert first['application_count']==first['target_count']==8
        second=initialize_database(c,config,execute=True)
        assert first==second
        grant_permissions(c,config,execute=True)


def test_nonadmin_owner_migration_seed_grants_and_operational_preflight(deployed_roles):
    config,engines,env=deployed_roles
    with engines['owner'].connect() as c:
        with pytest.raises(DeploymentError,match='CALLER_OWNED'):
            initialize_database(c,config,execute=True)
    provision(config,engines)
    with engines['owner'].connect() as c,engines['runtime'].connect() as runtime:
        assert c.execute(text('SELECT current_user,session_user')).one()==(config.roles.maintenance_role,)*2
        assert not c.execute(text('SELECT rolsuper FROM pg_roles WHERE rolname=current_user')).scalar_one()
        assert c.execute(text('SELECT count(*) FROM application')).scalar_one()==8
        assert c.execute(text('SELECT count(*) FROM collection_target WHERE enabled')).scalar_one()==0
        assert c.execute(text("SELECT current_setting('search_path'),current_schema()")).one()==('public','public')
        assert c.execute(text("SELECT current_setting('TimeZone'),current_setting('lock_timeout'),current_setting('statement_timeout')")).one()==('UTC','5s','30s')
        statements=[]
        def capture(_connection,_cursor,statement,*args):
            statements.append(statement)
        event.listen(engines['owner'],'before_cursor_execute',capture)
        try:
            result=preflight(c,config,for_live=True,environ=env,runtime_connection=runtime)
        finally:
            event.remove(engines['owner'],'before_cursor_execute',capture)
        assert statements and all(statement.lstrip().startswith('SELECT') for statement in statements)
        assert result['database_ready'] and result['runtime_login_verified']
        assert result['live_ready'] and result['operational_ready'] and not result['live_authorized']
        assert not result['retention_ready'] and not result['retention_runtime_gate']
        assert result['blockers']==[] and result['status']=='operational_ready'
        assert 'postgresql://' not in json.dumps(result)
        assert not c.closed and c.in_transaction()  # caller still owns transaction


def test_runtime_actual_login_full_page_pipeline_and_report_read_only(deployed_roles,tmp_path):
    import psycopg
    from feasibility.apple_ingestion.contracts import ConfigSnapshot
    from feasibility.apple_ingestion.controller import Controller
    from feasibility.apple_ingestion.parser import PARSER_VERSION
    from feasibility.apple_ingestion.recovery import DiagnosticSpool
    from feasibility.apple_ingestion.reporting import run_report
    from feasibility.apple_ingestion.synthetic import ScenarioSession,SimulatedClock
    from feasibility.apple_ingestion.seed import load_seed_manifest
    from feasibility.apple_ingestion.transport import BoundedTransport
    config,engines,env=deployed_roles
    provision(config,engines)
    apps=load_seed_manifest(ROOT/'results/mainstream/app_sample_manifest.json')
    with engines['owner'].connect() as c:
        app,tid=c.execute(text("""SELECT a.id,t.id FROM application a JOIN collection_target t ON a.id=t.application_id
            WHERE a.source_application_id=:source"""),dict(source=apps[0].source_application_id)).one()
    clock=SimulatedClock(datetime(2026,10,29,16,tzinfo=timezone.utc))
    session=ScenarioSession([row.source_application_id for row in apps],clock)
    controller=Controller(engines['runtime'],BoundedTransport(session,clock=clock.monotonic,sleep=clock.sleep),
        DiagnosticSpool(tmp_path/'runtime-diagnostics.jsonl'),now=clock.now,monotonic=clock.monotonic)
    snapshot=ConfigSnapshot(application_id=app,target_id=tid,source_application_id=apps[0].source_application_id,
        software_revision='synthetic-nonowner-runtime',parser_version=PARSER_VERSION)
    result=controller.run_target(snapshot,uuid4())
    assert result.execution_status=='succeeded' and result.committed_pages==5
    assert len(session.calls)==5
    with engines['runtime'].connect() as c:
        assert c.execute(text('SELECT current_user,session_user')).one()==(config.roles.runtime_role,)*2
        assert not c.execute(text('SELECT rolsuper FROM pg_roles WHERE rolname=current_user')).scalar_one()
        assert c.execute(text('SELECT count(*) FROM review_version')).scalar_one()==100
        assert c.execute(text('SELECT count(*) FROM review_observation')).scalar_one()==100
        for statement in ('UPDATE review_version SET body=body','DELETE FROM review_version',
                'DELETE FROM review','UPDATE application SET name=name','UPDATE collection_target SET enabled=true'):
            with pytest.raises(Exception) as error:
                with c.begin_nested():
                    c.execute(text(statement))
            assert getattr(error.value.orig,'sqlstate',None)=='42501'
    with engines['report'].connect() as c:
        assert c.execute(text('SELECT current_user,session_user')).one()==(config.roles.report_role,)*2
        report=run_report(c,result.run_id)
        assert report['evidence_kind']=='synthetic'
        assert 'SYNTHETIC_BODY' not in json.dumps(report)
        with pytest.raises(Exception) as error:
            with c.begin_nested():
                c.execute(text("UPDATE collection_run SET anomalies='[]'"))
        assert getattr(error.value.orig,'sqlstate',None)=='42501'


def test_documented_retention_is_not_execution_authorization(deployed_roles):
    config,engines,env=deployed_roles
    provision(config,engines)
    documented=replace(config,retention=RetentionConfig('documented','synthetic-operator',7,
        'synthetic-retention-fixture','synthetic-backup-fixture','synthetic-export-fixture','synthetic-expiry-review'))
    with engines['owner'].connect() as owner,engines['runtime'].connect() as runtime:
        ready=preflight(owner,documented,for_live=True,environ=env,runtime_connection=runtime)
        assert ready['live_ready'] and ready['retention_ready']
        assert not ready['live_authorized'] and not ready['live_policy_checked']
        assert ready['authorization_owner']=='live.ProjectExecutionPolicy'
        assert ready['legacy_authorization_owner']=='live.LiveExecutionPolicy'
    with engines['owner'].connect() as owner:
        blocked=preflight(owner,documented,for_live=True,environ=env)
        assert not blocked['live_ready'] and 'RUNTIME_LOGIN_NOT_VERIFIED' in blocked['blockers']


def test_retention_metadata_and_legacy_flag_do_not_gate_operational_readiness(deployed_roles):
    config,engines,env=deployed_roles
    provision(config,engines)
    profiles=(RetentionConfig(mode='long_term'),
        RetentionConfig(state='documented',mode='long_term'),
        RetentionConfig(state='documented',duration_days=7),RetentionConfig())
    with engines['owner'].connect() as owner,engines['runtime'].connect() as runtime:
        for profile in profiles:
            reports=[]
            for confirmed in (False,True):
                candidate=replace(config,retention=replace(profile,arrangement_confirmed=confirmed))
                ready=preflight(owner,candidate,for_live=True,environ=env,runtime_connection=runtime)
                assert ready['database_ready'] and ready['live_ready'] and ready['operational_ready']
                assert ready['status']=='operational_ready' and ready['blockers']==[]
                assert ready['live_ready_semantics']=='deployment_operational_alias'
                assert ready['retention_ready'] is profile.technical_complete
                assert not ready['retention_runtime_gate']
                assert ready['data_use_and_retention_applicability']=='not_assessed_by_software'
                assert not ready['live_authorized'] and not ready['live_policy_checked']
                assert 'arrangement_confirmed' not in ready['retention']
                assert 'retention_arrangement_confirmed' not in ready
                reports.append(ready)
            assert reports[0]==reports[1]


def test_preflight_detects_extra_version_column_grant(deployed_roles):
    config,engines,env=deployed_roles
    provision(config,engines)
    with engines['owner'].begin() as c:
        c.exec_driver_sql(f'GRANT UPDATE(body) ON review_version TO "{config.roles.runtime_role}"')
    with engines['owner'].connect() as c:
        check=preflight(c,config,environ=env)
        assert not check['database_ready']
        assert not check['operational_ready'] and check['status']=='operational_blocked'
        assert 'EXACT_RUNTIME_OR_REPORT_UPDATE_GRANTS_REQUIRED' in check['blockers']


def test_initialization_and_grants_respect_caller_rollback(deployed_roles):
    config,engines,_=deployed_roles
    with engines['owner'].connect() as c:
        transaction=c.begin()
        initialize_database(c,config,execute=True)
        grant_permissions(c,config,execute=True)
        assert c.execute(text('SELECT count(*) FROM application')).scalar_one()==8
        transaction.rollback()
        assert c.execute(text("SELECT count(*) FROM pg_tables WHERE schemaname='public'")).scalar_one()==0


def test_other_database_same_runtime_login_cannot_verify_this_deployment(deployed_roles,apple_database):
    from feasibility.apple_ingestion.db import create_db_engine
    config,engines,env=deployed_roles
    provision(config,engines)
    other=create_db_engine(engines['runtime'].url.set(database=apple_database.url.database))
    try:
        with engines['owner'].connect() as owner,other.connect() as foreign_runtime:
            assert foreign_runtime.execute(text('SELECT current_user')).scalar_one()==config.roles.runtime_role
            result=preflight(owner,config,for_live=True,environ=env,runtime_connection=foreign_runtime)
            assert not result['live_ready'] and not result['runtime_login_verified']
            assert 'ACTUAL_RUNTIME_LOGIN_REQUIRED' in result['blockers']
    finally:
        other.dispose()
    mismatched=dict(env)
    mismatched[config.database.report_url_env]=engines['report'].url.set(database='another_database').render_as_string(hide_password=False)
    # Connect_timeout is injected by our factory; the rejection remains before
    # connecting even when caller-provided DSNs disagree on deployment identity.
    with pytest.raises(DeploymentError,match='MISMATCHED_ROLE'):
        deployment_engine(config,'owner',environ=mismatched)

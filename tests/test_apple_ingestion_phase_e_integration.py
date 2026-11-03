"""Cross-module E acceptance on disposable PostgreSQL and offline HTTP only.

A real requests.Session uses an in-process BaseAdapter. LIVE below names the
execution branch under test, not real Apple evidence or genuine authorization.
All approval/retention records, review content and operator identities are
explicit synthetic fixtures. No DNS/TLS/HTTP connection is attempted.
"""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from io import BytesIO
import json
from pathlib import Path
from urllib.parse import urlsplit
from uuid import uuid4
from xml.sax.saxutils import escape

import pytest
import requests
from requests.adapters import BaseAdapter
from sqlalchemy import select, text, update

from feasibility.apple_ingestion.contracts import ConfigSnapshot, RunMode
from feasibility.apple_ingestion.controller import ControllerError
from feasibility.apple_ingestion.deployment import (
    DeploymentConfig, deployment_engine, grant_permissions, initialize_database, preflight,
)
from feasibility.apple_ingestion.live import (
    LiveExecutionApproval, LiveExecutionPolicy, LivePolicyError, prepare_live_controller,
)
from feasibility.apple_ingestion.models import CollectionRun, CollectionTarget, FetchAttempt, ReviewVersion
from feasibility.apple_ingestion.parser import PARSER_VERSION
from feasibility.apple_ingestion.recovery import DiagnosticSpool

ROOT = Path(__file__).resolve().parents[1]
NOW = datetime(2026, 11, 3, 12, tzinfo=timezone.utc)
R, T, F, V = (model.__table__ for model in (CollectionRun, CollectionTarget, FetchAttempt, ReviewVersion))
TEXT = 'SYNTHETIC_PRIVATE_FULL_BODY\n完整正文😀 &amp; ' * 2000 + 'FULL_TAIL'
TITLE = 'SYNTHETIC_PRIVATE_TITLE &amp; 😀'


class OfflineClock:
    def __init__(self):
        self.seconds = 0.0
    def monotonic(self):
        return self.seconds
    def sleep(self, seconds):
        self.seconds += seconds
    def now(self):
        return NOW + timedelta(seconds=self.seconds)


def _entry(source_id):
    return {'id': {'label': source_id}, 'title': {'label': TITLE}, 'content': {'label': TEXT},
            'im:rating': {'label': '2'}, 'im:version': {'label': '1.0'},
            'updated': {'label': '2026-11-03T04:00:00-08:00'}}


class OfflineAppleAdapter(BaseAdapter):
    def __init__(self, observer_engine, clock, *, expire_on_send=False):
        self.calls = []
        self.observer_engine, self.clock, self.expire_on_send = observer_engine, clock, expire_on_send
        self.closed = False
    def send(self, request, **options):
        url = urlsplit(request.url)
        assert (url.scheme, url.netloc, url.query) == ('https', 'itunes.apple.com', '')
        assert options['stream'] is True and options['timeout'] == (10.0, 25.0)
        assert options['verify'] is True and options['cert'] is None and options['proxies'] == {}
        assert not {'authorization', 'proxy-authorization', 'cookie'} & {key.lower() for key in request.headers}
        assert request.headers['User-Agent'].startswith('DataSourceFeasibility/')
        with self.observer_engine.connect() as connection:
            holders = connection.execute(text("""SELECT a.usename,a.state,a.xact_start
                FROM pg_stat_activity a WHERE a.pid IN
                (SELECT pid FROM pg_locks WHERE locktype='advisory' AND granted)""")).all()
        assert len(holders) == 1 and holders[0].state == 'idle' and holders[0].xact_start is None
        self.calls.append(dict(url=request.url, headers=dict(request.headers), at=self.clock.monotonic(),
                               runtime_login=holders[0].usename))
        page = int(url.path.split('/page=')[1].split('/')[0])
        format = url.path.rsplit('/', 1)[-1]
        if self.expire_on_send:
            self.clock.seconds += 301
        if page == 1 and format == 'json':
            payload = b'{"feed":{}}'
        elif format == 'xml':
            fields = ''.join('<entry>' + ''.join(f'<{key}>' + escape(value['label']) + f'</{key}>'
                for key, value in _entry(identity).items()) + '</entry>' for identity in ('opaque-A', 'opaque-B'))
            payload = ('<feed xmlns="http://www.w3.org/2005/Atom" xmlns:im="http://itunes.apple.com/rss">'
                       + fields + '</feed>').encode()
        else:
            identities = ('opaque-B', 'opaque-C') if page == 2 else (f'opaque-{page}-X', f'opaque-{page}-Y')
            payload = json.dumps({'feed': {'entry': [_entry(identity) for identity in identities]}},
                                 ensure_ascii=False).encode()
        response = requests.Response()
        response.status_code = 200
        response.url, response.request = request.url, request
        response.headers['Content-Type'] = 'application/atom+xml' if format == 'xml' else 'application/json'
        response.raw = BytesIO(payload)
        return response
    def close(self):
        self.closed = True


@pytest.fixture
def offline_deployment(apple_database, tmp_path):
    """Actual non-admin role logins; all objects/roles belong to this test only."""
    admin = apple_database
    suffix = uuid4().hex[:12]
    names = {name: f'e_int_{name}_{suffix}' for name in ('owner', 'runtime', 'report')}
    engines = {}
    created = []
    with admin.connect() as connection:
        database, original_owner = connection.execute(text('SELECT current_database(),current_user')).one()
    try:
        with admin.begin() as connection:
            for name in names.values():
                connection.exec_driver_sql(f'CREATE ROLE "{name}" LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOREPLICATION NOBYPASSRLS')
                created.append(name)
            connection.exec_driver_sql(f'ALTER DATABASE "{database}" OWNER TO "{names["owner"]}"')
            connection.exec_driver_sql(f'ALTER SCHEMA public OWNER TO "{names["owner"]}"')
            objects = connection.execute(text("SELECT relname,relkind FROM pg_class WHERE relnamespace='public'::regnamespace AND relkind='r'")).all()
            for name, _ in objects:
                # Identity sequences follow their table's owner automatically.
                connection.exec_driver_sql(f'ALTER TABLE public."{name}" OWNER TO "{names["owner"]}"')
            connection.exec_driver_sql(f'ALTER FUNCTION public.guard_collection_run_identity() OWNER TO "{names["owner"]}"')
        data = json.loads((ROOT / 'deploy/apple_ingestion/unix.example.json').read_text())
        data['roles'].update(maintenance_role=names['owner'], runtime_role=names['runtime'], report_role=names['report'])
        data['retention'].update(state='documented', owner='SYNTHETIC_TEST_RETENTION_OWNER', duration_days=7,
            policy_ref='SYNTHETIC_TEST_RETENTION_REFERENCE', backup_handling_ref='SYNTHETIC_TEST_BACKUP',
            export_handling_ref='SYNTHETIC_TEST_EXPORT', expiry_review_ref='SYNTHETIC_TEST_EXPIRY_REVIEW')
        data['diagnostics']['operator'] = 'SYNTHETIC_TEST_OPERATOR'
        config = DeploymentConfig.from_dict(data)
        private = tmp_path / 'private'
        private.mkdir(mode=0o700)
        receipts = private / 'receipts'
        receipts.mkdir(mode=0o700)
        environment = {getattr(config.database, f'{role}_url_env'): admin.url.set(username=names[role]).render_as_string(hide_password=False)
                       for role in ('owner', 'runtime', 'report')}
        environment[config.diagnostics.spool_path_env] = str(private / 'diagnostics.jsonl')
        for role in ('owner', 'runtime', 'report'):
            engines[role] = deployment_engine(config, role, environ=environment)
        with engines['owner'].begin() as connection:
            initialize_database(connection, config, execute=True)
            grant_permissions(connection, config, execute=True)
        with engines['owner'].connect() as connection:
            app, target = connection.execute(text("SELECT application_id,id FROM collection_target ORDER BY id LIMIT 1")).one()
            source = connection.scalar(text('SELECT source_application_id FROM application WHERE id=:app'), {'app': app})
        snapshot = ConfigSnapshot(application_id=app, target_id=target, source_application_id=source,
            software_revision='SYNTHETIC_PHASE_E_INTEGRATION', parser_version=PARSER_VERSION, run_mode=RunMode.LIVE,
            access_decision_ref='SYNTHETIC_TEST_ACCESS_REFERENCE', retention_policy_ref=config.retention.policy_ref)
        approval = LiveExecutionApproval(approval_id=uuid4(), operator='SYNTHETIC_TEST_OPERATOR',
            approved_by='SYNTHETIC_TEST_APPROVER', approved_at=NOW-timedelta(minutes=1), valid_from=NOW-timedelta(seconds=1),
            valid_until=NOW+timedelta(minutes=5), source_application_ids=(source,),
            access_basis_ref=snapshot.access_decision_ref, retention_policy_ref=snapshot.retention_policy_ref,
            status='approved', readiness_confirmed=True, execution_authorized=True)
        yield dict(admin=admin, engines=engines, config=config, environment=environment, receipts=receipts,
            snapshot=snapshot, approval=approval, spool=DiagnosticSpool(private / 'diagnostics.jsonl'), names=names)
    finally:
        for engine in engines.values():
            engine.dispose()
        with admin.begin() as connection:
            existing = [name for name in created if connection.scalar(text(
                'SELECT EXISTS(SELECT 1 FROM pg_roles WHERE rolname=:name)'), {'name': name})]
            for name in existing:
                connection.exec_driver_sql(f'REASSIGN OWNED BY "{name}" TO "{original_owner}"')
                connection.exec_driver_sql(f'DROP OWNED BY "{name}"')
            for name in reversed(existing):
                connection.exec_driver_sql(f'DROP ROLE "{name}"')


def _factory(deployment, clock, *, expire_on_send=False):
    sessions, adapters = [], []
    def create():
        assert list(deployment['receipts'].glob('*.json'))  # claim precedes Session creation
        session = requests.Session()
        adapter = OfflineAppleAdapter(deployment['admin'], clock, expire_on_send=expire_on_send)
        session.mount('https://', adapter)
        sessions.append(session)
        adapters.append(adapter)
        return session
    return create, sessions, adapters


def _enable(deployment):
    with deployment['engines']['owner'].begin() as connection:
        connection.execute(update(T).where(T.c.id == deployment['snapshot'].target_id).values(enabled=True))


def _rows(deployment, table):
    with deployment['engines']['report'].connect() as connection:
        return [dict(row) for row in connection.execute(select(table).order_by(table.c.id)).mappings()]


def _prepare(deployment, policy, clock, factory, *, config=None, runtime=None, audit=None, batch=None):
    return prepare_live_controller(runtime or deployment['engines']['runtime'], deployment['snapshot'], batch or uuid4(),
        deployment['spool'], policy=policy, deployment_config=config or deployment['config'],
        audit_engine=audit or deployment['engines']['owner'], environ=deployment['environment'],
        session_factory=factory, now=clock.now, clock=clock.monotonic, sleep=clock.sleep)


def test_e_default_pending_decisions_and_disabled_target_block_before_http_resources(offline_deployment):
    d = offline_deployment
    clock = OfflineClock()
    factory, sessions, adapters = _factory(d, clock)
    cases = [
        (None, d['config'], 'LIVE_MODE_DISABLED'),
        (LiveExecutionPolicy(LiveExecutionApproval(), d['receipts']), d['config'], 'LIVE_MODE_DISABLED'),
        (LiveExecutionPolicy(replace(d['approval'], access_basis_ref=None), d['receipts']), d['config'], 'LIVE_APPROVAL_INVALID'),
        (LiveExecutionPolicy(d['approval'], d['receipts']), replace(d['config'], retention=replace(
            d['config'].retention, state='pending', owner=None, duration_days=None, policy_ref=None)), 'LIVE_DEPLOYMENT_NOT_READY'),
        (LiveExecutionPolicy(replace(d['approval'], valid_until=NOW-timedelta(microseconds=1)), d['receipts']),
            d['config'], 'LIVE_APPROVAL_OUTSIDE_VALIDITY'),
        (LiveExecutionPolicy(d['approval'], d['receipts']), d['config'], 'LIVE_TARGET_DISABLED'),
    ]
    for policy, config, expected in cases:
        with pytest.raises(ControllerError, match=expected):
            with _prepare(d, policy, clock, factory, config=config):
                pytest.fail('closed gate prepared a collector')
        assert sessions == adapters == [] and not list(d['receipts'].iterdir())
        assert _rows(d, R) == _rows(d, F) == _rows(d, V) == []


def test_e_nonadmin_runtime_real_requests_adapter_full_pipeline_and_receipt_reuse(offline_deployment):
    from dataclasses import asdict
    d = offline_deployment
    _enable(d)
    with d['engines']['owner'].connect() as audit, d['engines']['runtime'].connect() as runtime:
        report = preflight(audit, d['config'], for_live=True, environ=d['environment'], runtime_connection=runtime)
        assert report['live_ready'] and report['runtime_login_verified'] and report['retention_documented']
        assert not report['live_authorized'] and not report['real_http_performed']
    clock = OfflineClock()
    factory, sessions, adapters = _factory(d, clock)
    policy = LiveExecutionPolicy(d['approval'], d['receipts'])
    batch = uuid4()
    with prepare_live_controller(d['engines']['runtime'], d['snapshot'], batch, d['spool'],
            policy=policy, deployment_config=d['config'], audit_engine=d['engines']['owner'],
            environ=d['environment'], session_factory=factory, now=clock.now,
            clock=clock.monotonic, sleep=clock.sleep) as controller:
        assert not sessions and not list(d['receipts'].iterdir())
        with pytest.raises(ControllerError, match='LIVE_SINGLE_RUN_ONLY'):
            controller.run_batch((d['snapshot'],)*8, uuid4())
        assert not sessions and not list(d['receipts'].iterdir()) and not _rows(d, R)
        result = controller.run_target(d['snapshot'], batch)
    assert result.execution_status == 'succeeded' and result.coverage_status == 'baseline'
    assert result.committed_pages == 5 and result.request_count == 6
    assert len(sessions) == len(adapters) == 1 and adapters[0].closed
    assert len(adapters[0].calls) == 6
    assert {call['runtime_login'] for call in adapters[0].calls} == {d['names']['runtime']}
    assert [call['at'] for call in adapters[0].calls] == [0, 2, 4, 6, 8, 10]
    attempts, versions, runs = _rows(d, F), _rows(d, V), _rows(d, R)
    assert len(runs) == 1 and len(versions) == 9
    assert sum(row['persistence_status'] == 'committed' for row in attempts) == 5
    assert attempts[0]['format'] == 'json' and attempts[0]['persistence_status'] == 'not_applicable'
    assert attempts[1]['format'] == 'xml' and attempts[1]['persistence_status'] == 'committed'
    assert all(row['finished_at'] is not None and row['http_status'] == 200 for row in attempts)
    assert all(row['body'] == TEXT and row['title'] == TITLE for row in versions)
    assert all(len(row['content_hash']) == len(row['metadata_hash']) == 32 for row in versions)
    assert runs[0]['config_snapshot'] == d['snapshot'].to_dict()
    diagnostics = json.dumps(dict(result=asdict(result), attempts=attempts, runs=runs), default=str)
    assert 'SYNTHETIC_PRIVATE_FULL_BODY' not in diagnostics and 'SYNTHETIC_PRIVATE_TITLE' not in diagnostics
    assert d['spool'].entries() == ()
    receipts = list(d['receipts'].glob('*.json'))
    assert len(receipts) == 1 and receipts[0].stat().st_mode & 0o777 == 0o600
    with d['engines']['runtime'].connect() as runtime:
        assert runtime.execute(text('SELECT current_user,session_user')).one() == (d['names']['runtime'],)*2
        assert not runtime.scalar(text('SELECT rolsuper FROM pg_roles WHERE rolname=current_user'))
        assert not runtime.scalar(text("SELECT has_table_privilege(current_user,'review_version','UPDATE,DELETE')"))
        assert not runtime.scalar(text("SELECT has_column_privilege(current_user,'collection_target','enabled','UPDATE')"))
    reused = LiveExecutionPolicy(d['approval'], d['receipts'])
    reuse_batch = uuid4()
    with pytest.raises(ControllerError, match='LIVE_APPROVAL_CONSUMED'):
        with _prepare(d, reused, clock, factory, batch=reuse_batch) as controller:
            # Receipt reservation is lazy, so consuming execution, not entering
            # an idle context, is the point that must refuse a reused approval.
            controller.run_target(d['snapshot'], reuse_batch)
    assert len(sessions) == 1 and len(_rows(d, R)) == 1 and len(_rows(d, F)) == 6


def test_e_approval_deadline_during_real_response_stream_stops_without_fallback(offline_deployment):
    d = offline_deployment
    _enable(d)
    clock = OfflineClock()
    factory, sessions, adapters = _factory(d, clock, expire_on_send=True)
    batch = uuid4()
    with prepare_live_controller(d['engines']['runtime'], d['snapshot'], batch, d['spool'],
            policy=LiveExecutionPolicy(d['approval'], d['receipts']), deployment_config=d['config'],
            audit_engine=d['engines']['owner'], environ=d['environment'], session_factory=factory,
            now=clock.now, clock=clock.monotonic, sleep=clock.sleep) as controller:
        result = controller.run_target(d['snapshot'], batch)
    assert result.stop_reason == 'target_deadline' and result.execution_status == 'failed'
    assert len(sessions) == 1 and len(adapters[0].calls) == 1 and adapters[0].closed
    assert _rows(d, V) == []
    attempt, = _rows(d, F)
    assert attempt['persistence_status'] == 'not_applicable'
    assert 'TARGET_DEADLINE' in attempt['error_codes']
    assert _rows(d, R)[0]['finished_at'] is not None
    assert len(list(d['receipts'].glob('*.json'))) == 1


def test_e_prepared_snapshot_batch_cannot_be_swapped_before_execution(offline_deployment):
    d = offline_deployment
    _enable(d)
    clock = OfflineClock()
    factory, sessions, adapters = _factory(d, clock)
    batch = uuid4()
    with prepare_live_controller(d['engines']['runtime'], d['snapshot'], batch, d['spool'],
            policy=LiveExecutionPolicy(d['approval'], d['receipts']), deployment_config=d['config'],
            audit_engine=d['engines']['owner'], environ=d['environment'], session_factory=factory,
            now=clock.now, clock=clock.monotonic, sleep=clock.sleep) as controller:
        with pytest.raises(ControllerError, match='LIVE_APPROVAL_SCOPE_MISMATCH'):
            controller.run_target(replace(d['snapshot'], software_revision='SYNTHETIC_CHANGED_AFTER_PREFLIGHT'), uuid4())
        assert not sessions and not adapters and not list(d['receipts'].iterdir())
        assert _rows(d, R) == _rows(d, F) == []


def test_e_same_cluster_wrong_database_cannot_satisfy_runtime_readiness(offline_deployment):
    from feasibility.apple_ingestion.db import create_db_engine
    d = offline_deployment
    _enable(d)
    other_name = 'apple_phase_a_e_other_' + uuid4().hex[:12]
    bootstrap = create_db_engine(d['admin'].url.set(database='apple_phase_a_test'))
    other_owner = other_runtime = None
    try:
        with bootstrap.connect().execution_options(isolation_level='AUTOCOMMIT') as connection:
            connection.exec_driver_sql(f'CREATE DATABASE "{other_name}" OWNER "{d["names"]["owner"]}"')
        environment = dict(d['environment'])
        for role in ('owner', 'runtime', 'report'):
            environment[getattr(d['config'].database, f'{role}_url_env')] = d['admin'].url.set(
                database=other_name, username=d['names'][role]).render_as_string(hide_password=False)
        other_owner = deployment_engine(d['config'], 'owner', environ=environment)
        other_runtime = deployment_engine(d['config'], 'runtime', environ=environment)
        with other_owner.begin() as connection:
            initialize_database(connection, d['config'], execute=True)
            grant_permissions(connection, d['config'], execute=True)
        # Identical role names, UTC, table names and migration/seed contract in
        # another database must not validate a collector for the audited DB.
        with d['engines']['owner'].connect() as audit, other_runtime.connect() as runtime:
            report = preflight(audit, d['config'], for_live=True, environ=d['environment'], runtime_connection=runtime)
            assert not report['live_ready'] and not report['runtime_login_verified']
            assert 'ACTUAL_RUNTIME_LOGIN_REQUIRED' in report['blockers']
        clock = OfflineClock()
        factory, sessions, adapters = _factory(d, clock)
        with pytest.raises(ControllerError, match='LIVE_DEPLOYMENT_DATABASE_MISMATCH'):
            with _prepare(d, LiveExecutionPolicy(d['approval'], d['receipts']), clock, factory, runtime=other_runtime):
                pytest.fail('wrong database prepared a collector')
        assert not sessions and not adapters and not list(d['receipts'].iterdir())
        assert _rows(d, R) == _rows(d, F) == []
        with other_owner.connect() as connection:
            assert connection.scalar(text('SELECT count(*) FROM collection_run')) == 0
    finally:
        for engine in (other_runtime, other_owner):
            if engine is not None:
                engine.dispose()
        with bootstrap.connect().execution_options(isolation_level='AUTOCOMMIT') as connection:
            connection.exec_driver_sql(f'DROP DATABASE IF EXISTS "{other_name}" WITH (FORCE)')
        bootstrap.dispose()

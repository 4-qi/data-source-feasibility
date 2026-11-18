"""Bounded experimental operator entry; inert until explicitly enabled.

The existing Windows scheduler supplies timers. This entry never schedules itself,
retries a slot, changes production policy or writes the original pilot database.
"""
import argparse
from contextlib import contextmanager
from dataclasses import replace
from datetime import datetime, timezone
from decimal import Decimal
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import time
from uuid import UUID

import requests
from sqlalchemy import text
from sqlalchemy.engine import make_url

from .contracts import ConfigSnapshot, IngestionConfig, RunMode
from .coverage_comparison import compare
from .coverage_runner import APP, CoverageError, FixedDepthRunner
from .coverage_schedule import StudyStore, save_json
from .deployment import load_config, deployment_engine, preflight
from .live import _CheckedSession
from .models import Base
from .normalizer import HASH_CONTRACT_VERSION
from .parser import PARSER_VERSION
from .recovery import DiagnosticSpool
from .reporting import integrity_report, run_report
from .transport import BoundedTransport

PRIVATE = Path.home() / '.config/data-source-feasibility'
STATE = Path.home() / '.local/state/data-source-feasibility'


def environments(config, database):
    """Reuse private credentials, but rebind every role to one isolated database."""
    if not re.fullmatch(r'apple_coverage_main_[a-z0-9_]+', database):
        raise CoverageError('EXPERIMENT_DATABASE_REQUIRED')
    original = json.loads((PRIVATE / 'connection.env.json').read_text())
    isolated = dict(original)
    for name in (config.database.owner_url_env, config.database.runtime_url_env,
                 config.database.report_url_env):
        url = make_url(original[name])
        if url.database != 'apple_ingestion':
            raise CoverageError('PILOT_ENDPOINT_MISMATCH')
        isolated[name] = url.set(database=database).render_as_string(hide_password=False)
    return original, isolated


def pilot_digest(engine):
    digest = hashlib.sha256()
    counts = {}
    def encode(value):
        if isinstance(value, (bytes, memoryview)):
            return bytes(value).hex()
        if isinstance(value, (datetime, UUID, Decimal)):
            return str(value)
        raise TypeError
    with engine.connect() as connection:
        connection.exec_driver_sql('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
        if connection.scalar(text('SELECT current_database()')) != 'apple_ingestion':
            raise CoverageError('PILOT_ENDPOINT_MISMATCH')
        for table in sorted(Base.metadata.tables):
            order = 'run_id,review_id' if table == 'review_observation' else 'id'
            rows = [list(row) for row in connection.execute(text('SELECT * FROM '+table+' ORDER BY '+order))]
            counts[table] = len(rows)
            digest.update(table.encode())
            digest.update(json.dumps(rows, default=encode, sort_keys=True,
                                     separators=(',', ':')).encode())
        if connection.scalar(text('SELECT count(*) FROM collection_target WHERE enabled')):
            raise CoverageError('ORIGINAL_PILOT_ENABLED')
    return {'sha256': digest.hexdigest(), 'counts': counts}


def clock_check(*, seconds=2.0, sleep=time.sleep, wall=time.time,
                mono=time.monotonic, raw=None):
    """Detect clock steps and WSL disciplined-clock drift; never adjust clocks."""
    raw = raw or (lambda: time.clock_gettime(time.CLOCK_MONOTONIC_RAW))
    before = wall(), mono(), raw()
    sleep(seconds)
    after = wall(), mono(), raw()
    wall_delta, mono_delta, raw_delta = (b-a for a,b in zip(before, after))
    valid = (raw_delta > 0 and abs(wall_delta-mono_delta) <= .05
             and abs(mono_delta-raw_delta) <= .02 + .01*raw_delta)
    return {'verified': valid, 'wall_seconds': wall_delta, 'monotonic_seconds': mono_delta,
            'raw_seconds': raw_delta, 'clock_adjusted': False}


@contextmanager
def existing_operator_lock():
    path = STATE / 'phase-f/scheduled-operator.lock'
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'w') as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise CoverageError('OTHER_COLLECTION_BUSY') from None
        yield


def verify(store, config, environment, *, require_disabled=False):
    manifest = store.verify_source()
    engines = {role: deployment_engine(config, role, environ=environment)
               for role in ('owner', 'runtime', 'report')}
    try:
        with engines['owner'].connect() as owner, engines['runtime'].connect() as runtime:
            if owner.scalar(text('SELECT current_database()')) != manifest['database']:
                raise CoverageError('EXPERIMENT_DATABASE_MISMATCH')
            result = preflight(owner, config, for_live=True, environ={**os.environ, **environment,
                               config.diagnostics.spool_path_env:str(store.directory/'diagnostics.jsonl')},
                               runtime_connection=runtime)
            if not result['operational_ready']:
                raise CoverageError('EXPERIMENT_DEPLOYMENT_NOT_READY')
            targets = owner.execute(text('SELECT a.source_application_id,t.enabled,t.max_pages,'
                't.max_http_requests,t.interval_hours FROM collection_target t '
                'JOIN application a ON a.id=t.application_id')).all()
            if any(enabled and source != APP for source, enabled, *_ in targets):
                raise CoverageError('OUT_OF_SCOPE_TARGET_ENABLED')
            if require_disabled and any(row[1] for row in targets):
                raise CoverageError('EXPERIMENT_TARGET_NOT_DISABLED')
            settings = next(row for row in targets if row[0] == APP)
            if tuple(settings[2:]) != (10,20,12):
                raise CoverageError('EXPERIMENT_SETTINGS_MISMATCH')
        with engines['report'].connect() as report:
            report.exec_driver_sql('SET TRANSACTION READ ONLY')
            integrity = integrity_report(report)
        if not integrity['ok']:
            raise CoverageError('EXPERIMENT_INTEGRITY_FAILED')
        return {'database': manifest['database'], 'roles_verified': True,
                'schema_tables': 7, 'operational_ready': True, 'integrity': integrity,
                'enabled': manifest['enabled'], 'clock': clock_check(),
                'real_http_performed': False}
    finally:
        for engine in engines.values():
            engine.dispose()


def target_state(engine, enabled):
    """Only the isolated Duolingo target can be enabled; other seven stay off."""
    with engine.begin() as connection:
        database = connection.scalar(text('SELECT current_database()'))
        if not database.startswith('apple_coverage_main_'):
            raise CoverageError('EXPERIMENT_DATABASE_MISMATCH')
        connection.execute(text('UPDATE collection_target SET enabled=:enabled WHERE application_id='
                                '(SELECT id FROM application WHERE source_application_id=:app)'),
                           {'enabled': enabled, 'app': APP})


def make_snapshot(owner, manifest):
    with owner.connect() as connection:
        row = connection.execute(text('SELECT a.id,t.id FROM application a JOIN collection_target t '
            'ON t.application_id=a.id WHERE a.source_application_id=:app'), {'app':APP}).one()
    return ConfigSnapshot(row[0], APP, row[1], 'coverage-sha256/'+manifest['source_sha256'],
                          PARSER_VERSION, run_mode=RunMode.LIVE,
                          access_decision_ref='experiment-scope/'+manifest['study_id'],
                          retention_policy_ref='long_term', hash_contract_version=HASH_CONTRACT_VERSION,
                          config=replace(IngestionConfig(), interval_hours=12,max_pages=10,max_http_requests=20))


def consolidate(store):
    manifest = store.load()
    observations = []
    for slot in manifest['slots']:
        path = store.directory / f"observation-{slot['index']}.json"
        item = json.loads(path.read_text()) if path.exists() else None
        verification_path = store.directory / f"verification-{slot['index']}.json"
        if item is not None:
            verification = json.loads(verification_path.read_text()) if verification_path.exists() else {}
            if not (verification.get('integrity', {}).get('ok')
                    and verification.get('original_pilot_unchanged') is True):
                item['verification_failed'] = True
        observations.append(item)
    result = compare(observations)
    result.update(study_id=manifest['study_id'], planned_slots=manifest['slots'],
                  verification_failures=[i for i,item in enumerate(observations)
                                         if item and item.get('verification_failed')],
                  requests_reserved=sum(slot['requests'] for slot in manifest['slots']))
    save_json(store.directory / 'comparison.json', result)
    rows = ['# Duolingo Coverage Experiment Results', '',
            'Fixed-depth windows and counterfactual production early stopping are reported separately.', '',
            '| Strategy | Planned pairs | Evaluable | Sufficient | Requests observed |',
            '| --- | ---: | ---: | ---: | ---: |']
    for name, arm in result['strategies'].items():
        rows.append(f"| {name} | {arm['planned_pairs']} | {arm['evaluable']} | {arm['sufficient']} | {arm['fixed_depth_requests_observed']} |")
    rows += ['', 'Observed ID overlap does not prove complete coverage. Missing or failed windows remain explicit.',
             'The companion comparison.json retains actual intervals, prefix validity, failures and replay results.', '']
    path = store.directory / 'technical-report.md'
    path.write_text('\n'.join(rows))
    path.chmod(0o600)
    return result


def operate(store, mode, *, session_factory=requests.Session):
    """Verify never constructs a session. Observe requires explicit enablement."""
    config = load_config(PRIVATE / 'deployment.json')
    manifest = store.verify_source()
    original, isolated = environments(config, manifest['database'])
    if mode == 'verify':
        result = verify(store, config, isolated, require_disabled=True)
        save_json(store.directory / 'entry-verification.json', result)
        return result
    if mode == 'observe':
        store.enabled()  # Reject disabled/out-of-window execution before any write-capable engine.
    with existing_operator_lock():
        owner = deployment_engine(config, 'owner', environ=isolated)
        runtime = deployment_engine(config, 'runtime', environ=isolated)
        report = deployment_engine(config, 'report', environ=isolated)
        pilot = deployment_engine(config, 'report', environ=original)
        session = None
        try:
            if mode == 'maintenance':
                state = store.maintenance()
                # The state lock proves no active invocation is being interrupted.
                target_state(owner, False)
                if state['slots'][-1]['status'] not in ('planned','running'):
                    consolidate(store)
                    store.retire()
                return {'maintenance': True, 'retired': store.load()['retired'], 'real_http_performed': False}
            store.enabled()
            verified = verify(store, config, isolated, require_disabled=True)
            if not verified['clock']['verified']:
                raise CoverageError('CLOCK_NOT_READY')
            before = pilot_digest(pilot)
            if before != json.loads((store.directory/'pilot-baseline.json').read_text()):
                raise CoverageError('PILOT_BASELINE_CHANGED')
            slot = store.reserve_slot()
            if slot is None:
                return {'no_due_slot': True, 'real_http_performed': False}
            index = slot['index']
            # Persist invocation before enablement/session construction. Never replay this slot.
            save_json(store.directory / f'invocation-{index}.json', slot, exclusive=True)
            snapshot = make_snapshot(owner, store.load())
            start_mono, start_raw = time.monotonic(), time.clock_gettime(time.CLOCK_MONOTONIC_RAW)
            def guard():
                value = store.enabled()
                if value['slots'][index]['status'] != 'running':
                    raise CoverageError('SLOT_NOT_RUNNING')
                drift = ((time.monotonic()-start_mono) -
                         (time.clock_gettime(time.CLOCK_MONOTONIC_RAW)-start_raw))
                if abs(drift) > .05 + .01*(time.monotonic()-start_mono):
                    raise CoverageError('CLOCK_DRIFT')
            target_state(owner, True)
            session = session_factory()
            transport = BoundedTransport(_CheckedSession(session, lambda url: guard()))
            runner = FixedDepthRunner(runtime, transport,
                DiagnosticSpool(store.directory / 'diagnostics.jsonl'), database=manifest['database'],
                guard=guard, reserve=lambda page,fmt:store.reserve_request(index,page,fmt),
                checkpoint=lambda output:save_json(store.directory/f'observation-{index}.json',output))
            output = runner.run(snapshot, UUID(slot['batch_id']), run_id=UUID(slot['run_id']))
            with report.connect() as connection:
                connection.exec_driver_sql('SET TRANSACTION READ ONLY')
                integrity = integrity_report(connection)
                summary = run_report(connection, UUID(slot['run_id']))
            after = pilot_digest(pilot)
            save_json(store.directory/f'verification-{index}.json',
                      {'integrity':integrity,'run':summary,'original_pilot_unchanged':after==before})
            if not integrity['ok'] or before != after:
                output.update(overall_status='verification_failed', verification_failed=True)
                save_json(store.directory/f'observation-{index}.json',output)
            store.finish(index,output)
            if index == 6:
                consolidate(store)
                store.retire()
            return {'slot':index,'run_id':output['run_id'],'status':output['overall_status'],
                    'requests':output['requests'],'retired':store.load()['retired']}
        except Exception:
            # An uncertain invocation is never automatically repeated.
            state = store.load()
            if mode == 'observe':
                state['hold'] = True
                store.save(state)
            raise
        finally:
            try:
                target_state(owner,False)
            finally:
                if session is not None:
                    session.close()
                for engine in (owner,runtime,report,pilot):
                    engine.dispose()


def operator_exit_status(mode, result):
    """Process success describes this operation, never just normal JSON output."""
    if mode == 'observe':
        if result.get('no_due_slot'):
            return 2
        return 0 if result.get('status') == 'succeeded' else 1
    if mode == 'verify':
        return 0 if (result.get('operational_ready') and result.get('clock', {}).get('verified')
                     and result.get('integrity', {}).get('ok')
                     and not result['integrity'].get('running_pending_attempt_count', 0)) else 1
    return 0 if result.get('maintenance') else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--state',required=True)
    parser.add_argument('mode',choices=('verify','observe','maintenance'))
    args = parser.parse_args()
    store = StudyStore(args.state)
    try:
        with store.locked():
            result = operate(store,args.mode)
        print(json.dumps(result, default=str))
        raise SystemExit(operator_exit_status(args.mode, result))
    except Exception as error:
        # Never print exception strings: connection/parser exceptions may carry private data.
        code = str(error) if type(error) is CoverageError else 'EXPERIMENT_OPERATOR_FAILED'
        print(json.dumps({'status':'blocked','code':code,'safe_error':type(error).__name__}))
        raise SystemExit(1)


if __name__ == '__main__':
    main()

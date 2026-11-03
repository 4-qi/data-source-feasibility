"""Session/crash recovery on real private PostgreSQL; safe disk-only diagnostics."""
from datetime import timedelta
import json
import os
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import event, insert, select, text, update

from feasibility.apple_ingestion.models import CollectionRun, FetchAttempt, ReviewObservation, ReviewVersion
from feasibility.apple_ingestion.recovery import (
    ApplicationBusy, DiagnosticSpool, RecoveryError, SessionLost, SpoolError,
    application_session, recover_interrupted, replay_spool,
)
from test_apple_ingestion_reconcile import NOW, frame, new_run, page, ready, record

R, F, O, V = (m.__table__ for m in (CollectionRun, FetchAttempt, ReviewObservation, ReviewVersion))
RECOVERED = NOW + timedelta(hours=1)


def read(engine, table):
    with engine.connect() as connection:
        return [dict(row) for row in connection.execute(select(table)).mappings()]


def intent(connection, run_id, number=1, **changes):
    values = dict(run_id=run_id, request_number=number, page_number=number, format='json',
                  attempt_number=1, started_at=NOW, parsing_status='pending', persistence_status='pending')
    values.update(changes)
    with connection.begin():
        return connection.scalar(insert(F).values(**values).returning(F.c.id))


def test_application_lock_competition_idle_lifetime_and_release(apple_database):
    engine = apple_database
    app, _ = frame(engine)
    with application_session(engine, app) as first:
        assert first.backend_pid > 0 and not first.connection.in_transaction()
        first.assert_alive()
        assert not first.connection.in_transaction()
        with pytest.raises(ApplicationBusy, match='APPLICATION_BUSY'):
            with application_session(engine, app):
                pytest.fail('competing session acquired the same application')
        first.assert_alive()
        with first.connection.begin():
            assert first.connection.scalar(text('SHOW lock_timeout')) == '5s'
            assert first.connection.scalar(text('SHOW statement_timeout')) == '10s'
    with application_session(engine, app) as next_owner:
        next_owner.assert_alive()


def test_context_preserves_body_exception_and_rolls_back_before_unlock(apple_database):
    app, _ = frame(apple_database)
    with pytest.raises(RuntimeError, match='SYNTHETIC_FAILURE'):
        with application_session(apple_database, app) as session:
            session.connection.execute(text('SELECT 1'))
            raise RuntimeError('SYNTHETIC_FAILURE')
    with application_session(apple_database, app) as owner:
        assert not owner.connection.in_transaction()


def test_backend_termination_is_detected_without_checkout_or_reconnect(apple_database):
    app, _ = frame(apple_database)
    with pytest.raises(SessionLost):
        with application_session(apple_database, app) as owner:
            with apple_database.begin() as killer:
                assert killer.scalar(text('SELECT pg_terminate_backend(:pid)'), {'pid': owner.backend_pid})
            checkouts = []
            def checkout(*_):
                checkouts.append(1)
            event.listen(apple_database, 'checkout', checkout)
            try:
                for _ in range(2):
                    with pytest.raises(SessionLost, match='APPLICATION_SESSION_LOST'):
                        owner.assert_alive()
                assert checkouts == []
            finally:
                event.remove(apple_database, 'checkout', checkout)
            raise SessionLost()
    with application_session(apple_database, app) as next_owner:
        next_owner.assert_alive()


def test_released_lock_is_detected_and_discarded(apple_database):
    from feasibility.apple_ingestion.reconcile import application_lock_key
    app, _ = frame(apple_database)
    with pytest.raises(SessionLost):
        with application_session(apple_database, app) as owner:
            with owner.connection.begin():
                owner.connection.execute(text('SELECT pg_advisory_unlock(:key)'), {'key': application_lock_key(app)})
            owner.assert_alive()


def test_recover_orphan_preserves_committed_page_and_resolves_attempts(apple_database):
    engine = apple_database
    app, target = frame(engine)
    other_app, other_target = frame(engine, 'other-app')
    with application_session(engine, other_app) as other:
        untouched = new_run(other.connection, other_app, other_target)
    with application_session(engine, app) as owner:
        run = new_run(owner.connection, app, target)
        committed = page(owner.connection, run, 1, [record()])
        pending = intent(owner.connection, run, 2)
        parsed, _ = ready(owner.connection, run, 3, [record('not-committed')])
        before = read(engine, F)[0]
    with application_session(engine, app) as recovery:
        assert recover_interrupted(recovery.connection, app, RECOVERED) == (run,)
        assert recover_interrupted(recovery.connection, app, RECOVERED) == ()
        assert not recovery.connection.in_transaction()
    attempts = {row['id']: row for row in read(engine, F)}
    assert attempts[committed.attempt_id] == before
    assert attempts[pending]['http_status'] is None
    assert attempts[pending]['parsing_status'] == 'not_attempted'
    assert attempts[pending]['persistence_status'] == 'not_applicable'
    assert attempts[pending]['finished_at'] == RECOVERED
    assert 'REQUEST_OUTCOME_UNKNOWN' in attempts[pending]['error_codes']
    assert attempts[parsed]['persistence_status'] == 'rolled_back'
    runs = {row['id']: row for row in read(engine, R)}
    assert (runs[run]['execution_status'], runs[run]['coverage_status']) == ('interrupted', 'indeterminate')
    assert runs[untouched]['execution_status'] == 'running'
    assert len(read(engine, O)) == len(read(engine, V)) == 1


def test_recovery_requires_owned_lock_and_valid_chronology(apple_database):
    app, target = frame(apple_database)
    with apple_database.connect() as connection:
        with pytest.raises(RecoveryError, match='APPLICATION_SESSION_LOCK_REQUIRED'):
            recover_interrupted(connection, app, RECOVERED)
    with application_session(apple_database, app) as owner:
        run = new_run(owner.connection, app, target)
        with pytest.raises(RecoveryError, match='RECOVERY_TIME_PRECEDES_RUN'):
            recover_interrupted(owner.connection, app, NOW - timedelta(seconds=1))
        assert read(apple_database, R)[0]['execution_status'] == 'running'
        with pytest.raises(RecoveryError, match='AWARE_RECOVERY_TIME_REQUIRED'):
            recover_interrupted(owner.connection, app, NOW.replace(tzinfo=None))


def test_spool_replay_is_attempt_idempotent_and_committed_marker_wins(apple_database, tmp_path):
    engine = apple_database
    app, target = frame(engine)
    spool = DiagnosticSpool(tmp_path / 'diagnostics.jsonl')
    assert spool.entries() == ()  # no file is normal before the first failure
    with application_session(engine, app) as owner:
        run = new_run(owner.connection, app, target)
        committed = page(owner.connection, run, 1, [record()])
        unknown = intent(owner.connection, run, 2)
        with owner.connection.begin():
            owner.connection.execute(update(F).where(F.c.id == unknown).values(anomalies=[
                {'code': 'EMPTY_PAGE', 'count': 1, 'page': i} for i in range(100)]))
        for attempt_id in (committed.attempt_id, unknown):
            spool.append(run, attempt_id, 'DB_UNAVAILABLE', 'persistence', NOW)
            spool.append(run, attempt_id, 'REQUEST_OUTCOME_UNKNOWN', 'http', NOW)
        spool.append(run, None, 'DB_UNAVAILABLE', 'finalize', NOW)
        assert replay_spool(owner.connection, app, spool, RECOVERED) == 3
        saved = read(engine, F)
        assert replay_spool(owner.connection, app, spool, RECOVERED) == 0
        assert saved == read(engine, F)
        assert not owner.connection.in_transaction()
        assert recover_interrupted(owner.connection, app, RECOVERED) == (run,)
    attempts = {row['id']: row for row in read(engine, F)}
    assert attempts[committed.attempt_id]['persistence_status'] == 'committed'
    assert attempts[committed.attempt_id]['parsing_status'] == 'succeeded'
    assert attempts[unknown]['persistence_status'] == 'not_applicable'
    assert attempts[unknown]['http_status'] is None
    assert len(attempts[unknown]['anomalies']) <= 100
    assert any(value['code'] == 'SPOOL_REPLAYED' for value in attempts[unknown]['anomalies'])
    assert len(read(engine, O)) == len(read(engine, V)) == 1
    assert len(spool.entries()) == 5  # retained for crash-safe repeated import


def test_spool_foreign_application_and_mismatched_attempt_are_not_imported(apple_database, tmp_path):
    app, target = frame(apple_database)
    other_app, _ = frame(apple_database, 'other')
    spool = DiagnosticSpool(tmp_path / 'diagnostics.jsonl')
    with application_session(apple_database, app) as owner:
        run = new_run(owner.connection, app, target)
        attempt_id = intent(owner.connection, run)
        spool.append(run, attempt_id, 'DB_UNAVAILABLE', 'persistence', NOW)
    with application_session(apple_database, other_app) as owner:
        assert replay_spool(owner.connection, other_app, spool, RECOVERED) == 0
    bad = DiagnosticSpool(tmp_path / 'bad.jsonl')
    bad.append(run, attempt_id + 1, 'DB_UNAVAILABLE', 'persistence', NOW)
    with application_session(apple_database, app) as owner:
        with pytest.raises(RecoveryError, match='SPOOL_ATTEMPT_RUN_MISMATCH'):
            replay_spool(owner.connection, app, bad, RECOVERED)
    assert read(apple_database, F)[0]['error_codes'] == []


def test_spool_contains_only_whitelisted_fields_0600_and_fsync(tmp_path, monkeypatch):
    path = tmp_path / 'diagnostic.jsonl'
    spool = DiagnosticSpool(path)
    synced = []
    real = os.fsync
    monkeypatch.setattr(os, 'fsync', lambda fd: synced.append(fd) or real(fd))
    run = uuid4()
    spool.append(run, 5, 'DB_UNAVAILABLE', 'persistence', NOW)
    assert len(synced) == 2 and path.stat().st_mode & 0o777 == 0o600
    value, = spool.entries()
    assert set(value) == {'run_id', 'attempt_id', 'code', 'stage', 'at'}
    assert value == dict(run_id=str(run), attempt_id=5, code='DB_UNAVAILABLE', stage='persistence',
                         at='2026-11-03T12:00:00.000000Z')


@pytest.mark.parametrize('change', [dict(run_id='PRIVATE'), dict(attempt_id=True), dict(attempt_id=0),
                                    dict(code='PRIVATE body'), dict(stage='PRIVATE title'), dict(at=NOW.replace(tzinfo=None))])
def test_spool_rejects_unsanitized_input_before_writing(tmp_path, change):
    path = tmp_path / 'diagnostic.jsonl'
    values = dict(run_id=uuid4(), attempt_id=1, code='DB_UNAVAILABLE', stage='persistence', at=NOW) | change
    with pytest.raises(SpoolError) as caught:
        DiagnosticSpool(path).append(**values)
    assert 'PRIVATE' not in str(caught.value) and not path.exists()


def test_spool_rejects_repo_symlinks_hardlinks_insecure_mode_fifo_and_corruption(tmp_path):
    root = Path(__file__).resolve().parents[1]
    with pytest.raises(SpoolError):
        DiagnosticSpool(root / 'private.jsonl').append(uuid4(), 1, 'DB_UNAVAILABLE', 'persistence', NOW)
    real = tmp_path / 'real.jsonl'
    DiagnosticSpool(real).append(uuid4(), 1, 'DB_UNAVAILABLE', 'persistence', NOW)
    link = tmp_path / 'linked.jsonl'
    link.symlink_to(real)
    with pytest.raises(SpoolError):
        DiagnosticSpool(link).entries()
    directory = tmp_path / 'dirlink'
    directory.symlink_to(tmp_path, target_is_directory=True)
    with pytest.raises(SpoolError):
        DiagnosticSpool(directory / 'real.jsonl').entries()
    hardlink = tmp_path / 'hardlink.jsonl'
    os.link(real, hardlink)
    with pytest.raises(SpoolError):
        DiagnosticSpool(hardlink).entries()
    hardlink.unlink()
    real.chmod(0o644)
    with pytest.raises(SpoolError):
        DiagnosticSpool(real).entries()
    fifo = tmp_path / 'fifo'
    os.mkfifo(fifo, 0o600)
    with pytest.raises(SpoolError):
        DiagnosticSpool(fifo).append(uuid4(), 1, 'DB_UNAVAILABLE', 'persistence', NOW)
    real.chmod(0o600)
    for corrupt in (b'{"PRIVATE":true}\n', b'PRIVATE', b'{"run_id":null,"run_id":"PRIVATE"}\n'):
        real.write_bytes(corrupt)
        with pytest.raises(SpoolError) as caught:
            DiagnosticSpool(real).entries()
        assert 'PRIVATE' not in str(caught.value)


def test_total_spool_storage_failure_is_explicit(tmp_path, monkeypatch):
    def fail(*_):
        raise OSError('PRIVATE disk failure')
    monkeypatch.setattr(os, 'fsync', fail)
    with pytest.raises(SpoolError, match='DIAGNOSTIC_SPOOL_UNAVAILABLE'):
        DiagnosticSpool(tmp_path / 'diagnostics.jsonl').append(uuid4(), 1, 'DB_UNAVAILABLE', 'persistence', NOW)


def test_replay_imports_new_events_after_prior_marker_without_reimporting_old(apple_database, tmp_path):
    app, target = frame(apple_database)
    spool = DiagnosticSpool(tmp_path / 'events.jsonl')
    with application_session(apple_database, app) as owner:
        run = new_run(owner.connection, app, target)
        attempt_id = intent(owner.connection, run)
        for identity in (attempt_id, None):
            spool.append(run, identity, 'DB_UNAVAILABLE', 'run_intent', NOW)
        assert replay_spool(owner.connection, app, spool, RECOVERED) == 2
        first = read(apple_database, F)[0]
        for identity in (attempt_id, None):
            spool.append(run, identity, 'DB_UNAVAILABLE', 'run_intent', NOW)  # duplicate line
            spool.append(run, identity, 'REQUEST_OUTCOME_UNKNOWN', 'after_page_commit', NOW + timedelta(seconds=1))
        assert replay_spool(owner.connection, app, spool, RECOVERED) == 2
        after = read(apple_database, F)[0]
        marker = next(item for item in after['anomalies'] if item['code'] == 'SPOOL_REPLAYED')
        assert len(marker['event_keys']) == 2 and all(len(key) == 64 for key in marker['event_keys'])
        assert after['error_codes'] == ['DB_UNAVAILABLE', 'REQUEST_OUTCOME_UNKNOWN']
        assert first['finished_at'] == after['finished_at'] == RECOVERED
        assert replay_spool(owner.connection, app, spool, RECOVERED) == 0
        assert read(apple_database, F)[0] == after


def test_replay_ledger_capacity_fails_without_losing_or_acknowledging_new_events(apple_database, tmp_path):
    app, target = frame(apple_database)
    spool = DiagnosticSpool(tmp_path / 'capacity.jsonl')
    with application_session(apple_database, app) as owner:
        run = new_run(owner.connection, app, target)
        attempt_id = intent(owner.connection, run)
        for second in range(100):
            spool.append(run, attempt_id, 'DB_UNAVAILABLE', 'page_commit', NOW + timedelta(seconds=second))
        assert replay_spool(owner.connection, app, spool, RECOVERED) == 1
        before = read(apple_database, F)[0]
        spool.append(run, attempt_id, 'DB_UNAVAILABLE', 'page_commit', NOW + timedelta(seconds=100))
        with pytest.raises(RecoveryError, match='SPOOL_EVENT_CAPACITY'):
            replay_spool(owner.connection, app, spool, RECOVERED)
        assert read(apple_database, F)[0] == before
        assert len(spool.entries()) == 101


def test_pool_return_restores_timeouts_and_never_leaves_application_lock(apple_database):
    app, _ = frame(apple_database)
    with apple_database.begin() as connection:
        connection.execute(text("SELECT set_config('lock_timeout','1234ms',false)"))
        connection.execute(text("SELECT set_config('statement_timeout','2345ms',false)"))
        pid = connection.scalar(text('SELECT pg_backend_pid()'))
    with application_session(apple_database, app) as owner:
        assert owner.backend_pid == pid
    with apple_database.begin() as connection:
        assert connection.scalar(text('SELECT pg_backend_pid()')) == pid
        assert connection.scalar(text('SHOW lock_timeout')) == '1234ms'
        assert connection.scalar(text('SHOW statement_timeout')) == '2345ms'
        assert connection.scalar(text("SELECT count(*) FROM pg_locks WHERE pid=pg_backend_pid() AND locktype='advisory'")) == 0


def test_outage_spool_replay_preserves_unknown_request_and_known_metadata_separately(apple_database, tmp_path):
    app, target = frame(apple_database)
    spool = DiagnosticSpool(tmp_path / 'outage.jsonl')
    with application_session(apple_database, app) as owner:
        run = new_run(owner.connection, app, target)
        unknown = intent(owner.connection, run)
        known = intent(owner.connection, run, 2, http_status=200, finished_at=NOW + timedelta(seconds=2),
                       parsing_status='succeeded', entry_count=1)
        for attempt_id in (unknown, known):
            spool.append(run, attempt_id, 'APPLICATION_SESSION_LOST', 'response_metadata', NOW + timedelta(seconds=3))
    with application_session(apple_database, app) as owner:
        assert replay_spool(owner.connection, app, spool, RECOVERED) == 2
        assert recover_interrupted(owner.connection, app, RECOVERED) == (run,)
        assert replay_spool(owner.connection, app, spool, RECOVERED) == 0
    rows = {row['id']: row for row in read(apple_database, F)}
    unknown_row, known_row = rows[unknown], rows[known]
    assert set(unknown_row['error_codes']) == {'APPLICATION_SESSION_LOST', 'REQUEST_OUTCOME_UNKNOWN'}
    assert unknown_row['http_status'] is None
    assert unknown_row['finished_at'] == RECOVERED
    assert any(item['code'] == 'REQUEST_OUTCOME_UNKNOWN' and item['completion_time_unknown'] is True
               for item in unknown_row['anomalies'])
    assert known_row['error_codes'] == ['APPLICATION_SESSION_LOST']
    assert known_row['http_status'] == 200
    assert known_row['finished_at'] == NOW + timedelta(seconds=2)
    assert known_row['parsing_status'] == 'succeeded' and known_row['persistence_status'] == 'rolled_back'
    assert not any(item['code'] == 'REQUEST_OUTCOME_UNKNOWN' for item in known_row['anomalies'])


def test_cleanup_rolls_back_raw_transaction_after_sqlalchemy_commit_hook_failure(apple_database):
    from psycopg.pq import TransactionStatus
    app, _ = frame(apple_database)
    with pytest.raises(RuntimeError, match='SYNTHETIC_COMMIT_FAILURE'):
        with application_session(apple_database, app) as owner:
            connection = owner.connection
            def fail_commit(_):
                raise RuntimeError('SYNTHETIC_COMMIT_FAILURE')
            event.listen(connection, 'commit', fail_commit)
            try:
                try:
                    with connection.begin():
                        connection.execute(text("UPDATE application SET name='must rollback' WHERE id=:app"), {'app': app})
                except RuntimeError:
                    assert not connection.in_transaction()
                    assert connection.connection.driver_connection.info.transaction_status == TransactionStatus.INTRANS
                    raise
            finally:
                event.remove(connection, 'commit', fail_commit)
    with apple_database.connect() as connection:
        assert connection.scalar(text('SELECT name FROM application WHERE id=:app'), {'app': app}) == 'Synthetic'
    with application_session(apple_database, app) as owner:
        owner.assert_alive()


def test_assert_alive_refuses_untracked_driver_transaction_without_querying_or_committing(apple_database):
    app, _ = frame(apple_database)
    queries = []
    with pytest.raises(SessionLost):
        with application_session(apple_database, app) as owner:
            driver = owner.connection.connection.driver_connection
            driver.execute("UPDATE application SET name='must rollback' WHERE id=%s", (app,))
            assert not owner.connection.in_transaction()
            def observed(*_):
                queries.append(1)
            event.listen(owner.connection, 'before_cursor_execute', observed)
            try:
                owner.assert_alive()
            finally:
                event.remove(owner.connection, 'before_cursor_execute', observed)
                assert queries == []
    with apple_database.connect() as connection:
        assert connection.scalar(text('SELECT name FROM application WHERE id=:app'), {'app': app}) == 'Synthetic'

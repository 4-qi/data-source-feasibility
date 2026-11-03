"""Real disposable PostgreSQL page-state tests with synthetic full text only."""
from contextlib import contextmanager
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import json
from uuid import uuid4

import pytest

pytest.importorskip("sqlalchemy")
pytest.importorskip("psycopg")
from sqlalchemy import func, insert, select, text, update

from feasibility.apple_ingestion.contracts import ReviewRecord
from feasibility.apple_ingestion.models import Application, CollectionTarget, CollectionRun, FetchAttempt, Review, ReviewObservation, ReviewVersion
from feasibility.apple_ingestion.reconcile import (
    ReconciliationError, ReconciliationPreconditionError,
    application_lock_key, persist_page,
)

A, T, R, F, I, V, O = (model.__table__ for model in (
    Application, CollectionTarget, CollectionRun, FetchAttempt, Review, ReviewVersion, ReviewObservation))
NOW = datetime(2026, 11, 3, 12, tzinfo=timezone.utc)


def record(source_id="000opaque-review", body="synthetic A", **changes):
    return ReviewRecord(source_id, changes.pop("title", "synthetic title"), body,
                        changes.pop("rating", 4), **changes)


def frame(engine, source_id="000opaque-app"):
    with engine.begin() as c:
        app = c.scalar(insert(A).values(source="apple_app_store", source_application_id=source_id,
            name="Synthetic", analytical_category="education").returning(A.c.id))
        target = c.scalar(insert(T).values(application_id=app, storefront="us", sort_by="mostrecent").returning(T.c.id))
    return app, target


def new_run(c, app, target):
    run_id = uuid4()
    with c.begin():
        c.execute(insert(R).values(id=run_id, application_id=app, target_id=target, batch_id=uuid4(),
            started_at=NOW, execution_status="running", coverage_status="pending", config_snapshot={}))
    return run_id


def finish(c, run_id):
    with c.begin():
        c.execute(update(R).where(R.c.id == run_id).values(execution_status="succeeded", coverage_status="baseline",
            finished_at=NOW + timedelta(hours=1), stop_reason="synthetic_fixture"))


def ready(c, run_id, page, records, *, request=None, format="json"):
    observed = NOW + timedelta(seconds=page)
    with c.begin():
        attempt = c.scalar(insert(F).values(run_id=run_id, request_number=request or page, page_number=page,
            format=format, attempt_number=1, started_at=NOW, finished_at=observed,
            parsing_status="succeeded", persistence_status="pending", entry_count=len(records)).returning(F.c.id))
    return attempt, observed


def page(c, run_id, page_number, records, **kwargs):
    attempt, instant = ready(c, run_id, page_number, records)
    return persist_page(c, run_id, attempt, records, instant, **kwargs)


@contextmanager
def locked(engine, app):
    with engine.connect() as c:
        c.execute(text("SELECT pg_advisory_lock(:key)"), {"key": application_lock_key(app)})
        c.commit()
        try:
            yield c
        finally:
            c.rollback()
            c.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": application_lock_key(app)})
            c.commit()


def rows(engine, table):
    with engine.connect() as c:
        return [dict(row) for row in c.execute(select(table)).mappings()]


def diagnostic_totals(anomalies):
    return next(item for item in anomalies if item["code"] == "DIAGNOSTIC_TOTALS")


def test_new_unchanged_changed_and_historical_return_are_four_run_observations(apple_database):
    engine = apple_database
    app, target = frame(engine)
    with locked(engine, app) as c:
        actions = []
        runs = []
        for body in ("synthetic A", "synthetic A", "synthetic B", "synthetic A"):
            rid = new_run(c, app, target)
            runs.append(rid)
            actions.append(page(c, rid, 1, (record(body=body),)))
            finish(c, rid)
    assert [(r.new_count, r.unchanged_count, r.changed_count) for r in actions] == [(1,0,0),(0,1,0),(0,0,1),(0,0,1)]
    versions = sorted(rows(engine, V), key=lambda row: row["version_number"])
    assert [v["body"] for v in versions] == ["synthetic A", "synthetic B", "synthetic A"]
    assert [v["version_number"] for v in versions] == [1,2,3]
    assert len(rows(engine, O)) == 4
    assert rows(engine, I)[0]["current_version_id"] == versions[-1]["id"]
    assert versions[0]["content_hash"] == versions[2]["content_hash"]


def test_metadata_only_changes_create_new_version(apple_database):
    engine = apple_database
    app, target = frame(engine)
    with locked(engine, app) as c:
        rid = new_run(c, app, target)
        page(c, rid, 1, (record(rating=4),))
        finish(c, rid)
        rid = new_run(c, app, target)
        result = page(c, rid, 1, (record(rating=5),))
    versions = rows(engine, V)
    assert result.changed_count == 1
    assert len(versions) == 2
    assert versions[0]["content_hash"] == versions[1]["content_hash"]
    assert versions[0]["metadata_hash"] != versions[1]["metadata_hash"]


def test_canonical_equivalence_keeps_original_full_unicode_text(apple_database):
    engine = apple_database
    app, target = frame(engine)
    original = record(body=("e\u0301\r\n🙂汉字\r" * 10000), title=None,
                      application_version="e\u0301", source_updated_at=NOW)
    equivalent = replace(original, body=original.body.replace("e\u0301", "é").replace("\r\n", "\n").replace("\r", "\n"),
                         application_version="é", source_updated_at=NOW.astimezone(timezone(timedelta(hours=3))))
    with locked(engine, app) as c:
        rid = new_run(c, app, target)
        page(c, rid, 1, (original,))
        finish(c, rid)
        rid = new_run(c, app, target)
        result = page(c, rid, 1, (equivalent,))
    assert result.unchanged_count == 1
    stored = rows(engine, V)
    assert len(stored) == 1 and stored[0]["body"] == original.body
    assert stored[0]["title"] is None


def test_same_page_duplicates_and_conflicts_keep_first_snapshot_and_position(apple_database):
    engine = apple_database
    app, target = frame(engine)
    with locked(engine, app) as c:
        rid = new_run(c, app, target)
        result = page(c, rid, 1, (record(), record(), record(body="synthetic alternate"), record()))
    assert (result.entry_count, result.distinct_review_count, result.new_count) == (4,1,1)
    assert (result.duplicate_count, result.same_page_duplicate_count, result.cross_page_duplicate_count, result.conflict_count) == (3,3,0,1)
    observation = rows(engine, O)[0]
    assert (observation["occurrence_count"], observation["conflict_count"], observation["first_observed_position"]) == (4,1,1)
    assert len(rows(engine, V)) == 1 and rows(engine, V)[0]["body"] == "synthetic A"
    summary = diagnostic_totals(rows(engine, F)[0]["anomalies"])
    assert summary["counts"]["INTRA_RUN_CONFLICT"] == 1
    safe = json.dumps(rows(engine, R)[0]["anomalies"])
    assert "synthetic alternate" not in safe and "000opaque-review" not in safe


def test_cross_page_conflicts_and_duplicate_only_metrics_survive_commit(apple_database):
    engine = apple_database
    app, target = frame(engine)
    with locked(engine, app) as c:
        rid = new_run(c, app, target)
        first = page(c, rid, 1, (record(),))
        second = page(c, rid, 2, (record(), record(body="synthetic B"), record()))
    assert first.new_count == 1
    assert second.duplicate_only and second.has_conflicts
    assert (second.duplicate_count, second.cross_page_duplicate_count, second.same_page_duplicate_count) == (3,3,2)
    assert rows(engine, O)[0]["occurrence_count"] == 4
    assert rows(engine, O)[0]["conflict_count"] == 1
    assert len(rows(engine, V)) == 1
    attempt = next(row for row in rows(engine, F) if row["page_number"] == 2)
    assert any(item["code"] == "PAGE_DUPLICATE_ONLY" for item in attempt["anomalies"])
    assert next(item for item in attempt["anomalies"] if item["code"] == "PAGE_SUMMARY")["cross_page_duplicate_count"] == 3
    run_summary = next(item for item in rows(engine, R)[0]["anomalies"] if item["code"] == "RECONCILIATION_SUMMARY")
    assert run_summary["entry_count"] == 4 and run_summary["distinct_review_count"] == 1


def test_mixed_page_duplicates_are_warning_not_duplicate_only(apple_database):
    engine = apple_database
    app, target = frame(engine)
    with locked(engine, app) as c:
        rid = new_run(c, app, target)
        page(c, rid, 1, (record(),))
        result = page(c, rid, 2, (record(), record("new-id")))
    assert result.cross_page_duplicate_count == 1 and result.new_count == 1
    assert not result.duplicate_only and not result.has_conflicts
    assert len(rows(engine, O)) == 2


def test_committed_page_replay_returns_durable_summary_without_any_counts_or_text_changes(apple_database):
    engine = apple_database
    app, target = frame(engine)
    with locked(engine, app) as c:
        rid = new_run(c, app, target)
        attempt, instant = ready(c, rid, 1, (record(), record()))
        result = persist_page(c, rid, attempt, (record(), record()), instant)
        before = {table.name: rows(engine, table) for table in (I,V,O,F,R)}
        # Caller data are never applied when the durable selected marker exists.
        replay = persist_page(c, rid, attempt, (record(body="synthetic ignored"),), instant)
        assert replay == replace(result, replayed=True)
        assert before == {table.name: rows(engine, table) for table in (I,V,O,F,R)}
        finish(c, rid)
        assert persist_page(c, rid, attempt, (), instant).replayed


def test_empty_page_commits_selected_marker_without_deleting_or_observing_old_ids(apple_database):
    engine = apple_database
    app, target = frame(engine)
    with locked(engine, app) as c:
        rid = new_run(c, app, target)
        page(c, rid, 1, (record(),))
        finish(c, rid)
        untouched = {table.name: rows(engine, table) for table in (I,V)}
        rid = new_run(c, app, target)
        result = page(c, rid, 1, ())
    assert result.entry_count == 0 and not result.duplicate_only
    assert untouched == {table.name: rows(engine, table) for table in (I,V)}
    assert len(rows(engine, O)) == 1
    empty = next(row for row in rows(engine, F) if row["run_id"] == rid)
    assert empty["persistence_status"] == "committed"
    assert any(item["code"] == "EMPTY_PAGE" for item in empty["anomalies"])


@pytest.mark.parametrize("stage", ["after_identity_insert", "after_version_insert", "after_observation_upsert", "after_attempt_update"])
def test_fault_rolls_back_whole_page_preserves_prior_page_and_records_safe_diagnostics(apple_database, stage, caplog):
    engine = apple_database
    app, target = frame(engine)
    with locked(engine, app) as c:
        prior = new_run(c, app, target)
        page(c, prior, 1, (record("existing"),))
        finish(c, prior)
        rid = new_run(c, app, target)
        page(c, rid, 1, (record("prior-page"),))
        baseline = {table.name: rows(engine, table) for table in (I,V,O)}
        records = (record("existing", body="synthetic changed"), record("new-id"))
        attempt, instant = ready(c, rid, 2, records)
        def fail(current):
            if current == stage:
                raise RuntimeError("PRIVATE-INJECTED-TEXT")
        with pytest.raises(ReconciliationError) as caught:
            persist_page(c, rid, attempt, records, instant, fault_hook=fail)
        assert caught.value.code == "PAGE_PERSISTENCE_FAILED" and caught.value.diagnostics_persisted
        assert "PRIVATE-INJECTED-TEXT" not in str(caught.value)
        assert "PRIVATE-INJECTED-TEXT" not in caplog.text
        assert baseline == {table.name: rows(engine, table) for table in (I,V,O)}
        failed = next(row for row in rows(engine, F) if row["id"] == attempt)
        assert failed["persistence_status"] == "rolled_back" and failed["error_codes"] == ["PAGE_PERSISTENCE_FAILED"]
        assert "PRIVATE-INJECTED-TEXT" not in json.dumps(failed["anomalies"])
        # No automatic retry occurs. An explicit synthetic test retry commits once.
        retried = persist_page(c, rid, attempt, records, instant)
        assert retried.changed_count == 1 and retried.new_count == 1
        assert persist_page(c, rid, attempt, records, instant).replayed


def test_deferred_commit_constraint_failure_rolls_back_all_page_writes(apple_database):
    engine = apple_database
    app, target = frame(engine)
    with locked(engine, app) as c:
        rid = new_run(c, app, target)
        attempt, instant = ready(c, rid, 1, (record(),))
        def break_pointer(stage):
            if stage == "after_attempt_update":
                c.execute(update(I).values(current_version_id=9223372036854775800))
        with pytest.raises(ReconciliationError) as caught:
            persist_page(c, rid, attempt, (record(),), instant, fault_hook=break_pointer)
        assert caught.value.code == "DB_CONSTRAINT" and caught.value.sqlstate == "23503"
        assert caught.value.diagnostics_persisted
    assert rows(engine, I) == rows(engine, V) == rows(engine, O) == []
    assert rows(engine, F)[0]["persistence_status"] == "rolled_back"


def test_bounded_conflict_details_keep_exact_totals_on_attempt_and_run(apple_database):
    engine = apple_database
    app, target = frame(engine)
    records = (record(),) + tuple(record(body=f"synthetic conflict {n}") for n in range(130))
    with locked(engine, app) as c:
        rid = new_run(c, app, target)
        result = page(c, rid, 1, records)
        page(c, rid, 2, (record(body="synthetic later conflict"),))
    assert result.conflict_count == 130
    assert rows(engine, O)[0]["conflict_count"] == 131
    for row in rows(engine, F):
        assert len(row["anomalies"]) <= 100
    first = next(row for row in rows(engine, F) if row["page_number"] == 1)
    totals = diagnostic_totals(first["anomalies"])
    assert totals["detail_truncated"] and totals["counts"]["INTRA_RUN_CONFLICT"] == 130
    run_totals = diagnostic_totals(rows(engine, R)[0]["anomalies"])
    assert run_totals["detail_truncated"] and run_totals["counts"]["INTRA_RUN_CONFLICT"] == 131
    assert run_totals["counts"]["CROSS_PAGE_DUPLICATE"] == 1


def test_opaque_id_is_app_scoped_and_full_title_changes_are_versioned(apple_database):
    engine = apple_database
    first_app, first_target = frame(engine, "app-one")
    second_app, second_target = frame(engine, "app-two")
    for app, target in ((first_app, first_target), (second_app, second_target)):
        with locked(engine, app) as c:
            rid = new_run(c, app, target)
            page(c, rid, 1, (record("000opaque-review"),))
            finish(c, rid)
    with locked(engine, first_app) as c:
        rid = new_run(c, first_app, first_target)
        changed = page(c, rid, 1, (record(title="synthetic long title " * 2000),))
    assert len(rows(engine, I)) == 2 and changed.changed_count == 1
    assert max(len(row["title"]) for row in rows(engine, V)) == len("synthetic long title " * 2000)


def test_comparison_checks_fields_even_when_hashes_collide(apple_database, monkeypatch):
    from feasibility.apple_ingestion import reconcile
    monkeypatch.setattr(reconcile, "fingerprint", lambda record: (b"a"*32, b"b"*32))
    engine = apple_database
    app, target = frame(engine)
    with locked(engine, app) as c:
        rid = new_run(c, app, target)
        page(c, rid, 1, (record(),))
        finish(c, rid)
        rid = new_run(c, app, target)
        result = page(c, rid, 1, (record(body="synthetic changed despite collision"),))
    assert result.changed_count == 1 and len(rows(engine, V)) == 2


def test_wrong_connection_lock_or_active_transaction_fails_without_attempt_mutation(apple_database):
    engine = apple_database
    app, target = frame(engine)
    with engine.connect() as c:
        rid = new_run(c, app, target)
        attempt, instant = ready(c, rid, 1, (record(),))
        with pytest.raises(ReconciliationPreconditionError, match="APPLICATION_SESSION_LOCK_REQUIRED"):
            persist_page(c, rid, attempt, (record(),), instant)
        with c.begin():
            with pytest.raises(ReconciliationPreconditionError, match="PAGE_REQUIRES_IDLE_CONNECTION"):
                persist_page(c, rid, attempt, (record(),), instant)
    with locked(engine, app) as owner:
        with engine.connect() as other:
            assert not other.scalar(text("SELECT pg_try_advisory_lock(:key)"), {"key": application_lock_key(app)})
            other.commit()
            with pytest.raises(ReconciliationPreconditionError, match="APPLICATION_SESSION_LOCK_REQUIRED"):
                persist_page(other, rid, attempt, (record(),), instant)
        result = persist_page(owner, rid, attempt, (record(),), instant)
        assert result.new_count == 1 and not result.replayed
    assert rows(engine, O)[0]["occurrence_count"] == 1


def test_wrong_run_attempt_and_unparsed_attempt_are_rejected(apple_database):
    engine = apple_database
    app, target = frame(engine)
    with locked(engine, app) as c:
        rid = new_run(c, app, target)
        attempt, instant = ready(c, rid, 1, (record(),))
        finish(c, rid)
        next_run = new_run(c, app, target)
        with pytest.raises(ReconciliationPreconditionError, match="ATTEMPT_RUN_MISMATCH"):
            persist_page(c, next_run, attempt, (record(),), instant)
        other_attempt, instant = ready(c, next_run, 1, (record(),))
        with c.begin():
            c.execute(update(F).where(F.c.id == other_attempt).values(parsing_status="pending"))
        with pytest.raises(ReconciliationPreconditionError, match="ATTEMPT_NOT_READY_FOR_PAGE"):
            persist_page(c, next_run, other_attempt, (record(),), instant)
    assert rows(engine, I) == []


def test_same_run_duplicate_uses_observed_version_even_if_pointer_is_changed_externally(apple_database):
    # Simulate an unsupported maintenance change to prove the comparison anchor
    # remains the run's observation rather than whatever current now points to.
    engine = apple_database
    app, target = frame(engine)
    with locked(engine, app) as c:
        rid = new_run(c, app, target)
        page(c, rid, 1, (record(),))
        with c.begin():
            original = c.execute(select(V)).mappings().one()
            copied = {key:value for key,value in original.items() if key != "id"}
            copied.update(version_number=2, body="synthetic external current")
            newer = c.scalar(insert(V).values(**copied).returning(V.c.id))
            c.execute(update(I).values(current_version_id=newer))
        result = page(c, rid, 2, (record(),))
    assert result.conflict_count == 0 and result.duplicate_count == 1
    assert rows(engine, I)[0]["current_version_id"] == newer
    assert rows(engine, O)[0]["observed_version_id"] == original["id"]


def test_full_page_validation_occurs_before_connection_access_and_hides_bad_text():
    valid = record()
    invalid = replace(valid)
    object.__setattr__(invalid, "rating", 9)
    with pytest.raises(ReconciliationPreconditionError, match="PAGE_VALIDATION_FAILED"):
        persist_page(object(), uuid4(), 1, (valid, invalid), NOW)
    with pytest.raises(ReconciliationPreconditionError, match="PAGE_VALIDATION_FAILED"):
        persist_page(object(), uuid4(), 1, (valid, {"body":"PRIVATE-INVALID-TEXT"}), NOW)
    with pytest.raises(ReconciliationPreconditionError, match="PAGE_VALIDATION_FAILED"):
        persist_page(object(), uuid4(), 1, (valid,), NOW.replace(tzinfo=None))


def test_lock_key_is_stable_checked_and_namespaced():
    assert application_lock_key(1) == application_lock_key(1)
    assert application_lock_key(1) != application_lock_key(2)
    assert -(2**63) <= application_lock_key(2**63-1) < 2**63
    for invalid in (0,-1,True,"1",2**63):
        with pytest.raises(ReconciliationPreconditionError, match="INVALID_APPLICATION_ID"):
            application_lock_key(invalid)


def test_commit_hook_before_send_rolls_back_driver_transaction_before_failure_diagnostic(apple_database):
    from psycopg.pq import TransactionStatus
    from sqlalchemy import event
    engine=apple_database
    app,target=frame(engine)
    with locked(engine,app) as c:
        rid=new_run(c,app,target)
        page(c,rid,1,(record("prior-page"),))
        baseline={table.name:rows(engine,table) for table in (I,V,O)}
        records=(record("new-page"),)
        attempt,instant=ready(c,rid,2,records)
        armed=[True]
        observed=[]
        def fail_before_driver_commit(connection):
            if armed[0]:
                armed[0]=False
                observed.append(connection.connection.driver_connection.info.transaction_status)
                assert observed[-1] == TransactionStatus.INTRANS
                raise RuntimeError("PRIVATE_BEFORE_COMMIT_SEND")
        event.listen(c,"commit",fail_before_driver_commit)
        try:
            with pytest.raises(ReconciliationError) as caught:
                persist_page(c,rid,attempt,records,instant)
        finally:
            event.remove(c,"commit",fail_before_driver_commit)
        assert observed == [TransactionStatus.INTRANS]
        assert caught.value.diagnostics_persisted
        assert c.connection.driver_connection.info.transaction_status == TransactionStatus.IDLE
        assert baseline == {table.name:rows(engine,table) for table in (I,V,O)}
        failed=next(row for row in rows(engine,F) if row["id"]==attempt)
        assert failed["persistence_status"]=="rolled_back"
        assert not any(item["code"]=="PAGE_SUMMARY" for item in failed["anomalies"])


def test_actual_commit_then_ack_failure_preserves_durable_marker_and_page(apple_database,monkeypatch):
    from psycopg.pq import TransactionStatus
    engine=apple_database
    app,target=frame(engine)
    with locked(engine,app) as c:
        rid=new_run(c,app,target)
        records=(record(),)
        attempt,instant=ready(c,rid,1,records)
        driver=c.connection.driver_connection
        original_commit=driver.commit
        armed=[True]
        observed=[]
        def actual_commit_then_fail():
            original_commit()
            if armed[0]:
                armed[0]=False
                observed.append(driver.info.transaction_status)
                assert observed[-1] == TransactionStatus.IDLE
                raise RuntimeError("PRIVATE_AFTER_ACTUAL_COMMIT")
        with monkeypatch.context() as scoped:
            scoped.setattr(driver,"commit",actual_commit_then_fail)
            with pytest.raises(ReconciliationError) as caught:
                persist_page(c,rid,attempt,records,instant)
        assert observed == [TransactionStatus.IDLE]
        assert not caught.value.diagnostics_persisted
        assert driver.info.transaction_status == TransactionStatus.IDLE
        saved=rows(engine,F)[0]
        assert saved["persistence_status"]=="committed" and saved["error_codes"]==[]
        assert len(rows(engine,I))==len(rows(engine,V))==len(rows(engine,O))==1
        assert persist_page(c,rid,attempt,records,instant).replayed
        assert rows(engine,O)[0]["occurrence_count"]==1

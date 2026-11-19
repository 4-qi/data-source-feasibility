"""Retrieval contract checks using disposable PostgreSQL and synthetic text."""

import csv
from datetime import timedelta, timezone
from uuid import uuid4

import pytest

pytest.importorskip("sqlalchemy")
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from feasibility.apple_ingestion.contracts import ReviewRecord
from feasibility.apple_ingestion.reconcile import persist_page
from feasibility.apple_ingestion.recovery import application_session
from feasibility.apple_ingestion.retrieval import RetrievalError, iter_current_reviews, list_review_versions
from feasibility.apple_ingestion.retrieval_export import (
    CSV_COLUMNS, decode_csv_cell, export_current_reviews,
)
from test_apple_ingestion_reference import NOW, make_snapshot


def observe(engine, app, at, records, status="succeeded"):
    run = uuid4()
    with application_session(engine, app.application_id) as locked:
        c = locked.connection
        with c.begin():
            c.execute(text("""
                INSERT INTO collection_run(id, target_id, application_id, batch_id, started_at,
                    execution_status, coverage_status, config_snapshot)
                VALUES (:run, :target, :app, :batch, :at, 'running', 'pending', '{}')
            """), dict(run=run, target=app.target_id, app=app.application_id, batch=uuid4(), at=at))
            attempt = c.scalar(text("""
                INSERT INTO fetch_attempt(run_id, request_number, page_number, format, attempt_number,
                    started_at, finished_at, http_status, parsing_status, persistence_status, entry_count)
                VALUES (:run, 1, 1, 'json', 1, :at, :at, 200, 'succeeded', 'pending', :count)
                RETURNING id
            """), dict(run=run, at=at, count=len(records)))
        persist_page(c, run, attempt, records, at)
        with c.begin():
            c.execute(text("""
                UPDATE collection_run SET execution_status=:status, finished_at=:at,
                    coverage_status='indeterminate', stop_reason='synthetic' WHERE id=:run
            """), dict(run=run, at=at, status=status))
    return run


@pytest.fixture
def history(apple_database):
    engine = apple_database
    app = make_snapshot(engine, source_id="0001")
    other = make_snapshot(engine, source_id="0002")
    observe(engine, app, NOW, [
        ReviewRecord("001", None, "雪\n\"", 4),
        ReviewRecord("002", "", "empty title", 2),
        ReviewRecord("003", r"\N", r"\N", 3, source_updated_at=NOW),
    ])
    version_run = observe(engine, app, NOW + timedelta(days=1), [
        ReviewRecord("001", None, "雪\n\"", 5),
        ReviewRecord("001", None, "conflicting text", 5),
    ], status="partial")
    observe(engine, app, NOW + timedelta(days=2), [ReviewRecord("001", None, "雪\n\"", 5)])
    observe(engine, other, NOW, [ReviewRecord("001", None, "other app", 1)])
    return engine, app, version_run


def test_current_history_and_filters(history):
    engine, app, run_id = history
    with engine.connect() as c:
        def current(**kw):
            return list(iter_current_reviews(c, source_application_id=app.source_application_id, **kw))

        rows = current(batch_size=1)
        assert current(batch_size=50) == rows
        assert [row.source_review_id for row in rows] == ["001", "002", "003"]
        row = rows[0]
        assert (row.rating, row.version_number, row.detecting_run_status) == (5, 2, "partial")
        assert (row.detecting_run_id, row.observation_count, row.conflict_occurrence_count) == (run_id, 3, 1)
        assert current(ratings=[4]) == []
        assert current(ratings=[5, 5]) == [row]
        east = timezone(timedelta(hours=8))
        assert current(start=NOW.astimezone(east), end=NOW + timedelta(seconds=1)) == rows
        assert current(end=NOW) == []
        assert current(time_field="source_updated_at", start=NOW) == [rows[2]]
        assert current(time_field="source_updated_at") == rows
        versions = list_review_versions(c, source_application_id="0001", source_review_id="001")
        assert [(v.version_number, v.rating, v.is_current) for v in versions] == [(1, 4, False), (2, 5, True)]
        assert versions[0].body == versions[1].body == row.body
        assert list_review_versions(c, source_application_id="0001", source_review_id="absent") == []
        with pytest.raises(RetrievalError, match="Application not found"):
            list(iter_current_reviews(c, source_application_id="absent"))


@pytest.mark.parametrize("kw", [
    {"ratings": [True]}, {"ratings": [6]}, {"ratings": []}, {"ratings": "1"},
    {"start": NOW.replace(tzinfo=None)}, {"start": NOW, "end": NOW},
    {"time_field": "source_created_at"}, {"batch_size": 0}, {"batch_size": True},
])
def test_invalid_filters_fail_before_sql(kw):
    with pytest.raises(RetrievalError):
        list(iter_current_reviews(None, source_application_id="0001", **kw))


def test_export_round_trip_and_concurrent_version(history, tmp_path, monkeypatch):
    from feasibility.apple_ingestion import retrieval_export as module

    engine, app, _ = history
    original = module.iter_current_reviews

    def concurrent_write(connection, **kw):
        assert connection.exec_driver_sql("SHOW transaction_read_only").scalar_one() == "on"
        assert connection.exec_driver_sql("SHOW transaction_isolation").scalar_one() == "repeatable read"
        # The exporter has already selected the database in this snapshot.
        observe(engine, app, NOW + timedelta(days=3), [ReviewRecord("001", None, "雪\n\"", 1)])
        yield from original(connection, **kw)

    monkeypatch.setattr(module, "iter_current_reviews", concurrent_write)
    output = tmp_path / "export"
    manifest = export_current_reviews(engine, output, dataset_label="synthetic",
        expected_database=engine.url.database, source_application_id="0001", batch_size=1)
    assert manifest["row_count"] == 3
    assert manifest["exported_at"].endswith("Z")
    assert "雪" not in (output / "manifest.json").read_text()
    with (output / "reviews.csv").open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        assert tuple(reader.fieldnames) == CSV_COLUMNS
        rows = [{k: decode_csv_cell(v) for k, v in row.items()} for row in reader]
    assert [r["title"] for r in rows] == [None, "", r"\N"]
    assert rows[0]["body"] == "雪\n\"" and rows[2]["body"] == r"\N"
    assert rows[0]["rating"] == "5"
    assert rows[0]["source_review_id"] == "001"
    assert rows[0]["source_updated_at"] is None and rows[2]["source_updated_at"].endswith("Z")
    with engine.connect() as c:
        assert list(iter_current_reviews(c, source_application_id="0001"))[0].rating == 1


def test_database_mismatch_cleans_output(history, tmp_path):
    engine, _, _ = history
    output = tmp_path / "wrong"
    with pytest.raises(RetrievalError, match="does not match"):
        export_current_reviews(engine, output, dataset_label="wrong",
            expected_database="different", source_application_id="0001")
    assert not output.exists()


def test_select_only_reporting_role(history):
    engine, _, _ = history
    role = "retrieval_test_" + uuid4().hex
    with engine.begin() as c:
        c.exec_driver_sql(f'CREATE ROLE "{role}" NOLOGIN')
        c.exec_driver_sql(f'GRANT USAGE ON SCHEMA public TO "{role}"')
        c.exec_driver_sql(f'GRANT SELECT ON ALL TABLES IN SCHEMA public TO "{role}"')
    try:
        with engine.begin() as c:
            c.exec_driver_sql(f'SET LOCAL ROLE "{role}"')
            assert len(list(iter_current_reviews(c, source_application_id="0001"))) == 3
            assert len(list_review_versions(c, source_application_id="0001", source_review_id="001")) == 2
            with pytest.raises(DBAPIError) as denied, c.begin_nested():
                c.exec_driver_sql("UPDATE review SET last_observed_at = now()")
            assert denied.value.orig.sqlstate == "42501"
    finally:
        with engine.begin() as c:
            c.exec_driver_sql(f'DROP OWNED BY "{role}"')
            c.exec_driver_sql(f'DROP ROLE "{role}"')

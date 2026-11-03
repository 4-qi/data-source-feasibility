"""Offline contract acceptance; no RSS, transport, parser or hashing involved."""
from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from feasibility.apple_ingestion.contracts import (
    ComparisonEligibility, ConfigSnapshot, ContractError, CoverageStatus,
    ExecutionStatus, FeedFormat, IngestionConfig, ParsingStatus, PersistenceStatus,
    ReasonCode, ReferenceExclusionReason, ReviewRecord, RunMode,
)
from feasibility.apple_ingestion.seed import load_seed_manifest, seed_defaults


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "results/mainstream/app_sample_manifest.json"


def snapshot(**changes):
    return ConfigSnapshot(application_id=1, source_application_id="572688855", target_id=2,
                          software_revision="synthetic-test-revision", parser_version="fixture-v1",
                          **changes)


def test_pilot_defaults_and_json_roundtrip():
    value = snapshot()
    config = value.config
    assert (config.min_pages, config.max_pages, config.max_http_requests, config.retry_count) == (2, 5, 10, 0)
    assert (config.min_overlap_count, config.min_overlap_ratio) == (20, .2)
    assert (config.global_spacing_seconds, config.connect_timeout_seconds, config.read_timeout_seconds) == (2, 10, 25)
    assert (config.max_response_bytes, config.target_deadline_seconds, config.interval_hours) == (2_000_000, 900, 24)
    assert (config.reference_max_age_hours, config.reference_age_policy) == (72, "warn_only")
    assert config.formats == (FeedFormat.JSON, FeedFormat.XML)
    assert config.allow_redirects is False and config.ambient_credentials is False
    assert ConfigSnapshot.from_dict(json.loads(json.dumps(value.to_dict(), allow_nan=False))) == value


def test_snapshot_is_deeply_immutable_and_serialization_is_detached():
    original = snapshot()
    data = original.to_dict()
    restored = ConfigSnapshot.from_dict(data)
    data["config"]["formats"].append("other")
    data["config"]["retry_count"] = 50
    exported = restored.to_dict()
    exported["config"]["formats"].clear()
    assert restored == original
    assert restored.config.formats == (FeedFormat.JSON, FeedFormat.XML)
    with pytest.raises(FrozenInstanceError):
        restored.config.retry_count = 5
    with pytest.raises(FrozenInstanceError):
        restored.software_revision = "changed"


@pytest.mark.parametrize("field", list(snapshot().to_dict()))
def test_all_snapshot_fields_are_required_on_deserialization(field):
    data = snapshot().to_dict()
    del data[field]
    with pytest.raises(ContractError):
        ConfigSnapshot.from_dict(data)


@pytest.mark.parametrize("field", list(IngestionConfig().to_dict()))
def test_all_effective_settings_are_required_on_deserialization(field):
    data = snapshot().to_dict()
    del data["config"][field]
    with pytest.raises(ContractError):
        ConfigSnapshot.from_dict(data)


@pytest.mark.parametrize("field,value", [
    ("min_pages", True), ("max_pages", 1), ("max_http_requests", 0),
    ("min_overlap_count", -1), ("retry_count", 1.5), ("interval_hours", "24"),
    ("min_overlap_ratio", True), ("min_overlap_ratio", 1.1),
    ("min_overlap_ratio", float("nan")), ("global_spacing_seconds", float("inf")),
    ("connect_timeout_seconds", 0), ("read_timeout_seconds", -1),
    ("max_response_bytes", 0), ("target_deadline_seconds", 0),
    ("reference_max_age_hours", 0), ("reference_age_policy", "exclude_old"),
    ("allow_redirects", True), ("allow_redirects", 0), ("ambient_credentials", True),
    ("allowed_host", "example.com"), ("scheme", "http"),
    ("formats", [FeedFormat.JSON, FeedFormat.XML]), ("formats", ("json", "xml")),
    ("fallback_policy", "any_failure"),
])
def test_config_rejects_invalid_types_ranges_and_unsafe_policies(field, value):
    with pytest.raises(ContractError):
        replace(IngestionConfig(), **{field: value})


@pytest.mark.parametrize("field,value", [
    ("schema_version", "future/2"), ("source", "other"), ("storefront", "gb"),
    ("sort_by", "rating"), ("application_id", True), ("target_id", 0),
    ("source_application_id", 572688855), ("parser_version", " "),
    ("software_revision", {}), ("hash_contract_version", []),
    ("access_decision_ref", ""), ("retention_policy_ref", False),
    ("run_mode", "synthetic"), ("config", {}),
])
def test_snapshot_rejects_invalid_identity_and_versions(field, value):
    with pytest.raises(ContractError):
        replace(snapshot(), **{field: value})


@pytest.mark.parametrize("path,value", [
    (("extra",), "bad"), (("run_mode",), "unknown"), (("run_mode",), []),
    (("config", "extra"), 1), (("config", "formats"), "json"),
    (("config", "formats"), ["json", "yaml"]),
    (("config", "formats"), ["json", {}]),
    (("config", "formats"), ["xml", "json"]),
])
def test_snapshot_rejects_malformed_json_contract(path, value):
    data = snapshot().to_dict()
    node = data
    for key in path[:-1]:
        node = node[key]
    node[path[-1]] = value
    with pytest.raises(ContractError):
        ConfigSnapshot.from_dict(data)


def test_live_snapshot_cannot_silently_fill_missing_decisions():
    for access, retention in ((None, None), ("access-1", None), (None, "retention-1")):
        with pytest.raises(ContractError, match="live snapshots require"):
            snapshot(run_mode=RunMode.LIVE, access_decision_ref=access, retention_policy_ref=retention)
    recorded = snapshot(run_mode=RunMode.LIVE, access_decision_ref="pending-owner-record",
                        retention_policy_ref="policy-record")
    assert not hasattr(recorded, "live_authorized")
    assert not hasattr(recorded, "permitted")
    assert recorded.run_mode is RunMode.LIVE  # provenance, not a permission decision


def test_record_preserves_full_text_ids_nulls_and_aware_offsets():
    when = datetime(2026, 11, 3, 12, tzinfo=timezone(timedelta(hours=-8)))
    record = ReviewRecord("  opaque:001 /suffix  ", "\r\nTitle &amp; 😀", "line 1\r\n" + "正文 " * 20_000,
                          5, " 1.0 ", when)
    assert record.source_review_id == "  opaque:001 /suffix  "
    assert record.title == "\r\nTitle &amp; 😀"
    assert record.body.endswith("正文 ") and len(record.body) > 50_000
    assert record.source_updated_at is when
    assert ReviewRecord("id", None, "", 1).title is None
    assert ReviewRecord("id", "", "", 1).title == ""
    with pytest.raises(FrozenInstanceError):
        record.body = "changed"


@pytest.mark.parametrize("field,value", [
    ("source_review_id", ""), ("source_review_id", " \t\n"), ("source_review_id", 123),
    ("source_review_id", "nul\x00id"), ("title", []), ("body", None),
    ("body", "nul\x00body"), ("rating", True), ("rating", "3"), ("rating", 0), ("rating", 6),
    ("application_version", 3), ("source_updated_at", datetime(2026, 11, 3)),
    ("source_updated_at", "2026-11-03T00:00:00Z"),
])
def test_record_rejects_invalid_values_without_disclosing_content(field, value):
    args = dict(source_review_id="opaque", title=None, body="private full review", rating=3)
    args[field] = value
    with pytest.raises(ContractError) as caught:
        ReviewRecord(**args)
    assert "private full review" not in str(caught.value)


def test_status_dimensions_and_reason_codes_remain_independent():
    assert ExecutionStatus.SUCCEEDED.value == "succeeded"
    assert CoverageStatus.OVERLAP_INSUFFICIENT.value == "overlap_insufficient"
    assert ComparisonEligibility.ELIGIBLE.value == "eligible"
    assert {status.value for status in ParsingStatus} == {"pending", "not_attempted", "succeeded", "failed"}
    assert PersistenceStatus.UNKNOWN.value == "unknown"
    assert ReasonCode.REFERENCE_AGE_WARNING.value == "REFERENCE_AGE_WARNING"
    exclusions = {reason.value for reason in ReferenceExclusionReason}
    assert "REFERENCE_AGE_WARNING" not in exclusions
    assert "LOW_ID_OVERLAP_COUNT" not in exclusions
    assert "OVERLAP_INSUFFICIENT" not in exclusions


def test_seed_frame_comes_from_historical_manifest_without_mutating_it():
    before = MANIFEST.read_bytes()
    raw = json.loads(before)
    records = load_seed_manifest(MANIFEST)
    assert len(records) == 8
    assert [r.source_application_id for r in records] == [r["app_store_id"] for r in raw["apps"]]
    assert [r.name for r in records] == [r["name"] for r in raw["apps"]]
    assert {r.storefront for r in records} == {"us"}
    assert MANIFEST.read_bytes() == before


@pytest.mark.parametrize("defect", ["missing", "seven", "duplicate", "storefront", "category", "numeric_id"])
def test_seed_rejects_incomplete_or_changed_sampling_frame(tmp_path, defect):
    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    if defect == "missing":
        del data["apps"][0]["name"]
    elif defect == "seven":
        data["apps"].pop()
    elif defect == "duplicate":
        data["apps"][0]["app_store_id"] = data["apps"][1]["app_store_id"]
    elif defect == "storefront":
        data["apps"][0]["storefront"] = "gb"
    elif defect == "category":
        data["apps"][0]["analysis_stratum"] = "education"
    else:
        data["apps"][0]["app_store_id"] = 572688855
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ContractError):
        load_seed_manifest(path)


def test_import_has_no_file_network_or_database_side_effects():
    # A fresh interpreter proves imports do not load manifest, models or SQLAlchemy.
    script = '''
import sys

def audit(event, args):
    if event in {"socket.connect", "socket.getaddrinfo"}:
        raise AssertionError("network access during import")
    if event == "open" and str(args[0]).endswith("app_sample_manifest.json"):
        raise AssertionError("manifest read during import")
sys.addaudithook(audit)
import feasibility.apple_ingestion
import feasibility.apple_ingestion.contracts
import feasibility.apple_ingestion.seed
assert "sqlalchemy" not in sys.modules
assert "feasibility.apple_ingestion.models" not in sys.modules
'''
    result = subprocess.run([sys.executable, "-c", script], cwd=ROOT,
                            env={**os.environ, "PYTHONPATH": str(ROOT / "src")},
                            capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_seed_requires_explicit_caller_transaction():
    class Connection:
        def in_transaction(self):
            return False
    with pytest.raises(ContractError, match="caller-owned transaction"):
        seed_defaults(Connection(), MANIFEST)


def test_seed_postgresql_idempotence_preservation_and_caller_rollback():
    """Opt-in real seed check; isolated transactional schema, synthetic defaults."""
    dsn = os.environ.get("APPLE_INGESTION_TEST_DSN")
    if not dsn or os.environ.get("APPLE_INGESTION_DISPOSABLE") != "1":
        pytest.skip("seed integration requires explicit disposable PostgreSQL")
    psycopg = pytest.importorskip("psycopg")
    sa = pytest.importorskip("sqlalchemy")
    from sqlalchemy.schema import CreateSchema
    from uuid import uuid4
    from feasibility.apple_ingestion.models import Base

    params = psycopg.conninfo.conninfo_to_dict(dsn)
    if not params.get("dbname", "").startswith("apple_phase_a_"):
        pytest.fail("seed test refuses a non-disposable database")
    url = sa.URL.create("postgresql+psycopg", username=params.get("user"),
                        password=params.get("password"), database=params["dbname"],
                        query={k: v for k, v in params.items() if k not in {"user", "password", "dbname"}})
    engine = sa.create_engine(url, hide_parameters=True)
    schema = "seed_test_" + uuid4().hex
    try:
        with engine.connect() as connection:
            transaction = connection.begin()
            try:
                connection.execute(CreateSchema(schema))
                connection = connection.execution_options(schema_translate_map={None: schema})
                Base.metadata.create_all(connection)
                app = Base.metadata.tables["application"]
                target = Base.metadata.tables["collection_target"]
                with connection.begin_nested() as savepoint:
                    first = seed_defaults(connection, MANIFEST)
                    assert len(first.application_ids) == len(first.target_ids) == 8
                    assert connection.execute(sa.select(sa.func.count()).select_from(app)).scalar_one() == 8
                    savepoint.rollback()
                assert connection.execute(sa.select(sa.func.count()).select_from(app)).scalar_one() == 0
                first = seed_defaults(connection, MANIFEST)
                rows = connection.execute(sa.select(target)).mappings().all()
                assert len(rows) == 8
                for row in rows:
                    assert row["enabled"] is False
                    assert (row["storefront"], row["sort_by"]) == ("us", "mostrecent")
                    assert (row["min_pages"], row["max_pages"], row["max_http_requests"]) == (2, 5, 10)
                    assert (row["min_overlap_count"], float(row["min_overlap_ratio"])) == (20, .2)
                    assert (row["reference_max_age_hours"], row["interval_hours"]) == (72, 24)
                connection.execute(target.update().where(target.c.id == first.target_ids[0]).values(
                    enabled=True, min_pages=3))
                second = seed_defaults(connection, MANIFEST)
                assert second == first
                assert connection.execute(sa.select(sa.func.count()).select_from(app)).scalar_one() == 8
                changed = connection.execute(sa.select(target.c.enabled, target.c.min_pages).where(
                    target.c.id == first.target_ids[0])).one()
                assert changed == (True, 3)
                assert connection.in_transaction()
            finally:
                transaction.rollback()  # removes all seed data and the test-only schema
        with engine.connect() as connection:
            assert connection.execute(sa.text(
                "SELECT count(*) FROM pg_namespace WHERE nspname=:schema"), {"schema": schema}
            ).scalar_one() == 0
    finally:
        engine.dispose()

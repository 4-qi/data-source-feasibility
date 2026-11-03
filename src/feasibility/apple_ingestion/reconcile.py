"""Atomic, full-fidelity page reconciliation; no HTTP or run lifecycle logic.

The caller owns one dedicated PostgreSQL Connection through a run. Before each
call, acquire pg_advisory_lock(application_lock_key(application_id)) on that
connection and commit the lock-acquisition transaction. Pass the same connection
with no active transaction; persist_page owns and commits exactly one page
transaction. Release the session lock before returning the connection to a pool.
A lost/invalidated connection is never reconnected by this module.

Cross-page duplicate counts include every occurrence of an ID seen on an earlier
committed page. Same-page duplicate counts include repeated occurrences within
this page, so these two diagnostic subsets can overlap. duplicate_count is the
non-overlapping total (entry_count minus new observations in this run).
"""
from __future__ import annotations

from dataclasses import dataclass, fields
from datetime import datetime, timezone
import hashlib
from typing import Callable, Iterable
from uuid import UUID

from sqlalchemy import func, insert, select, text, update
from sqlalchemy.engine import Connection
from sqlalchemy.exc import DBAPIError, IntegrityError

from .contracts import ContractError, ReviewRecord
from .models import CollectionRun, FetchAttempt, Review, ReviewObservation, ReviewVersion
from .normalizer import canonical_fields, fingerprint

RUN = CollectionRun.__table__
ATTEMPT = FetchAttempt.__table__
REVIEW = Review.__table__
VERSION = ReviewVersion.__table__
OBSERVATION = ReviewObservation.__table__
MAX_DIAGNOSTICS = 100
_SQLSTATES = frozenset({"23502", "23503", "23505", "23514", "22001", "22003", "22021", "22P02", "40P01", "40001", "55P03", "57014"})
_COUNTERS = ("entry_count", "new_count", "unchanged_count", "changed_count", "duplicate_count",
             "same_page_duplicate_count", "cross_page_duplicate_count", "conflict_count")


class ReconciliationError(RuntimeError):
    """Safe failure suitable for diagnostics; contains no database exception text."""
    def __init__(self, code: str, *, diagnostics_persisted: bool = False, sqlstate: str | None = None):
        self.code = code
        self.diagnostics_persisted = diagnostics_persisted
        self.sqlstate = sqlstate
        super().__init__(code)


class ReconciliationPreconditionError(ReconciliationError):
    """No page mutation is permitted when the caller's protocol is invalid."""


@dataclass(frozen=True)
class PageResult:
    run_id: UUID
    attempt_id: int
    page_number: int
    entry_count: int
    distinct_review_count: int
    new_count: int
    unchanged_count: int
    changed_count: int
    duplicate_count: int
    same_page_duplicate_count: int
    cross_page_duplicate_count: int
    conflict_count: int
    replayed: bool = False

    @property
    def first_observation_count(self) -> int:
        return self.new_count + self.unchanged_count + self.changed_count

    @property
    def duplicate_only(self) -> bool:
        return self.entry_count > 0 and self.first_observation_count == 0

    @property
    def has_conflicts(self) -> bool:
        return self.conflict_count > 0


def application_lock_key(application_id: int) -> int:
    """Stable signed 64-bit key in the Apple ingestion application namespace."""
    if type(application_id) is not int or not 0 < application_id <= (2**63 - 1):
        raise ReconciliationPreconditionError("INVALID_APPLICATION_ID")
    payload = f"apple-ingestion/application/{application_id}".encode("ascii")
    return int.from_bytes(hashlib.sha256(payload).digest()[:8], "big", signed=True)


def _prepare(records: Iterable[ReviewRecord], observed_at: datetime):
    try:
        if not isinstance(observed_at, datetime) or observed_at.tzinfo is None or observed_at.utcoffset() is None:
            raise ContractError("observed_at must be aware")
        instant = observed_at.astimezone(timezone.utc)
        prepared = []
        for record in records:
            if type(record) is not ReviewRecord:
                raise ContractError("record must be ReviewRecord")
            # Revalidate even if a caller bypassed frozen-dataclass protection.
            validated = ReviewRecord(**{field.name: getattr(record, field.name) for field in fields(ReviewRecord)})
            validated.source_review_id.encode("utf-8")
            prepared.append((validated, fingerprint(validated), canonical_fields(validated)))
        return tuple(prepared), instant
    except Exception:
        raise ReconciliationPreconditionError("PAGE_VALIDATION_FAILED") from None


def _check_connection(connection: Connection) -> None:
    if not isinstance(connection, Connection):
        raise ReconciliationPreconditionError("LOCKED_CONNECTION_REQUIRED")
    if connection.closed or connection.invalidated:
        raise ReconciliationPreconditionError("APPLICATION_SESSION_LOST")
    if connection.in_transaction():
        raise ReconciliationPreconditionError("PAGE_REQUIRES_IDLE_CONNECTION")
    if connection.dialect.name != "postgresql" or connection.dialect.driver != "psycopg":
        raise ReconciliationPreconditionError("POSTGRESQL_PSYCOPG_REQUIRED")
    if connection.engine.echo or not connection.engine.hide_parameters:
        raise ReconciliationPreconditionError("SAFE_SQL_LOGGING_REQUIRED")
    if getattr(connection.connection.driver_connection, "autocommit", False):
        raise ReconciliationPreconditionError("PAGE_REQUIRES_TRANSACTIONAL_CONNECTION")


def _owns_lock(connection: Connection, application_id: int) -> bool:
    unsigned = application_lock_key(application_id) & ((1 << 64) - 1)
    return bool(connection.scalar(text("""
        SELECT EXISTS (SELECT 1 FROM pg_locks
        WHERE locktype = 'advisory' AND pid = pg_backend_pid()
          AND classid::bigint = :high AND objid::bigint = :low
          AND objsubid = 1 AND mode = 'ExclusiveLock' AND granted)
    """), {"high": unsigned >> 32, "low": unsigned & 0xFFFFFFFF}))


def _timeouts(connection, lock_timeout_ms, statement_timeout_ms):
    connection.execute(select(func.set_config("lock_timeout", f"{lock_timeout_ms}ms", True)))
    connection.execute(select(func.set_config("statement_timeout", f"{statement_timeout_ms}ms", True)))


def _bounded(existing: list, additions: list, summary: dict | None = None) -> list:
    """Bound details while retaining exact per-code event totals, not raw text."""
    totals = next((item for item in existing if item.get("code") == "DIAGNOSTIC_TOTALS"), None)
    details = [dict(item) for item in existing if item.get("code") not in {
        "DIAGNOSTIC_TOTALS", "PAGE_SUMMARY", "RECONCILIATION_SUMMARY"}]
    counts = dict(totals["counts"]) if totals else {}
    truncated = bool(totals and totals.get("detail_truncated"))
    if totals is None:
        for detail in details:
            code = detail["code"]
            counts[code] = counts.get(code, 0) + detail.get("count", 1)
    # One summary (if supplied), one exact-totals record, at most 98/99 details.
    capacity = MAX_DIAGNOSTICS - 1 - (summary is not None)
    if len(details) > capacity:
        details = details[:capacity]
        truncated = True
    for addition in additions:
        code = addition["code"]
        count = addition.get("count", 1)
        counts[code] = counts.get(code, 0) + count
        signature = {key: value for key, value in addition.items() if key != "count"}
        match = next((item for item in details if {
            key: value for key, value in item.items() if key != "count"} == signature), None)
        if match is not None:
            match["count"] = match.get("count", 1) + count
        elif len(details) < capacity:
            details.append(dict(addition))
        else:
            truncated = True
    return ([summary] if summary else []) + [{"code": "DIAGNOSTIC_TOTALS", "counts": counts,
                                              "detail_truncated": truncated}] + details


def _page_summary(result: PageResult) -> dict:
    return {"code": "PAGE_SUMMARY", "page": result.page_number,
            "distinct_review_count": result.distinct_review_count,
            **{name: getattr(result, name) for name in _COUNTERS}}


def _run_summary(existing: list, result: PageResult) -> dict:
    prior = next((item for item in existing if item.get("code") == "RECONCILIATION_SUMMARY"), {})
    return {"code": "RECONCILIATION_SUMMARY",
            "committed_page_count": prior.get("committed_page_count", 0) + 1,
            "distinct_review_count": prior.get("distinct_review_count", 0) + result.first_observation_count,
            **{name: prior.get(name, 0) + getattr(result, name) for name in _COUNTERS}}


def _replayed_result(run_id, attempt) -> PageResult:
    summary = next((item for item in attempt["anomalies"] if item.get("code") == "PAGE_SUMMARY"), None)
    if summary is None:
        raise ReconciliationPreconditionError("COMMITTED_PAGE_SUMMARY_MISSING")
    return PageResult(run_id=run_id, attempt_id=attempt["id"], page_number=attempt["page_number"],
                      distinct_review_count=summary["distinct_review_count"], replayed=True,
                      **{name: summary[name] for name in _COUNTERS})


def _stored_values(connection, version_id):
    version = connection.execute(select(VERSION).where(VERSION.c.id == version_id)).mappings().one()
    record = ReviewRecord(source_review_id="internal-comparison", title=version["title"], body=version["body"],
                          rating=version["rating"], application_version=version["application_version"],
                          source_updated_at=version["source_updated_at"])
    return (version["content_hash"], version["metadata_hash"]), canonical_fields(record), version["version_number"]


def _new_version(connection, record, hashes, review_id, application_id, version_number, run_id,
                 observed_at, version_id=None):
    values = dict(review_id=review_id, application_id=application_id, version_number=version_number,
                  title=record.title, body=record.body, rating=record.rating,
                  application_version=record.application_version, source_updated_at=record.source_updated_at,
                  content_hash=hashes[0], metadata_hash=hashes[1], first_observed_at=observed_at,
                  detecting_run_id=run_id)
    if version_id is not None:
        values["id"] = version_id
    return connection.scalar(insert(VERSION).values(**values).returning(VERSION.c.id))


def _write_page(connection, run_id, attempt_id, prepared, observed_at, fault_hook):
    run = connection.execute(select(RUN).where(RUN.c.id == run_id)).mappings().one_or_none()
    if run is None:
        raise ReconciliationPreconditionError("RUN_NOT_FOUND")
    application_id = run["application_id"]
    if not _owns_lock(connection, application_id):
        raise ReconciliationPreconditionError("APPLICATION_SESSION_LOCK_REQUIRED")
    attempt = connection.execute(select(ATTEMPT).where(ATTEMPT.c.id == attempt_id).with_for_update()).mappings().one_or_none()
    if attempt is None or attempt["run_id"] != run_id:
        raise ReconciliationPreconditionError("ATTEMPT_RUN_MISMATCH")
    if attempt["persistence_status"] == "committed":
        return _replayed_result(run_id, attempt)
    run = connection.execute(select(RUN).where(RUN.c.id == run_id).with_for_update()).mappings().one()
    if run["execution_status"] != "running":
        raise ReconciliationPreconditionError("RUN_NOT_RUNNING")
    if (attempt["parsing_status"] != "succeeded" or attempt["persistence_status"] not in {"pending", "rolled_back"}
            or attempt["entry_count"] != len(prepared) or attempt["finished_at"] != observed_at
            or observed_at < attempt["started_at"] or observed_at < run["started_at"]):
        raise ReconciliationPreconditionError("ATTEMPT_NOT_READY_FOR_PAGE")
    page = attempt["page_number"]
    last_page = connection.scalar(select(func.max(ATTEMPT.c.page_number)).where(
        ATTEMPT.c.run_id == run_id, ATTEMPT.c.persistence_status == "committed")) or 0
    if page != last_page + 1:
        raise ReconciliationPreconditionError("PAGE_ORDER_REQUIRED")
    source_ids = {record.source_review_id for record, _, _ in prepared}
    identities = {row["source_review_id"]: dict(row) for row in connection.execute(
        select(REVIEW).where(REVIEW.c.application_id == application_id,
                             REVIEW.c.source_review_id.in_(sorted(source_ids)))
        .order_by(REVIEW.c.id).with_for_update()).mappings()}
    observations = {}
    if identities:
        observations = {row["review_id"]: dict(row) for row in connection.execute(
            select(OBSERVATION).where(OBSERVATION.c.run_id == run_id,
                                     OBSERVATION.c.review_id.in_([r["id"] for r in identities.values()]))).mappings()}
    compared_versions = {}
    seen_on_page = set()
    counts = {name: 0 for name in _COUNTERS}
    counts["entry_count"] = len(prepared)
    details = []
    fault = fault_hook or (lambda stage: None)
    for position, (record, hashes, canonical) in enumerate(prepared, 1):
        identity = identities.get(record.source_review_id)
        if identity is None:
            reserved = connection.scalar(select(func.nextval(func.pg_get_serial_sequence("review_version", "id"))))
            review_id = connection.scalar(insert(REVIEW).values(
                application_id=application_id, source_review_id=record.source_review_id,
                current_version_id=reserved, first_observed_at=observed_at, last_observed_at=observed_at
            ).returning(REVIEW.c.id))
            fault("after_identity_insert")
            _new_version(connection, record, hashes, review_id, application_id, 1, run_id, observed_at, reserved)
            fault("after_version_insert")
            identity = {"id": review_id, "current_version_id": reserved}
            identities[record.source_review_id] = identity
            compared_versions[reserved] = (hashes, canonical, 1)
            first_action = "new"
        else:
            review_id = identity["id"]
            first_action = None
        observation = observations.get(review_id)
        if observation is not None:
            counts["duplicate_count"] += 1
            if record.source_review_id in seen_on_page:
                counts["same_page_duplicate_count"] += 1
                details.append({"code": "SAME_PAGE_DUPLICATE", "page": page, "review_id": review_id, "count": 1})
            if observation["first_observed_page"] < page:
                counts["cross_page_duplicate_count"] += 1
                details.append({"code": "CROSS_PAGE_DUPLICATE", "page": page, "review_id": review_id, "count": 1})
            accepted = observation["observed_version_id"]
            if accepted not in compared_versions:
                compared_versions[accepted] = _stored_values(connection, accepted)
            accepted_hashes, accepted_fields, _ = compared_versions[accepted]
            conflict = not (hashes == accepted_hashes and canonical == accepted_fields)
            counts["conflict_count"] += int(conflict)
            if conflict:
                details.append({"code": "INTRA_RUN_CONFLICT", "page": page, "review_id": review_id,
                                "candidate_content_hash": hashes[0].hex(),
                                "candidate_metadata_hash": hashes[1].hex(), "count": 1})
            connection.execute(update(OBSERVATION).where(
                OBSERVATION.c.run_id == run_id, OBSERVATION.c.review_id == review_id
            ).values(occurrence_count=OBSERVATION.c.occurrence_count + 1,
                     conflict_count=OBSERVATION.c.conflict_count + int(conflict)))
        else:
            current = identity["current_version_id"]
            if first_action is None:
                if current not in compared_versions:
                    compared_versions[current] = _stored_values(connection, current)
                previous_hashes, previous_fields, number = compared_versions[current]
                if hashes == previous_hashes and canonical == previous_fields:
                    first_action = "unchanged"
                else:
                    current = _new_version(connection, record, hashes, review_id, application_id,
                                           number + 1, run_id, observed_at)
                    fault("after_version_insert")
                    connection.execute(update(REVIEW).where(REVIEW.c.id == review_id).values(current_version_id=current))
                    identity["current_version_id"] = current
                    compared_versions[current] = (hashes, canonical, number + 1)
                    first_action = "changed"
            counts[first_action + "_count"] += 1
            connection.execute(insert(OBSERVATION).values(
                run_id=run_id, review_id=review_id, application_id=application_id,
                observed_version_id=current, first_observed_at=observed_at,
                first_observed_page=page, first_observed_position=position, first_action=first_action))
            observations[review_id] = {"observed_version_id": current, "first_observed_page": page}
        fault("after_observation_upsert")
        connection.execute(update(REVIEW).where(REVIEW.c.id == review_id).values(
            last_observed_at=func.greatest(REVIEW.c.last_observed_at, observed_at)))
        seen_on_page.add(record.source_review_id)
    result = PageResult(run_id=run_id, attempt_id=attempt_id, page_number=page,
                        distinct_review_count=len(source_ids), **counts)
    if not prepared:
        details.append({"code": "EMPTY_PAGE", "page": page, "count": 1})
    elif result.duplicate_only:
        details.append({"code": "PAGE_DUPLICATE_ONLY", "page": page, "count": 1})
    connection.execute(update(RUN).where(RUN.c.id == run_id).values(
        anomalies=_bounded(run["anomalies"], details, _run_summary(run["anomalies"], result))))
    connection.execute(update(ATTEMPT).where(ATTEMPT.c.id == attempt_id).values(
        persistence_status="committed", anomalies=_bounded(attempt["anomalies"], details, _page_summary(result))))
    fault("after_attempt_update")
    return result


def _rollback_unfinished_driver_transaction(connection: Connection) -> bool:
    """Restore an idle driver before any independent marker/diagnostic read.

    A SQLAlchemy commit hook may fail before COMMIT reaches PostgreSQL while
    SQLAlchemy has already detached its logical transaction. Connection.rollback
    alone then does nothing. Reading a marker in that driver transaction would
    see the uncommitted PAGE_SUMMARY and could accidentally commit the page.
    Actual committed pages have an IDLE driver and are never undone here.
    """
    if connection.closed or connection.invalidated:
        return False
    try:
        from psycopg.pq import TransactionStatus
        if connection.in_transaction():
            connection.rollback()
        driver = connection.connection.driver_connection
        state = driver.info.transaction_status
        if state in {TransactionStatus.INTRANS, TransactionStatus.INERROR}:
            driver.rollback()
        if driver.info.transaction_status != TransactionStatus.IDLE:
            raise RuntimeError("DRIVER_TRANSACTION_NOT_IDLE")
        return True
    except Exception:
        try:
            connection.invalidate()
        except Exception:
            pass
        return False


def _record_failure(connection, run_id, attempt_id, code, sqlstate, lock_timeout_ms, statement_timeout_ms):
    if not _rollback_unfinished_driver_transaction(connection):
        return False
    try:
        with connection.begin():
            _timeouts(connection, lock_timeout_ms, statement_timeout_ms)
            application_id = connection.scalar(select(RUN.c.application_id).where(RUN.c.id == run_id))
            if application_id is None or not _owns_lock(connection, application_id):
                return False
            attempt = connection.execute(select(ATTEMPT).where(ATTEMPT.c.id == attempt_id).with_for_update()).mappings().one_or_none()
            if (attempt is None or attempt["run_id"] != run_id
                    or attempt["persistence_status"] == "committed"):
                return False
            detail = {"code": code, "page": attempt["page_number"], "count": 1}
            if sqlstate:
                detail["sqlstate"] = sqlstate
            errors = list(dict.fromkeys([*attempt["error_codes"], code]))
            connection.execute(update(ATTEMPT).where(ATTEMPT.c.id == attempt_id).values(
                persistence_status="rolled_back", error_codes=errors,
                anomalies=_bounded(attempt["anomalies"], [detail])))
        return True
    except Exception:
        # A diagnostic commit can fail in the same way; never leave an
        # unfinished driver transaction for session cleanup to commit later.
        try:
            connection.invalidate()
        except Exception:
            pass
        return False


def persist_page(connection: Connection, run_id: UUID, attempt_id: int,
                 records: Iterable[ReviewRecord], observed_at: datetime, *,
                 fault_hook: Callable[[str], None] | None = None,
                 lock_timeout_ms: int = 5000, statement_timeout_ms: int = 30000) -> PageResult:
    """Validate all records, then commit one page or roll back the entire page.

    Attempt parse diagnostics must already be committed: succeeded/pending,
    entry_count matching records and finished_at equal to observed_at. Only a
    running run may accept a new page; committed attempt replay remains readable
    after finalization. Replay returns the durable PAGE_SUMMARY and never writes.

    Fault stages are after_identity_insert, after_version_insert,
    after_observation_upsert and after_attempt_update. Hooks receive stage names
    only; production leaves fault_hook unset. Failures are sanitized and a
    separate transaction records rolled_back when the same session is healthy.
    If that fails, diagnostics_persisted=False delegates outage handling to C.
    """
    prepared, instant = _prepare(records, observed_at)
    if not isinstance(run_id, UUID) or type(attempt_id) is not int or attempt_id <= 0:
        raise ReconciliationPreconditionError("INVALID_PAGE_IDENTITY")
    if (type(lock_timeout_ms) is not int or type(statement_timeout_ms) is not int
            or not 0 < lock_timeout_ms <= statement_timeout_ms <= 300000):
        raise ReconciliationPreconditionError("INVALID_DATABASE_TIMEOUTS")
    _check_connection(connection)
    try:
        with connection.begin():
            _timeouts(connection, lock_timeout_ms, statement_timeout_ms)
            if connection.scalar(text("SHOW transaction_isolation")) != "read committed":
                raise ReconciliationPreconditionError("READ_COMMITTED_REQUIRED")
            result = _write_page(connection, run_id, attempt_id, prepared, instant, fault_hook)
        return result
    except ReconciliationPreconditionError:
        raise
    except Exception as exc:
        sqlstate = getattr(getattr(exc, "orig", None), "sqlstate", None)
        sqlstate = sqlstate if sqlstate in _SQLSTATES else None
        code = ("DB_CONSTRAINT" if isinstance(exc, IntegrityError)
                else "DB_UNAVAILABLE" if isinstance(exc, DBAPIError) else "PAGE_PERSISTENCE_FAILED")
        persisted = _record_failure(connection, run_id, attempt_id, code, sqlstate,
                                    lock_timeout_ms, statement_timeout_ms)
        raise ReconciliationError(code, diagnostics_persisted=persisted, sqlstate=sqlstate) from None


__all__ = ["PageResult", "ReconciliationError", "ReconciliationPreconditionError",
           "application_lock_key", "persist_page"]

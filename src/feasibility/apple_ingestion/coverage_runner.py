"""Isolated contiguous-window acquisition; production Controller is unchanged.

Only internal parse/diagnostic/finalize helpers are composed here. Production
run_target and its policy validation/overlap stopping are never replaced.
"""
from dataclasses import asdict, replace
from datetime import datetime, timezone
import time
from uuid import UUID, uuid4

from sqlalchemy import insert, select, text

from .contracts import ConfigSnapshot, FeedFormat, IngestionConfig
from .controller import Controller, RUN, ATTEMPT
from .pagination_probe import _page_metrics
from .reconcile import persist_page, ReconciliationError, ReconciliationPreconditionError
from .recovery import application_session, replay_spool, recover_interrupted
from .reference import select_reference
from .parser import PARSER_VERSION
from .normalizer import HASH_CONTRACT_VERSION

APP = "570060128"
_PRECONDITION_CODES = frozenset({
    "INVALID_APPLICATION_ID", "PAGE_VALIDATION_FAILED", "LOCKED_CONNECTION_REQUIRED",
    "APPLICATION_SESSION_LOST", "PAGE_REQUIRES_IDLE_CONNECTION", "POSTGRESQL_PSYCOPG_REQUIRED",
    "SAFE_SQL_LOGGING_REQUIRED", "PAGE_REQUIRES_TRANSACTIONAL_CONNECTION",
    "COMMITTED_PAGE_SUMMARY_MISSING", "RUN_NOT_FOUND", "APPLICATION_SESSION_LOCK_REQUIRED",
    "ATTEMPT_RUN_MISMATCH", "RUN_NOT_RUNNING", "ATTEMPT_NOT_READY_FOR_PAGE", "PAGE_ORDER_REQUIRED",
    "INVALID_PAGE_IDENTITY", "INVALID_DATABASE_TIMEOUTS", "READ_COMMITTED_REQUIRED",
})


class CoverageError(RuntimeError):
    pass


def validate_snapshot(snapshot):
    ConfigSnapshot.from_dict(snapshot.to_dict())
    expected = snapshot.config
    if (snapshot.source_application_id != APP or snapshot.parser_version != PARSER_VERSION
            or snapshot.hash_contract_version != HASH_CONTRACT_VERSION or expected != replace(
            IngestionConfig(), interval_hours=12, max_pages=10, max_http_requests=20)):
        raise CoverageError("EXPERIMENT_SCOPE_MISMATCH")



class FixedDepthRunner:
    def __init__(self, engine, transport, spool, *, database, guard, reserve,
                 checkpoint, now=None, monotonic=time.monotonic):
        self.engine, self.transport, self.spool = engine, transport, spool
        self.database, self.guard, self.reserve = database, guard, reserve
        self.checkpoint = checkpoint
        self.now = now or (lambda: datetime.now(timezone.utc))
        self.monotonic = monotonic
        self.helper = Controller(engine, transport, spool, now=self.now,
                                 monotonic=monotonic, live_policy=self)

    def validate_target(self, snapshot, enabled, at):
        validate_snapshot(snapshot)
        if not enabled:
            raise CoverageError("EXPERIMENT_TARGET_DISABLED")
        self.guard()

    def run(self, snapshot, batch_id, *, run_id=None):
        validate_snapshot(snapshot)
        if type(batch_id) is not UUID:
            raise CoverageError("INVALID_BATCH_ID")
        run_id = run_id or uuid4()
        output = {"run_id": str(run_id), "batch_id": str(batch_id), "pages": [],
                  "attempt_timings": [], "requests": 0, "overall_status": "not_started",
                  "started_at": self.now().isoformat()}
        reference = None
        attempt_id = None
        stage = "intent"
        try:
            self.guard()
            with application_session(self.engine, snapshot.application_id) as session:
                connection = session.connection
                with connection.begin():
                    actual = connection.scalar(text("SELECT current_database()"))
                    if actual != self.database or actual == "apple_ingestion":
                        raise CoverageError("EXPERIMENT_DATABASE_MISMATCH")
                    self.helper._validate_target(connection, snapshot)
                replay_spool(connection, snapshot.application_id, self.spool, self.now())
                recover_interrupted(connection, snapshot.application_id, self.now())
                with connection.begin():
                    # Recovery may expose earlier uncertainty; never conceal it in a new reference.
                    if connection.scalar(select(RUN.c.id).where(
                            RUN.c.execution_status.in_(("interrupted", "running"))).limit(1)):
                        raise CoverageError("EXPERIMENT_RECOVERY_REQUIRES_REVIEW")
                    reference = select_reference(connection, snapshot, self.now())
                    connection.execute(insert(RUN).values(
                        id=run_id, batch_id=batch_id, target_id=snapshot.target_id,
                        application_id=snapshot.application_id, started_at=self.now(),
                        execution_status="running", coverage_status="pending",
                        reference_run_id=reference.reference_run_id,
                        config_snapshot=snapshot.to_dict(), anomalies=[reference.diagnostic()]))
                output["overall_status"] = "running"
                self.checkpoint(output)
                started = self.monotonic()
                deadline = started + snapshot.config.target_deadline_seconds
                seen, first_pages = {}, {}
                stop, failure, source_stop, interrupted = "page_budget", None, False, False
                try:
                    for page in range(1, 11):
                        parsed = None
                        page_timing = []
                        for format in (FeedFormat.JSON, FeedFormat.XML):
                            stage = "attempt_intent"
                            self.guard()
                            session.assert_alive()
                            if output["requests"] >= 20:
                                stop, failure = "request_budget", "INCOMPLETE_FALLBACK"
                                break
                            if self.monotonic() >= deadline:
                                stop, failure = "target_deadline", "TARGET_DEADLINE"
                                break
                            with connection.begin():
                                attempt_id = connection.scalar(insert(ATTEMPT).values(
                                    run_id=run_id, request_number=output["requests"] + 1,
                                    page_number=page, format=format.value, attempt_number=1,
                                    started_at=self.now(), parsing_status="pending",
                                    persistence_status="pending").returning(ATTEMPT.c.id))
                            # Global and per-slot quota persists before dispatch, after DB intent.
                            self.reserve(page, format.value)
                            output["requests"] += 1
                            timing = {"request_number": output["requests"], "page": page,
                                      "format": format.value, "status": "reserved"}
                            output["attempt_timings"].append(timing)
                            self.checkpoint(output)  # Unknown sends retain conservative request cost.
                            stage = "request"
                            session.assert_alive()
                            before = self.monotonic()
                            response = self.transport.fetch(APP, page, format, snapshot.config, deadline=deadline)
                            elapsed = self.monotonic() - before
                            session.assert_alive()
                            stage = "response_metadata"
                            code, parsed, detail = self.helper._parse_response(response, format, snapshot.config)
                            fallback = parsed is not None and format is FeedFormat.JSON and not parsed.records
                            observed_at = self.now()
                            with connection.begin():
                                self.helper._complete_attempt(connection, attempt_id, response,
                                                              observed_at, parsed, code, fallback, detail)
                            timing.update(status="completed", transport_seconds=elapsed,
                                          http_status=response.status_code, code=code)
                            page_timing.append(timing)
                            self.checkpoint(output)
                            if code:
                                source_stop = code in {"HTTP_DENIED", "HTTP_RATE_LIMIT"}
                                stop = ("http_denied" if source_stop else "parse_error" if code in
                                        {"FEED_SCHEMA", "ENTRY_SCHEMA", "INVALID_TIMESTAMP"} else "transport_error")
                                failure = code
                                break
                            if not fallback:
                                break
                            parsed = None
                        if failure:
                            output["pages"].append({"page": page, "status": "incomplete",
                                                    "requests": len(page_timing)})
                            break
                        metrics, local, conflicts = _page_metrics(parsed.records, seen)
                        stage = "page_commit"
                        if self.monotonic() >= deadline:
                            stop, failure = "target_deadline", "TARGET_DEADLINE"
                            break
                        try:
                            persist_page(connection, run_id, attempt_id, parsed.records, observed_at)
                        except ReconciliationError as error:
                            session.assert_alive()
                            with connection.begin():
                                committed = connection.scalar(select(ATTEMPT.c.persistence_status).where(
                                    ATTEMPT.c.id == attempt_id)) == "committed"
                            if not committed:
                                if isinstance(error, ReconciliationPreconditionError):
                                    detail_code = error.code if error.code in _PRECONDITION_CODES else "PERSISTENCE_ERROR"
                                    output["failure_detail"] = {"stage": "page_commit", "code": detail_code}
                                    with connection.begin():
                                        row = connection.execute(select(ATTEMPT.c.anomalies).where(
                                            ATTEMPT.c.id == attempt_id)).scalar_one()
                                        connection.execute(ATTEMPT.update().where(ATTEMPT.c.id == attempt_id).values(
                                            anomalies=[*row, {"code": "PERSISTENCE_ERROR",
                                                              "precondition": detail_code, "stage": "page_commit"}]))
                                    output["pages"].append({"page": page, "status": "incomplete",
                                                            "requests": len(page_timing)})
                                    stop, failure = "db_error", "PERSISTENCE_ERROR"
                                    break
                                raise
                        metrics.update(page=page, status="valid", requests=len(page_timing))
                        if conflicts:
                            metrics.update(status="conflicting", invalidated_pages=sorted(
                                {first_pages[key] for key in conflicts if key in first_pages}))
                            stop = "consistency_anomaly"
                        elif not local:
                            metrics["status"] = "empty"
                            stop, failure = "empty_window_budget", "EMPTY_PAGE"
                        elif not metrics["novel_ids"]:
                            metrics["status"] = "duplicate_only"
                            stop, failure = "consistency_anomaly", "PAGE_DUPLICATE_ONLY"
                        output["pages"].append(metrics)
                        self.checkpoint(output)
                        for key, fields in local.items():
                            first_pages.setdefault(key, page)
                            seen.setdefault(key, fields)
                        if failure or conflicts:
                            break
                        # Fixed-depth acquisition deliberately does not inspect overlap to stop.
                except CoverageError:
                    stop, failure = "policy_stop", "OPERATOR_INTERRUPT"
                except (KeyboardInterrupt, SystemExit):
                    stop, failure, interrupted = "operator_interrupt", "OPERATOR_INTERRUPT", True
                stage = "finalize"
                session.assert_alive()
                result = self.helper._finalize(connection, snapshot, batch_id, run_id, reference,
                                               stop, failure, source_stop, interrupted)
                output.update(overall_status=result.execution_status, result=asdict(result),
                              total_monotonic_seconds=self.monotonic() - started,
                              finished_at=self.now().isoformat())
                self.checkpoint(output)
                return output
        except Exception as error:
            # No reconnect and no request replay after transaction/connection uncertainty.
            code = "DB_UNAVAILABLE"
            if stage in {"request", "response_metadata"}:
                self.spool.append(run_id, attempt_id, "REQUEST_OUTCOME_UNKNOWN", stage, self.now())
            self.spool.append(run_id, attempt_id, code, stage, self.now())
            output.update(overall_status="recovery_required", finished_at=self.now().isoformat(),
                          safe_error=type(error).__name__, recovery_required=True)
            self.checkpoint(output)
            return output

"""Sequential bounded Apple collection with a default-closed live policy.

Caller-supplied transport and spool are explicit dependencies. Live execution
requires an explicitly enabled scoped policy; synthetic behavior is unchanged.
Recovery owns the dedicated application-lock session;
all intent, metadata, reconciliation and finalization writes use that session.
No response/review text is retained in results, logs or diagnostic state.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from decimal import Decimal
import time
from uuid import UUID, uuid4

from sqlalchemy import func, insert, select, update

from .contracts import ConfigSnapshot, FeedFormat, RunMode
from .models import Application, CollectionTarget, CollectionRun, FetchAttempt, ReviewObservation
from .normalizer import HASH_CONTRACT_VERSION
from .parser import PARSER_VERSION, FeedParseError, parse_feed
from .reconcile import PageResult, ReconciliationError, persist_page
from .reference import (classify_coverage, comparison_eligibility, coverage_metrics,
                        diagnostic_codes, select_reference)
from .transport import FetchResponse, PILOT_APPLICATION_IDS

APPLICATION = Application.__table__
TARGET = CollectionTarget.__table__
RUN = CollectionRun.__table__
ATTEMPT = FetchAttempt.__table__
OBSERVATION = ReviewObservation.__table__
_TRANSPORT_CODES = frozenset({"HTTP_DENIED", "HTTP_RATE_LIMIT", "HTTP_NON_200", "TRANSPORT_TIMEOUT", "TRANSPORT_ERROR",
                              "BODY_LIMIT", "TARGET_DEADLINE", "INVALID_REQUEST", "TRANSPORT_CLOCK"})
_FAILURE_CODES = _TRANSPORT_CODES | {"DB_CONSTRAINT", "DB_UNAVAILABLE", "PAGE_PERSISTENCE_FAILED", "PERSISTENCE_ERROR",
    "FEED_SCHEMA", "ENTRY_SCHEMA", "INVALID_TIMESTAMP", "APPLICATION_SESSION_LOST", "OPERATOR_INTERRUPT"}


class ControllerError(RuntimeError):
    def __init__(self, code, *, diagnostics_durable=False):
        self.code = code
        self.diagnostics_durable = diagnostics_durable
        super().__init__(code)


@dataclass(frozen=True)
class RunResult:
    application_id: int
    target_id: int
    batch_id: UUID
    run_id: UUID | None
    execution_status: str | None
    coverage_status: str | None
    stop_reason: str
    reference_run_id: UUID | None = None
    comparison_eligible: bool = False
    committed_pages: int = 0
    request_count: int = 0
    reason_codes: tuple[str, ...] = ()
    source_stop: bool = False
    finalized: bool = True
    recovery_required: bool = False
    run_persisted: bool | None = True  # None: run-intent commit outcome unknown.

    @property
    def skipped(self):
        return self.run_id is None


class _Stop(Exception):
    def __init__(self, reason, code, *, source_stop=False):
        self.reason, self.code, self.source_stop = reason, code, source_stop


class Controller:
    def __init__(self, engine, transport, spool, *, now=None, monotonic=time.monotonic, live_policy=None):
        self.engine, self.transport, self.spool = engine, transport, spool
        self.now = now or (lambda: datetime.now(timezone.utc))
        self.monotonic = monotonic
        self.live_policy = live_policy

    def _time(self):
        instant = self.now()
        if not isinstance(instant, datetime) or instant.tzinfo is None or instant.utcoffset() is None:
            raise ControllerError("AWARE_CLOCK_REQUIRED")
        return instant.astimezone(timezone.utc)

    def _validate(self, snapshot, batch_id):
        if type(snapshot) is not ConfigSnapshot or not isinstance(batch_id, UUID):
            raise ControllerError("INVALID_RUN_CONTRACT")
        try:
            ConfigSnapshot.from_dict(snapshot.to_dict())
        except Exception:
            raise ControllerError("INVALID_RUN_CONTRACT") from None
        if snapshot.run_mode is RunMode.LIVE or self.live_policy is not None:
            from .live import LiveExecutionPolicy,ProjectExecutionPolicy
            if type(self.live_policy) not in (LiveExecutionPolicy,ProjectExecutionPolicy):
                raise ControllerError("LIVE_MODE_DISABLED")
            self.live_policy.validate(snapshot,batch_id,self._time(),runtime_engine=self.engine)
            check_controller=getattr(self.live_policy,"validate_controller",None)
            if check_controller is not None: check_controller(self.engine,self.transport)
        config = snapshot.config
        if (snapshot.source_application_id not in PILOT_APPLICATION_IDS
                or snapshot.parser_version != PARSER_VERSION or snapshot.hash_contract_version != HASH_CONTRACT_VERSION):
            raise ControllerError("UNSUPPORTED_PILOT_CONTRACT")
        if config.retry_count != 0:
            raise ControllerError("UNSUPPORTED_PILOT_LIMITS")

    def _validate_target(self, connection, snapshot):
        row = connection.execute(select(TARGET, APPLICATION.c.source, APPLICATION.c.source_application_id)
            .select_from(TARGET.join(APPLICATION, TARGET.c.application_id == APPLICATION.c.id))
            .where(TARGET.c.id == snapshot.target_id)).mappings().one_or_none()
        if row is None or any(row[name] != getattr(snapshot, name) for name in
                              ("application_id", "storefront", "sort_by", "source", "source_application_id")):
            raise ControllerError("TARGET_SNAPSHOT_IDENTITY_MISMATCH")
        for name in ("interval_hours", "min_pages", "max_pages", "min_overlap_count", "min_overlap_ratio",
                     "max_http_requests", "reference_max_age_hours"):
            expected = getattr(snapshot.config, name)
            if name == "min_overlap_ratio":
                expected = Decimal(str(expected))
            if row[name] != expected:
                raise ControllerError("TARGET_SNAPSHOT_SETTINGS_MISMATCH")
        if snapshot.run_mode is RunMode.LIVE:
            self.live_policy.validate_target(snapshot,row["enabled"],self._time())
        # Synthetic rehearsal explicitly permits the seeded disabled targets.
        # No UPDATE to enabled or any target configuration is issued here.

    def run_batch(self, snapshots, batch_id):
        snapshots = tuple(snapshots)
        if any(s.run_mode is RunMode.LIVE for s in snapshots):
            check_batch=getattr(self.live_policy,"validate_batch",None)
            if check_batch is None:
                raise ControllerError("LIVE_SINGLE_RUN_ONLY" if self.live_policy is not None else "LIVE_MODE_DISABLED")
            check_batch(snapshots,batch_id,self._time())
        if (len(snapshots) != 8 or {s.source_application_id for s in snapshots} != PILOT_APPLICATION_IDS
                or len({s.target_id for s in snapshots}) != 8 or len({s.application_id for s in snapshots}) != 8):
            raise ControllerError("EIGHT_PILOT_TARGETS_REQUIRED")
        for snapshot in snapshots:
            self._validate(snapshot, batch_id)
        results = []
        stopped = None
        for snapshot in snapshots:
            if stopped:
                results.append(RunResult(snapshot.application_id, snapshot.target_id, batch_id, None, None, None,
                    stopped, reason_codes=(stopped.upper(),), run_persisted=False))
                continue
            try:
                result = self.run_target(snapshot, batch_id)
            except ControllerError as exc:
                from .live import ProjectExecutionPolicy,PROJECT_STOP_CODES
                if type(self.live_policy) is not ProjectExecutionPolicy or exc.code not in PROJECT_STOP_CODES:
                    raise
                result=RunResult(snapshot.application_id,snapshot.target_id,batch_id,None,None,None,
                    "project_policy_stopped",reason_codes=(exc.code,),run_persisted=False)
                stopped="project_policy_stopped"
            results.append(result)
            if result.source_stop:
                stopped = "source_denied"
            elif result.recovery_required:
                stopped = "infrastructure_unavailable"
            elif result.stop_reason=="policy_stop":
                stopped = "project_policy_stopped"
        return tuple(results)

    def run_target(self, snapshot: ConfigSnapshot, batch_id: UUID) -> RunResult:
        self._validate(snapshot, batch_id)
        if snapshot.run_mode is RunMode.LIVE:
            self.live_policy.begin_execution(snapshot,batch_id,self._time(),runtime_engine=self.engine)
        try:
            return self._run_target(snapshot,batch_id)
        finally:
            finish=getattr(self.live_policy,"finish_execution",None)
            if snapshot.run_mode is RunMode.LIVE and finish is not None: finish(snapshot,batch_id)

    def _run_target(self,snapshot,batch_id):
        # Import lazily: constructing the controller performs no I/O and the
        # recovery layer owns session acquisition rather than duplicating it.
        from .recovery import application_session, recover_interrupted, replay_spool
        run_id = uuid4()  # Safe intended identity exists even before DB acquisition.
        run_persisted = False
        attempt_id = None
        pages = requests = 0
        reference = None
        stage = "lock"
        try:
            with application_session(self.engine, snapshot.application_id) as session:
                connection = session.connection
                session.assert_alive()
                with connection.begin():
                    self._validate_target(connection, snapshot)
                stage = "recovery"
                replay_spool(connection, snapshot.application_id, self.spool, self._time())
                recover_interrupted(connection, snapshot.application_id, self._time())
                session.assert_alive()
                started = self._time()
                duration = snapshot.config.target_deadline_seconds
                if snapshot.run_mode is RunMode.LIVE:
                    duration = min(duration,self.live_policy.remaining_seconds(started))
                deadline = self.monotonic() + duration
                stage = "run_intent"
                try:
                    with connection.begin():
                        self._validate_target(connection, snapshot)
                        check_identity=getattr(self.live_policy,"validate_run_identity",None)
                        if snapshot.run_mode is RunMode.LIVE and check_identity is not None:
                            check_identity(connection,snapshot,batch_id)
                        reference = select_reference(connection, snapshot, started)
                        initial = [reference.diagnostic()]
                        if reference.age_warning:
                            initial.append({"code": "REFERENCE_AGE_WARNING", "age_hours": reference.age_hours,
                                            "threshold_hours": snapshot.config.reference_max_age_hours})
                        run_persisted = None
                        connection.execute(insert(RUN).values(id=run_id, target_id=snapshot.target_id,
                            application_id=snapshot.application_id, batch_id=batch_id, started_at=started,
                            execution_status="running", coverage_status="pending", reference_run_id=reference.reference_run_id,
                            config_snapshot=snapshot.to_dict(), anomalies=initial))
                except Exception:
                    # A commit acknowledgement can fail with a driver
                    # transaction still open. Discard this backend before
                    # recovery's cleanup can execute any SQL/commit on it.
                    connection.invalidate()
                    raise
                run_persisted = True
                stop_reason, failure_code, source_stop, interrupted = "page_budget", None, False, False
                try:
                    for page_number in range(1, snapshot.config.max_pages + 1):
                        if requests >= snapshot.config.max_http_requests:
                            stop_reason = "request_budget"
                            break
                        if self.monotonic() >= deadline:
                            stop_reason = "target_deadline"
                            break
                        selected = None
                        for format in (FeedFormat.JSON, FeedFormat.XML):
                            stage = "attempt_intent"
                            attempt_id = None
                            session.assert_alive()
                            if requests >= snapshot.config.max_http_requests:
                                raise _Stop("request_budget", "INCOMPLETE_FALLBACK")
                            if self.monotonic() >= deadline:
                                raise _Stop("target_deadline", "TARGET_DEADLINE")
                            with connection.begin():
                                attempt_number = (connection.scalar(select(func.max(ATTEMPT.c.attempt_number)).where(
                                    ATTEMPT.c.run_id == run_id, ATTEMPT.c.page_number == page_number,
                                    ATTEMPT.c.format == format.value)) or 0) + 1
                                attempt_id = connection.scalar(insert(ATTEMPT).values(run_id=run_id,
                                    request_number=requests + 1, page_number=page_number, format=format.value,
                                    attempt_number=attempt_number, started_at=self._time(), parsing_status="pending",
                                    persistence_status="pending").returning(ATTEMPT.c.id))
                            requests += 1
                            stage = "request"
                            session.assert_alive()
                            try:
                                before_http=getattr(self.live_policy,"before_http",None)
                                if snapshot.run_mode is RunMode.LIVE and before_http is not None:
                                    before_http(snapshot,batch_id,self._time(),runtime_engine=self.engine,
                                                request_number=requests,page_number=page_number)
                                response = self.transport.fetch(snapshot.source_application_id, page_number,
                                    format, snapshot.config, deadline=deadline)
                            except (KeyboardInterrupt, SystemExit):
                                raise
                            except ControllerError as exc:
                                from .live import PROJECT_STOP_CODES
                                if exc.code not in PROJECT_STOP_CODES: raise
                                response=FetchResponse(None,b"",0,exc.code)
                            except TimeoutError:
                                response = FetchResponse(None, b"", 0, "TRANSPORT_TIMEOUT")
                            except Exception:
                                response = FetchResponse(None, b"", 0, "TRANSPORT_ERROR")
                            session.assert_alive()
                            stage = "response_metadata"
                            observed_at = self._time()
                            code, parsed, parse_detail = self._parse_response(response, format, snapshot.config)
                            fallback = parsed is not None and format is FeedFormat.JSON and not parsed.records
                            with connection.begin():
                                self._complete_attempt(connection, attempt_id, response, observed_at, parsed, code, fallback, parse_detail)
                            if code:
                                reason = ("http_denied" if code in {"HTTP_DENIED", "HTTP_RATE_LIMIT"} else
                                    "parse_error" if code in {"FEED_SCHEMA", "ENTRY_SCHEMA", "INVALID_TIMESTAMP"} else
                                    "target_deadline" if code in {"TARGET_DEADLINE","PROJECT_POLICY_OUTSIDE_VALIDITY"} else
                                    "policy_stop" if code.startswith("PROJECT_") else "transport_error")
                                raise _Stop(reason, code, source_stop=code in {"HTTP_DENIED", "HTTP_RATE_LIMIT"})
                            if fallback:
                                continue
                            selected = parsed, observed_at
                            break
                        parsed, observed_at = selected
                        stage = "page_commit"
                        if self.monotonic() >= deadline:
                            raise _Stop("target_deadline", "TARGET_DEADLINE")
                        session.assert_alive()
                        try:
                            page_result = persist_page(connection, run_id, attempt_id, parsed.records, observed_at)
                        except ReconciliationError as exc:
                            # Re-read the durable marker only on this live locked
                            # session; never reconnect or automatically replay.
                            session.assert_alive()
                            with connection.begin():
                                saved = connection.execute(select(ATTEMPT).where(ATTEMPT.c.id == attempt_id)).mappings().one()
                            if saved["persistence_status"] == "committed":
                                summary = next(item for item in saved["anomalies"] if item["code"] == "PAGE_SUMMARY")
                                page_result = PageResult(run_id, attempt_id, page_number,
                                    **{name: summary[name] for name in PageResult.__dataclass_fields__
                                       if name not in {"run_id", "attempt_id", "page_number", "replayed"}}, replayed=True)
                            else:
                                raise _Stop("db_error", exc.code if exc.code in _FAILURE_CODES else "PERSISTENCE_ERROR") from None
                        pages += 1
                        stage = "after_page_commit"
                        session.assert_alive()
                        with connection.begin():
                            metrics, caution, conflict = self._metrics(connection, run_id, snapshot, reference)
                        if metrics.thresholds_met and not caution and not conflict:
                            stop_reason = "overlap_met"
                            break
                except _Stop as stop:
                    stop_reason, failure_code, source_stop = stop.reason, stop.code, stop.source_stop
                except (KeyboardInterrupt, SystemExit):
                    stop_reason, failure_code, interrupted = "operator_interrupt", "OPERATOR_INTERRUPT", True
                if not pages and stop_reason == "target_deadline" and failure_code is None:
                    failure_code = "TARGET_DEADLINE"
                stage = "finalize"
                session.assert_alive()
                return self._finalize(connection, snapshot, batch_id, run_id, reference, stop_reason,
                                      failure_code, source_stop, interrupted)
        except ControllerError:
            raise
        except Exception as exc:
            code = getattr(exc, "code", None)
            if stage == "lock" and code in {"APPLICATION_BUSY", "APPLICATION_LOCKED", "APPLICATION_LOCK_BUSY", "LOCK_UNAVAILABLE"}:
                return RunResult(snapshot.application_id, snapshot.target_id, batch_id, None, None, None,
                                 "application_locked", reason_codes=("APPLICATION_LOCKED",), run_persisted=False)
            code = "APPLICATION_SESSION_LOST" if code in {"APPLICATION_SESSION_LOST", "SESSION_LOST"} else "DB_UNAVAILABLE"
            try:
                self.spool.append(run_id, attempt_id, code, "intent" if stage == "lock" else stage, self._time())
                if attempt_id is not None and stage in {"request", "response_metadata"}:
                    self.spool.append(run_id, attempt_id, "REQUEST_OUTCOME_UNKNOWN", stage, self._time())
            except Exception:
                raise ControllerError("DIAGNOSTIC_DURABILITY_FAILED", diagnostics_durable=False) from None
            return RunResult(snapshot.application_id, snapshot.target_id, batch_id, run_id, None, None,
                "db_error", reference_run_id=reference.reference_run_id if reference else None,
                committed_pages=pages, request_count=requests, reason_codes=(code,), finalized=False,
                recovery_required=True, run_persisted=run_persisted)

    def _parse_response(self, response, format, config):
        if not isinstance(response, FetchResponse):
            return "TRANSPORT_ERROR", None, None
        if response.status_code in {401, 403}:
            return "HTTP_DENIED", None, None
        if response.status_code == 429:
            return "HTTP_RATE_LIMIT", None, None
        if response.error_code is not None:
            from .live import PROJECT_STOP_CODES
            return response.error_code if response.error_code in _TRANSPORT_CODES | PROJECT_STOP_CODES else "TRANSPORT_ERROR", None, None
        if response.status_code != 200:
            return "HTTP_NON_200", None, None
        if type(response.body) is not bytes or type(response.response_bytes) is not int or response.response_bytes < 0:
            return "TRANSPORT_ERROR", None, None
        if len(response.body) > config.max_response_bytes or response.response_bytes > config.max_response_bytes:
            return "BODY_LIMIT", None, None
        try:
            return None, parse_feed(response.body, format), None
        except FeedParseError as exc:
            return exc.code.value, None, exc.diagnostic()

    def _complete_attempt(self, connection, attempt_id, response, at, parsed, code, fallback, parse_detail):
        status = getattr(response, "status_code", None)
        status = status if type(status) is int and 100 <= status <= 599 else None
        size = getattr(response, "response_bytes", None)
        size = size if type(size) is int and 0 <= size <= 2147483647 else None
        diagnostics = ([{"code": value.value} for value in parsed.codes] if parsed else [])
        if fallback:
            diagnostics.append({"code": "JSON_FALLBACK"})
        if code:
            diagnostics.append({"code": code, **(parse_detail or {})})
        connection.execute(update(ATTEMPT).where(ATTEMPT.c.id == attempt_id).values(
            finished_at=at, http_status=status, response_bytes=size, entry_count=parsed.entry_count if parsed else None,
            parsing_status="succeeded" if parsed else "failed" if code in {"FEED_SCHEMA", "ENTRY_SCHEMA", "INVALID_TIMESTAMP"} else "not_attempted",
            persistence_status="not_applicable" if code or fallback else "pending", error_codes=[code] if code else [], anomalies=diagnostics))

    def _metrics(self, connection, run_id, snapshot, reference):
        observations = list(connection.execute(select(OBSERVATION).where(OBSERVATION.c.run_id == run_id)).mappings())
        attempts = list(connection.execute(select(ATTEMPT).where(ATTEMPT.c.run_id == run_id,
            ATTEMPT.c.persistence_status == "committed")).mappings())
        caution = any(row["entry_count"] == 0 or "PAGE_DUPLICATE_ONLY" in diagnostic_codes(row["anomalies"]) for row in attempts)
        conflict = any(row["conflict_count"] for row in observations)
        return coverage_metrics((row["review_id"] for row in observations),
            reference.review_ids if reference.reference_run_id else None, len(attempts), snapshot.config), caution, conflict

    def _finalize(self, connection, snapshot, batch_id, run_id, reference, stop, failure, source_stop, interrupted):
        with connection.begin():
            run = dict(connection.execute(select(RUN).where(RUN.c.id == run_id).with_for_update()).mappings().one())
            pending = list(connection.execute(select(ATTEMPT).where(ATTEMPT.c.run_id == run_id,
                (ATTEMPT.c.parsing_status == "pending") | ATTEMPT.c.persistence_status.in_(["pending", "unknown"]))).mappings())
            if pending and not failure:
                failure, stop = "PERSISTENCE_ERROR", "db_error"
            for attempt in pending:
                known_parse = attempt["parsing_status"] == "succeeded"
                code = failure if known_parse else "REQUEST_OUTCOME_UNKNOWN"
                connection.execute(update(ATTEMPT).where(ATTEMPT.c.id == attempt["id"]).values(
                    finished_at=attempt["finished_at"] or self._time(),
                    parsing_status=attempt["parsing_status"] if known_parse else "not_attempted",
                    persistence_status="rolled_back" if known_parse else "not_applicable",
                    error_codes=list(dict.fromkeys([*attempt["error_codes"], code])),
                    anomalies=attempt["anomalies"] + [{"code": code, "completion_time_unknown": not known_parse}]))
            metrics, caution, conflict = self._metrics(connection, run_id, snapshot, reference)
            execution = ("interrupted" if interrupted else "partial" if (failure or conflict) and metrics.committed_pages
                         else "failed" if failure else "succeeded")
            if conflict and not failure:
                stop = "consistency_anomaly"
            coverage = classify_coverage(metrics, execution_status=execution, conflict=conflict,
                coverage_caution=caution, had_usable_history=reference.had_usable_history)
            finished = self._time()
            proposed = {**run, "execution_status": execution, "coverage_status": coverage, "finished_at": finished}
            eligibility = comparison_eligibility(connection, proposed)
            reasons = list(metrics.reason_codes)
            if failure:
                reasons.append(failure)
            if conflict:
                reasons.append("INTRA_RUN_CONFLICT")
            if caution:
                reasons.append("COVERAGE_CAUTION")
            if reference.age_warning:
                reasons.append("REFERENCE_AGE_WARNING")
            if eligibility.eligible and reference.reference_run_id is None:
                reasons.append("REFERENCE_CHAIN_RESTARTED" if reference.had_usable_history else "BASELINE_ANCHOR")
            reasons = list(dict.fromkeys(reasons))
            summary = {"code": "CONTROLLER_SUMMARY", **asdict(metrics), "reason_codes": reasons,
                "comparison_eligible": eligibility.eligible, "exclusion_reasons": list(eligibility.reasons),
                "coverage_caution": caution, "blocking_conflict": conflict,
                "low_volume_interpretation": "bounded_successful_window" if execution == "succeeded" else "measured_partial_only"}
            anomalies = [summary, *run["anomalies"]]
            if len(anomalies) > 100:
                anomalies = anomalies[:100]
                for item in anomalies:
                    if item.get("code") == "DIAGNOSTIC_TOTALS":
                        item["detail_truncated"] = True
            connection.execute(update(RUN).where(RUN.c.id == run_id).values(execution_status=execution,
                coverage_status=coverage, finished_at=finished, stop_reason=stop, anomalies=anomalies))
            request_count = connection.scalar(select(func.count()).select_from(ATTEMPT).where(ATTEMPT.c.run_id == run_id))
        return RunResult(snapshot.application_id, snapshot.target_id, batch_id, run_id, execution, coverage, stop,
            reference.reference_run_id, eligibility.eligible, metrics.committed_pages, request_count, tuple(reasons), source_stop)


__all__ = ["Controller", "ControllerError", "RunResult"]

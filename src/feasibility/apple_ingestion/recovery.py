"""Dedicated PostgreSQL application sessions and safe diagnostic recovery.

All DB helpers require an idle, same-session locked Connection and own short
transactions. No transaction survives a return to the caller/HTTP stage. Spools
are append-only and remain outside Git; replay uses per-attempt DB markers.
"""
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import stat
from uuid import UUID

from sqlalchemy import select, text, update
from psycopg.pq import TransactionStatus
from sqlalchemy.engine import Connection

from .contracts import ReasonCode
from .models import CollectionRun, FetchAttempt
from .reconcile import application_lock_key

RUN, ATTEMPT = CollectionRun.__table__, FetchAttempt.__table__
_SESSION_KEY = "apple_ingestion_application_session"
_SPOOL_CODES = frozenset(code.value for code in ReasonCode) | {
    "PAGE_PERSISTENCE_FAILED", "TRANSPORT_ERROR", "TARGET_DEADLINE", "APPLICATION_SESSION_LOST"}
_SPOOL_STAGES = frozenset({"intent", "attempt_intent", "request", "fetch", "http", "parse", "persist",
                           "persistence", "transport", "reconcile", "finalize", "run_finalize", "recovery",
                           "run_intent", "response_metadata", "page_commit", "after_page_commit"})
_MAX_SPOOL_BYTES = 10_000_000
_MAX_EVENT_KEYS = 100
_REPOSITORY = Path(__file__).resolve().parents[3]


class RecoveryError(RuntimeError):
    def __init__(self, code="RECOVERY_FAILED"):
        self.code = code
        super().__init__(code)


class ApplicationBusy(RecoveryError):
    def __init__(self):
        super().__init__("APPLICATION_BUSY")


class SessionLost(RecoveryError):
    def __init__(self):
        super().__init__("APPLICATION_SESSION_LOST")


class SpoolError(RecoveryError):
    def __init__(self):
        super().__init__("DIAGNOSTIC_SPOOL_UNAVAILABLE")


def _aware(at):
    if not isinstance(at, datetime) or at.tzinfo is None or at.utcoffset() is None:
        raise RecoveryError("AWARE_RECOVERY_TIME_REQUIRED")
    return at.astimezone(timezone.utc)


def _owns_lock(connection, application_id):
    value = application_lock_key(application_id) & ((1 << 64) - 1)
    return bool(connection.scalar(text("""SELECT EXISTS (
        SELECT 1 FROM pg_locks WHERE locktype='advisory' AND pid=pg_backend_pid()
        AND classid::bigint=:high AND objid::bigint=:low AND objsubid=1
        AND mode='ExclusiveLock' AND granted)"""), {"high": value >> 32, "low": value & 0xFFFFFFFF}))


def _idle(connection):
    if not isinstance(connection, Connection) or connection.closed or connection.invalidated:
        raise SessionLost()
    if connection.in_transaction():
        raise RecoveryError("IDLE_APPLICATION_CONNECTION_REQUIRED")
    if connection.dialect.name != "postgresql" or connection.dialect.driver != "psycopg":
        raise RecoveryError("POSTGRESQL_PSYCOPG_REQUIRED")
    if connection.engine.echo or not connection.engine.hide_parameters:
        raise RecoveryError("SAFE_SQL_LOGGING_REQUIRED")
    driver = connection.connection.driver_connection
    if driver.autocommit:
        raise RecoveryError("TRANSACTIONAL_CONNECTION_REQUIRED")
    if driver.info.transaction_status != TransactionStatus.IDLE:
        raise RecoveryError("IDLE_DRIVER_CONNECTION_REQUIRED")


@dataclass
class ApplicationSession:
    connection: Connection = field(repr=False)
    backend_pid: int
    application_id: int
    _driver: object = field(repr=False)
    _lost: bool = field(default=False, repr=False)

    def assert_alive(self):
        """Check the pinned backend and lock without reconnecting a lost handle."""
        try:
            if self._lost:
                raise SessionLost()
            _idle(self.connection)
            if self.connection.connection.driver_connection is not self._driver:
                raise SessionLost()
            with self.connection.begin():
                if (self.connection.scalar(text("SELECT pg_backend_pid()")) != self.backend_pid
                        or not _owns_lock(self.connection, self.application_id)):
                    raise SessionLost()
        except Exception:
            self._lost = True
            raise SessionLost() from None


@contextmanager
def application_session(engine, application_id):
    """Try one session advisory lock, pin its backend, release before pool return.

    Uses 5s lock and 10s statement timeouts. Session settings are restored on a
    healthy exit. Caller transactions left open are rolled back before unlock.
    """
    key = application_lock_key(application_id)
    connection, session, prior = None, None, None
    body_failed = False
    try:
        connection = engine.connect()
        _idle(connection)
        with connection.begin():
            prior = (connection.scalar(text("SHOW lock_timeout")),
                     connection.scalar(text("SHOW statement_timeout")))
            connection.execute(text("SELECT set_config('lock_timeout','5000ms',false)"))
            connection.execute(text("SELECT set_config('statement_timeout','10000ms',false)"))
            pid = connection.scalar(text("SELECT pg_backend_pid()"))
            if _owns_lock(connection, application_id):
                connection.invalidate()
                raise SessionLost()
            if not connection.scalar(text("SELECT pg_try_advisory_lock(:key)"), {"key": key}):
                raise ApplicationBusy()
        session = ApplicationSession(connection, pid, application_id, connection.connection.driver_connection)
        connection.info[_SESSION_KEY] = session
        session.assert_alive()
        try:
            yield session
        except BaseException:
            body_failed = True
            raise
    except (ApplicationBusy, RecoveryError):
        raise
    except Exception:
        if body_failed:
            raise
        raise SessionLost() from None
    finally:
        if connection is not None:
            cleanup_failed = False
            try:
                if connection.closed or connection.invalidated or (session is not None and session._lost):
                    raise SessionLost()
                driver = connection.connection.driver_connection
                if session is not None and driver is not session._driver:
                    raise SessionLost()
                connection.rollback()
                # A failing SQLAlchemy commit hook can close its logical
                # transaction while libpq still has uncommitted writes. Its
                # rollback() is then a no-op: explicitly clear the pinned raw
                # transaction before any liveness query can commit those writes.
                status = driver.info.transaction_status
                if status in (TransactionStatus.INTRANS, TransactionStatus.INERROR):
                    driver.rollback()
                elif status != TransactionStatus.IDLE:
                    raise SessionLost()
                if driver.info.transaction_status != TransactionStatus.IDLE:
                    raise SessionLost()
                if session is not None:
                    session.assert_alive()
                with connection.begin():
                    if session is not None and not connection.scalar(text("SELECT pg_advisory_unlock(:key)"), {"key": key}):
                        raise SessionLost()
                    if prior:
                        connection.execute(text("SELECT set_config('lock_timeout',:value,false)"), {"value": prior[0]})
                        connection.execute(text("SELECT set_config('statement_timeout',:value,false)"), {"value": prior[1]})
                connection.info.pop(_SESSION_KEY, None)
            except Exception:
                cleanup_failed = True
                connection.invalidate()  # Discard the backend; never reconnect it.
            finally:
                connection.close()
            if cleanup_failed and not body_failed:
                raise SessionLost() from None


def _locked(connection, application_id):
    _idle(connection)
    session = connection.info.get(_SESSION_KEY)
    if session is not None:
        if session.application_id != application_id:
            raise RecoveryError("APPLICATION_SESSION_MISMATCH")
        session.assert_alive()


def _detail(existing, item):
    """Bound diagnostics, preserve summaries and mandatory spool replay marker."""
    result = [dict(value) for value in existing]
    if item in result:
        return result
    totals = next((value for value in result if value.get("code") == "DIAGNOSTIC_TOTALS"), None)
    if totals is None:
        totals = {"code": "DIAGNOSTIC_TOTALS", "counts": {}, "detail_truncated": False}
        for value in result:
            if value.get("code") not in {"PAGE_SUMMARY", "RECONCILIATION_SUMMARY"}:
                code = value.get("code")
                totals["counts"][code] = totals["counts"].get(code, 0) + value.get("count", 1)
        result.insert(0, totals)
    else:
        totals["counts"] = dict(totals["counts"])
    code = item["code"]
    totals["counts"][code] = totals["counts"].get(code, 0) + 1
    result.append(item)
    while len(result) > 100:
        removable = next((i for i in range(len(result) - 1, -1, -1)
                          if result[i].get("code") not in {"DIAGNOSTIC_TOTALS", "PAGE_SUMMARY",
                              "RECONCILIATION_SUMMARY", "SPOOL_REPLAYED", "SPOOL_RUN_REPLAYED"}), None)
        if removable is None:
            raise RecoveryError("DIAGNOSTIC_BOUND_FAILED")
        result.pop(removable)
        totals["detail_truncated"] = True
    return result


def _resolve_attempt(row, recovered_at, *, code=None):
    if recovered_at < row["started_at"] or (row["finished_at"] is not None and recovered_at < row["finished_at"]):
        raise RecoveryError("RECOVERY_TIME_PRECEDES_ATTEMPT")
    values = {}
    if row["persistence_status"] != "committed":
        if row["persistence_status"] in {"pending", "unknown"}:
            values["persistence_status"] = "rolled_back" if row["parsing_status"] == "succeeded" else "not_applicable"
        if row["parsing_status"] == "pending":
            values["parsing_status"] = "not_attempted"
    if row["finished_at"] is None:
        values["finished_at"] = recovered_at
    # Judge uncertainty from the original durable row, before closing its intent.
    # Outage provenance and HTTP-outcome uncertainty are independent diagnostics.
    outcome_unknown = row["persistence_status"] != "committed" and (
        row["finished_at"] is None or (
            row["http_status"] is None and row["parsing_status"] == "pending"))
    codes = ([code] if code is not None else [])
    if outcome_unknown:
        codes.append("REQUEST_OUTCOME_UNKNOWN")
    if not codes:
        codes.append("PERSISTENCE_MARKER_ABSENT")
    values["error_codes"] = list(dict.fromkeys([*row["error_codes"], *codes]))
    anomalies = row["anomalies"]
    for diagnostic_code in dict.fromkeys(codes):
        anomalies = _detail(anomalies, {"code": diagnostic_code, "stage": "recovery",
            "completion_time_unknown": row["finished_at"] is None})
    values["anomalies"] = anomalies
    return values


def recover_interrupted(connection, application_id, recovered_at):
    """Finalize orphan running runs; preserve observations and committed markers.

    Returns tuple[UUID, ...]. Does not resume page numbers or select references.
    """
    instant = _aware(recovered_at)
    _locked(connection, application_id)
    try:
        with connection.begin():
            if not _owns_lock(connection, application_id):
                raise RecoveryError("APPLICATION_SESSION_LOCK_REQUIRED")
            runs = connection.execute(select(RUN).where(RUN.c.application_id == application_id,
                RUN.c.execution_status == "running").with_for_update()).mappings().all()
            for run in runs:
                if instant < run["started_at"]:
                    raise RecoveryError("RECOVERY_TIME_PRECEDES_RUN")
                attempts = connection.execute(select(ATTEMPT).where(ATTEMPT.c.run_id == run["id"])
                    .with_for_update()).mappings().all()
                for row in attempts:
                    if instant < row["started_at"] or (row["finished_at"] is not None and instant < row["finished_at"]):
                        raise RecoveryError("RECOVERY_TIME_PRECEDES_ATTEMPT")
                    if (row["finished_at"] is None or row["parsing_status"] == "pending"
                            or row["persistence_status"] in {"pending", "unknown"}):
                        connection.execute(update(ATTEMPT).where(ATTEMPT.c.id == row["id"]).values(
                            **_resolve_attempt(row, instant)))
                connection.execute(update(RUN).where(RUN.c.id == run["id"]).values(
                    execution_status="interrupted", coverage_status="indeterminate", finished_at=instant,
                    stop_reason="recovered_interrupted", anomalies=_detail(run["anomalies"],
                        {"code": "RUN_RECOVERED_INTERRUPTED", "at": instant.isoformat()})))
            return tuple(run["id"] for run in runs)
    except RecoveryError:
        raise
    except Exception:
        raise RecoveryError("DB_UNAVAILABLE") from None


class DiagnosticSpool:
    """0600 append-only JSONL, no symlink traversal, file+directory fsync.

    Constructor creates nothing. append permits enumerated code/stage, UUID run,
    positive attempt ID or None (run diagnostic), and aware timestamp only.
    Capacity is 10 MB; write/read/corruption failures are explicit SpoolError.
    """
    def __init__(self, path):
        self._path = Path(path)

    @property
    def path(self):
        """Configured path only; reading it creates or changes no file."""
        return self._path

    @staticmethod
    def _entry(run_id, attempt_id, code, stage, at):
        try:
            if type(run_id) is not UUID and type(run_id) is not str:
                raise ValueError
            run = str(UUID(str(run_id)))
            if attempt_id is not None and (type(attempt_id) is not int or attempt_id <= 0):
                raise ValueError
            if type(code) is not str or code not in _SPOOL_CODES or type(stage) is not str or stage not in _SPOOL_STAGES:
                raise ValueError
            timestamp = _aware(at).isoformat(timespec="microseconds").replace("+00:00", "Z")
            return dict(run_id=run, attempt_id=attempt_id, code=code, stage=stage, at=timestamp)
        except Exception:
            raise SpoolError() from None

    @contextmanager
    def _file(self, *, write):
        directory_fd, file_fd = None, None
        try:
            path = self._path
            if not path.is_absolute() or ".." in path.parts or path == _REPOSITORY or _REPOSITORY in path.parents:
                raise ValueError
            if any((parent / ".git").is_file() or (parent / ".git" / "HEAD").is_file() for parent in path.parents):
                raise ValueError
            directory_fd = os.open("/", os.O_RDONLY | os.O_DIRECTORY)
            for part in path.parent.parts[1:]:
                next_fd = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=directory_fd)
                os.close(directory_fd)
                directory_fd = next_fd
            flags = os.O_NOFOLLOW | os.O_NONBLOCK | (os.O_WRONLY | os.O_CREAT | os.O_APPEND if write else os.O_RDONLY)
            try:
                file_fd = os.open(path.name, flags, 0o600, dir_fd=directory_fd)
            except FileNotFoundError:
                if not write:
                    yield None, directory_fd
                    return
                raise
            info = os.fstat(file_fd)
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o600:
                raise ValueError
            fcntl.flock(file_fd, fcntl.LOCK_EX if write else fcntl.LOCK_SH)
            yield file_fd, directory_fd
        except Exception:
            raise SpoolError() from None
        finally:
            if file_fd is not None:
                os.close(file_fd)
            if directory_fd is not None:
                os.close(directory_fd)

    def append(self, run_id, attempt_id, code, stage, at):
        entry = self._entry(run_id, attempt_id, code, stage, at)
        line = (json.dumps(entry, separators=(",", ":"), allow_nan=False) + "\n").encode("utf-8")
        with self._file(write=True) as (fd, parent):
            if os.fstat(fd).st_size + len(line) > _MAX_SPOOL_BYTES:
                raise SpoolError()
            pending = memoryview(line)
            while pending:
                written = os.write(fd, pending)
                if written <= 0:
                    raise SpoolError()
                pending = pending[written:]
            os.fsync(fd)
            os.fsync(parent)

    def entries(self):
        try:
            with self._file(write=False) as (fd, _):
                if fd is None:
                    return ()
                if os.fstat(fd).st_size > _MAX_SPOOL_BYTES:
                    raise SpoolError()
                with os.fdopen(os.dup(fd), "rb") as handle:
                    data = handle.read(_MAX_SPOOL_BYTES + 1)
            if data and not data.endswith(b"\n"):
                raise SpoolError()
            result = []
            def unique(pairs):
                result = {}
                for key, value in pairs:
                    if key in result:
                        raise SpoolError()
                    result[key] = value
                return result
            for line in data.splitlines():
                value = json.loads(line, object_pairs_hook=unique)
                if type(value) is not dict or set(value) != {"run_id", "attempt_id", "code", "stage", "at"} or type(value["at"]) is not str:
                    raise SpoolError()
                canonical = self._entry(value["run_id"], value["attempt_id"], value["code"], value["stage"],
                                        datetime.fromisoformat(value["at"].replace("Z", "+00:00")))
                if canonical != value:
                    raise SpoolError()
                result.append(canonical)
            return tuple(result)
        except Exception:
            raise SpoolError() from None


def replay_spool(connection, application_id, spool, recovered_at):
    """Import diagnostics once per attempt (or run-only group), under app lock.

    Returns count of groups with new events. Each marker stores at most 100 safe
    SHA-256 event keys; overflow fails the whole transaction explicitly. Keep the
    spool file for other applications
    and crash-safe replay. Missing/foreign runs are left untouched for later.
    Never invent HTTP status/body/observations or overwrite a committed marker.
    """
    instant = _aware(recovered_at)
    _locked(connection, application_id)
    entries = spool.entries()
    groups = {}
    for entry in entries:
        if datetime.fromisoformat(entry["at"].replace("Z", "+00:00")) > instant:
            raise RecoveryError("RECOVERY_TIME_PRECEDES_DIAGNOSTIC")
        groups.setdefault((UUID(entry["run_id"]), entry["attempt_id"]), []).append(entry)
    try:
        with connection.begin():
            if not _owns_lock(connection, application_id):
                raise RecoveryError("APPLICATION_SESSION_LOCK_REQUIRED")
            imported = 0
            for (run_id, attempt_id), events in groups.items():
                run = connection.execute(select(RUN).where(RUN.c.id == run_id,
                    RUN.c.application_id == application_id).with_for_update()).mappings().one_or_none()
                if run is None:
                    continue
                if instant < run["started_at"]:
                    raise RecoveryError("RECOVERY_TIME_PRECEDES_RUN")
                if attempt_id is None:
                    row, marker_code = run, "SPOOL_RUN_REPLAYED"
                else:
                    row = connection.execute(select(ATTEMPT).where(ATTEMPT.c.id == attempt_id,
                        ATTEMPT.c.run_id == run_id).with_for_update()).mappings().one_or_none()
                    if row is None:
                        raise RecoveryError("SPOOL_ATTEMPT_RUN_MISMATCH")
                    marker_code = "SPOOL_REPLAYED"
                marker = next((item for item in row["anomalies"] if item.get("code") == marker_code), {})
                prior_keys = set(marker.get("event_keys", []))
                new_events = {}
                for event in events:
                    key = hashlib.sha256(json.dumps(event, sort_keys=True,
                        separators=(",", ":")).encode("utf-8")).hexdigest()
                    if key not in prior_keys:
                        new_events[key] = event
                if not new_events:
                    continue
                if len(prior_keys | new_events.keys()) > _MAX_EVENT_KEYS:
                    raise RecoveryError("SPOOL_EVENT_CAPACITY")
                values = {} if attempt_id is None else _resolve_attempt(
                    row, instant, code=next(iter(new_events.values()))["code"])
                anomalies = [item for item in values.get("anomalies", row["anomalies"])
                             if item.get("code") != marker_code]
                if attempt_id is not None:
                    values["error_codes"] = list(dict.fromkeys([*values["error_codes"],
                        *(event["code"] for event in new_events.values())]))
                for event in new_events.values():
                    anomalies = _detail(anomalies, {"code": event["code"],
                        "stage": event["stage"], "at": event["at"]})
                marker = {"code": marker_code, "event_keys": sorted(prior_keys | new_events.keys())}
                values["anomalies"] = _detail(anomalies, marker)
                if attempt_id is None:
                    connection.execute(update(RUN).where(RUN.c.id == run_id).values(**values))
                else:
                    connection.execute(update(ATTEMPT).where(ATTEMPT.c.id == attempt_id).values(**values))
                imported += 1
            return imported
    except RecoveryError:
        raise
    except Exception:
        raise RecoveryError("DB_UNAVAILABLE") from None

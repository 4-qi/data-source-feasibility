"""Single-use Duolingo feasibility probe; no production controller or DB writes.

Non-contiguous pages are private diagnostic evidence, never collection_run rows.
Request intents and results are checkpointed before another request is allowed.
"""
from dataclasses import replace
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import stat
import time
from uuid import uuid4

from .contracts import FeedFormat, IngestionConfig
from .normalizer import HASH_CONTRACT_VERSION, canonical_fields, fingerprint
from .parser import FeedParseError, PARSER_VERSION, parse_feed
from .transport import BoundedTransport

APP_ID = "570060128"
PAGES = (1, 5, 6, 7, 8, 9, 10)


class ProbeError(ValueError):
    """Fixed code only; never include response text or unsafe exceptions."""


def prefix_validity(pages, depth):
    """Analytical completeness only, independent of whole-run execution status."""
    required = {number for number in range(1, depth + 1)}
    present = {row["page"] for row in pages if row["status"] == "valid"}
    affected = set()
    for row in pages:
        affected.update(row.get("invalidated_pages", []))
    return required <= present and not required & affected


class Evidence:
    def __init__(self, directory):
        self.directory = Path(directory)
        if (not self.directory.is_absolute() or self.directory.is_symlink()
                or self.directory.resolve() != self.directory
                or not self.directory.is_dir()
                or stat.S_IMODE(self.directory.stat().st_mode) != 0o700
                or self.directory.stat().st_uid != os.getuid()
                or any((p / ".git").is_file() or (p / ".git" / "HEAD").is_file()
                       for p in self.directory.parents)):
            raise ProbeError("PRIVATE_EVIDENCE_DIRECTORY_REQUIRED")
        self.path = self.directory / "probe.json"

    def save(self, value, *, exclusive=False):
        destination = self.path if exclusive else self.directory / (uuid4().hex + ".tmp")
        fd = None
        try:
            fd = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
            with os.fdopen(fd, "w") as handle:
                fd = None
                json.dump(value, handle, ensure_ascii=True, indent=2)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            if not exclusive:
                os.replace(destination, self.path)
            directory_fd = os.open(self.directory, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
        except FileExistsError:
            raise ProbeError("PROBE_ALREADY_RESERVED") from None
        except OSError:
            raise ProbeError("EVIDENCE_UNAVAILABLE") from None
        finally:
            if fd is not None:
                os.close(fd)


def _utc():
    return datetime.now(timezone.utc).isoformat()


def _page_metrics(records, seen):
    # Canonical text stays in memory only; persisted records carry IDs/hashes.
    local = {}
    projections = []
    conflicts = set()
    times = []
    duplicate_count = 0
    cross_duplicates = 0
    within_duplicates = 0
    for position, record in enumerate(records, 1):
        fields = canonical_fields(record)
        key = record.source_review_id
        previous = local.get(key, seen.get(key))
        if previous is not None:
            duplicate_count += 1
            cross_duplicates += int(key in seen)
            within_duplicates += int(key in local)
            if previous != fields:
                conflicts.add(key)
        local.setdefault(key, fields)
        content_hash, metadata_hash = fingerprint(record)
        projections.append({"position": position, "review_id": key,
                            "content_hash": content_hash.hex(), "metadata_hash": metadata_hash.hex(),
                            "source_updated_at": fields[-1]})
        if record.source_updated_at is not None:
            times.append(record.source_updated_at)
    ids = set(local)
    delta = ids - set(seen)
    metrics = {
        "entry_count": len(records), "distinct_ids": len(ids), "novel_ids": len(delta),
        "duplicate_occurrences": duplicate_count, "cross_page_duplicate_occurrences": cross_duplicates,
        "same_page_duplicate_occurrences": within_duplicates, "conflicting_ids": len(conflicts),
        "source_timestamp_missing": sum(record.source_updated_at is None for record in records),
        "source_timestamp_min": min(times).isoformat() if times else None,
        "source_timestamp_max": max(times).isoformat() if times else None,
        "source_timestamp_order_inversions": sum(a < b for a, b in zip(times, times[1:])),
        "records": projections,
    }
    return metrics, local, conflicts


def run_probe(session, directory, *, max_requests=14, clock=time.monotonic, sleep=time.sleep,
              preflight=None):
    """Exactly one observation, fixed app/page order, no retry or background job.

    Caller supplies a session and optional SELECT-only isolated DB preflight.
    Refuse any existing reservation, including a completed or uncertain probe.
    """
    if type(max_requests) is not int or not 1 <= max_requests <= 14:
        raise ProbeError("INVALID_REQUEST_BUDGET")
    evidence = Evidence(directory)
    lock_fd = os.open(evidence.directory / "operator.lock",
                      os.O_WRONLY | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    with os.fdopen(lock_fd, "w") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise ProbeError("PROBE_BUSY") from None
        if preflight is not None:
            preflight()
        value = {
            "schema_version": "apple-pagination-probe/1", "probe_id": str(uuid4()),
            "app_id": APP_ID, "storefront": "us", "sort": "mostrecent",
            "requested_pages": list(PAGES), "started_at": _utc(), "status": "running",
            "parser_version": PARSER_VERSION, "hash_contract_version": HASH_CONTRACT_VERSION,
            "implementation_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "request_budget": max_requests,
            "attempts": [], "pages": [], "stop_reason": None,
        }
        config = replace(IngestionConfig(), max_pages=10, max_http_requests=max_requests)
        value["config"] = config.to_dict()
        evidence.save(value, exclusive=True)
        start = clock()
        deadline = start + config.target_deadline_seconds
        transport = BoundedTransport(session, clock=clock, sleep=sleep)
        seen = {}
        page_sets = []
        first_pages = {}
        reason = None
        for page in PAGES:
            selected = None
            for format in (FeedFormat.JSON, FeedFormat.XML):
                if len(value["attempts"]) >= max_requests:
                    reason = "request_budget"
                    break
                if clock() >= deadline:
                    reason = "target_deadline"
                    break
                attempt = {"request_number": len(value["attempts"]) + 1, "page": page,
                           "format": format.value, "started_at": _utc(), "status": "intent"}
                value["attempts"].append(attempt)
                evidence.save(value)  # No HTTP unless the intent is durable.
                before = clock()
                response = transport.fetch(APP_ID, page, format, config, deadline=deadline)
                attempt.update(finished_at=_utc(), duration_seconds=clock() - before,
                               http_status=response.status_code, response_bytes=response.response_bytes)
                if response.error_code or response.status_code != 200:
                    attempt.update(status="transport_failure", code=response.error_code or "HTTP_NON_200")
                    reason = attempt["code"]
                else:
                    try:
                        selected = parse_feed(response.body, format)
                    except FeedParseError as error:
                        attempt.update(status="parse_failure", code=error.code.value,
                                       diagnostic=error.diagnostic())
                        reason = "parse_error"
                    else:
                        attempt.update(status="parsed", entry_count=selected.entry_count,
                                       codes=[code.value for code in selected.codes])
                evidence.save(value)
                if reason:
                    break
                if selected.records or format is FeedFormat.XML:
                    break
                selected = None  # Valid empty JSON permits exactly one XML attempt.
            if reason:
                value["pages"].append({"page": page, "status": "incomplete"})
                break
            metrics, local, conflicts = _page_metrics(selected.records, seen)
            ids = set(local)
            metrics.update(page=page, format=format.value, status="valid",
                           repeated_page_ids=any(ids == previous for previous in page_sets))
            if not ids:
                metrics["status"] = "empty"
                reason = "empty_page"
            elif conflicts:
                metrics.update(status="conflicting",
                               invalidated_pages=sorted({first_pages[key] for key in conflicts if key in first_pages}))
                reason = "conflicting_occurrence"
            elif page >= 6 and metrics["novel_ids"] == 0:
                metrics["status"] = "duplicate_only"
                reason = "duplicate_only_deep_page"
            value["pages"].append(metrics)
            evidence.save(value)
            if reason:
                break
            for key in local:
                first_pages.setdefault(key, page)
                seen.setdefault(key, local[key])
            page_sets.append(ids)
        value.update(status="completed" if reason is None else "stopped",
                     stop_reason=reason or "requested_pages_completed", finished_at=_utc(),
                     total_seconds=clock() - start, requests=len(value["attempts"]),
                     valid_pages=[row["page"] for row in value["pages"] if row["status"] == "valid"],
                     distinct_ids=len(seen), production_reference_eligible=False)
        evidence.save(value)
        return public_summary(value)


def public_summary(value):
    """Only aggregate outcomes; private ID projections are omitted."""
    return {**{key: value[key] for key in ("probe_id", "status", "stop_reason", "requests",
                                          "valid_pages", "distinct_ids", "started_at", "finished_at")},
            "pages": [{key: field for key, field in row.items() if key != "records"}
                      for row in value["pages"]],
            "attempts": value["attempts"]}

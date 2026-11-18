"""File-backed seven-slot operator state; no timer, daemon or automatic retries."""
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import fcntl
import hashlib
import json
import os
import re
from pathlib import Path
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

from .coverage_runner import CoverageError
from .pagination_probe import Evidence

ROOT = Path(__file__).resolve().parents[3]
WINDOW = timedelta(minutes=10)


def encode(value):
    if isinstance(value, (datetime, UUID)):
        return str(value)
    raise TypeError


def save_json(path, value, *, exclusive=False):
    path = Path(path)
    destination = path if exclusive else path.parent / (uuid4().hex + ".tmp")
    fd = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "w") as handle:
        json.dump(value, handle, indent=2, default=encode)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    if not exclusive:
        os.replace(destination, path)
    fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def source_hash():
    digest = hashlib.sha256()
    for folder in ("src/feasibility/apple_ingestion", "migrations"):
        for path in sorted((ROOT / folder).rglob("*.py")):
            digest.update(path.relative_to(ROOT).as_posix().encode())
            digest.update(path.read_bytes())
    return digest.hexdigest()


def new_plan(start_local, database, *, now=None):
    start = datetime.fromisoformat(start_local)
    if start.tzinfo is not None:
        raise CoverageError("LOCAL_SCHEDULE_EXPECTED")
    zone = ZoneInfo("America/Los_Angeles")
    if start.hour not in (9, 21) or start.minute or start.second or start.microsecond:
        raise CoverageError("INVALID_COLLECTION_TIME")
    slots = []
    for index in range(7):
        instant = (start + timedelta(hours=12*index)).replace(tzinfo=zone)
        utc = instant.astimezone(timezone.utc)
        slots.append({"index": index, "planned_local": instant.isoformat(),
                      "planned_utc": utc.isoformat(), "status": "planned",
                      "requests": 0, "run_id": None, "batch_id": None, "actual_start_utc": None})
    at = now or datetime.now(timezone.utc)
    if datetime.fromisoformat(slots[0]["planned_utc"]) <= at:
        raise CoverageError("FUTURE_SCHEDULE_REQUIRED")
    if any((datetime.fromisoformat(b["planned_utc"]) -
            datetime.fromisoformat(a["planned_utc"])) != timedelta(hours=12)
           for a, b in zip(slots, slots[1:])):
        raise CoverageError("DST_SCHEDULE_REQUIRES_REVIEW")
    if not re.fullmatch(r"apple_coverage_main_[a-z0-9_]+", database):
        raise CoverageError("EXPERIMENT_DATABASE_REQUIRED")
    return {"schema_version": "apple-coverage-study/1", "study_id": str(uuid4()),
            "app_id": "570060128", "database": database, "enabled": False,
            "retired": False, "hold": False, "clock_verified": False,
            "source_sha256": source_hash(), "max_requests": 140,
            "per_observation_max_requests": 20, "slots": slots}


class StudyStore:
    def __init__(self, directory):
        Evidence(directory)  # Reuse the private-directory boundary.
        self.directory = Path(directory)
        self.path = self.directory / "study.json"

    @contextmanager
    def locked(self):
        fd = os.open(self.directory / "study.lock",
                     os.O_WRONLY | os.O_CREAT | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, "w") as handle:
            try:
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise CoverageError("EXPERIMENT_BUSY") from None
            yield self

    def load(self):
        def require(condition):
            if not condition:
                raise ValueError
        try:
            value = json.loads(self.path.read_text())
            require(value["schema_version"] == "apple-coverage-study/1")
            require(value["app_id"] == "570060128")
            require(re.fullmatch(r"apple_coverage_main_[a-z0-9_]+", value["database"]))
            require(value["max_requests"] == 140 and value["per_observation_max_requests"] == 20)
            require(len(value["slots"]) == 7)
            require(re.fullmatch(r"[0-9a-f]{64}", value["source_sha256"]))
            for name in ("enabled", "retired", "hold", "clock_verified"):
                require(type(value[name]) is bool)
            previous = None
            for index, slot in enumerate(value["slots"]):
                require(slot["index"] == index)
                require(type(slot["requests"]) is int and 0 <= slot["requests"] <= 20)
                require(slot["status"] in {"planned","running","completed","failed","missed","interrupted"})
                planned = datetime.fromisoformat(slot["planned_utc"])
                local = datetime.fromisoformat(slot["planned_local"])
                require(planned.utcoffset() == timedelta(0) and planned == local)
                require(local.utcoffset() == planned.astimezone(ZoneInfo("America/Los_Angeles")).utcoffset())
                require(local.hour in (9,21) and local.minute == local.second == local.microsecond == 0)
                require(previous is None or planned-previous == timedelta(hours=12))
                previous = planned
            require(sum(slot["requests"] for slot in value["slots"]) <= 140)
        except (AssertionError, KeyError, TypeError, ValueError):
            raise CoverageError("INVALID_STUDY_MANIFEST") from None
        return value

    def save(self, value):
        save_json(self.path, value)

    def verify_source(self):
        value = self.load()
        if value["source_sha256"] != source_hash():
            raise CoverageError("EXPERIMENT_SOURCE_CHANGED")
        return value

    def enabled(self, *, at=None):
        value = self.verify_source()
        now = at or datetime.now(timezone.utc)
        if (not value["enabled"] or value["retired"] or value["hold"]
                or not value["clock_verified"]):
            raise CoverageError("EXPERIMENT_DISABLED")
        start = datetime.fromisoformat(value["slots"][0]["planned_utc"])
        end = datetime.fromisoformat(value["slots"][-1]["planned_utc"]) + WINDOW + timedelta(seconds=900)
        if not start <= now < end:
            raise CoverageError("EXPERIMENT_OUTSIDE_WINDOW")
        return value

    def reserve_slot(self, *, at=None):
        now = at or datetime.now(timezone.utc)
        value = self.enabled(at=now)
        selected = None
        for slot in value["slots"]:
            planned = datetime.fromisoformat(slot["planned_utc"])
            if slot["status"] == "running":
                value["hold"] = True
                self.save(value)
                raise CoverageError("EXPERIMENT_INTERRUPTED_REQUIRES_REVIEW")
            if slot["status"] != "planned":
                continue
            if now >= planned + WINDOW:
                slot.update(status="missed", detected_at_utc=now.isoformat())
            elif planned <= now:
                selected = slot
        if selected is None:
            self.save(value)
            return None
        selected.update(status="running", actual_start_utc=now.isoformat(),
                        run_id=str(uuid4()), batch_id=str(uuid4()))
        self.save(value)
        return selected

    def reserve_request(self, index, page, format, *, at=None):
        value = self.enabled(at=at)
        slot = value["slots"][index]
        if (slot["status"] != "running" or not 1 <= page <= 10 or format not in ("json", "xml")
                or slot["requests"] >= 20 or sum(s["requests"] for s in value["slots"]) >= 140):
            raise CoverageError("EXPERIMENT_REQUEST_BUDGET")
        slot["requests"] += 1
        self.save(value)

    def finish(self, index, output):
        value = self.load()
        slot = value["slots"][index]
        slot["status"] = "completed" if output["overall_status"] == "succeeded" else "failed"
        slot["finished_utc"] = datetime.now(timezone.utc).isoformat()
        value["hold"] = value["hold"] or slot["status"] != "completed"
        self.save(value)

    def maintenance(self, *, at=None):
        now = at or datetime.now(timezone.utc)
        value = self.load()
        if not value["enabled"] or value["retired"]:
            return value
        for slot in value["slots"]:
            if now >= datetime.fromisoformat(slot["planned_utc"]) + WINDOW and slot["status"] == "planned":
                slot.update(status="missed", detected_at_utc=now.isoformat())
            if slot["status"] == "running":
                slot["status"] = "interrupted"
                value["hold"] = True
        self.save(value)
        return value

    def retire(self):
        value = self.load()
        if value["slots"][-1]["status"] in ("planned", "running"):
            raise CoverageError("EXPERIMENT_NOT_TERMINAL")
        value.update(enabled=False, retired=True)
        self.save(value)

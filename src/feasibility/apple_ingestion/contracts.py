"""Validated value contracts; no parsing, hashing, reference selection or I/O.

A snapshot records technical provenance. Optional historical document
references are metadata, not a grant of access or an execution prerequisite. Frozen value objects contain no mutable nested collections.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, fields
from datetime import datetime
from enum import Enum
import math
from typing import Any, Mapping


class ContractError(ValueError):
    """Invalid contract input (messages contain field names, not review text)."""


class ExecutionStatus(str, Enum):
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    PARTIAL = "partial"
    FAILED = "failed"
    INTERRUPTED = "interrupted"


class CoverageStatus(str, Enum):
    PENDING = "pending"
    BASELINE = "baseline"
    OVERLAP_SUFFICIENT = "overlap_sufficient"
    OVERLAP_INSUFFICIENT = "overlap_insufficient"
    NO_REFERENCE = "no_reference"
    EMPTY_WINDOW = "empty_window"
    INDETERMINATE = "indeterminate"


class ComparisonEligibility(str, Enum):
    """Independent of coverage and reference age; selection is a later phase."""
    PENDING = "pending"
    ELIGIBLE = "eligible"
    INELIGIBLE = "ineligible"


class ParsingStatus(str, Enum):
    PENDING = "pending"
    NOT_ATTEMPTED = "not_attempted"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class PersistenceStatus(str, Enum):
    PENDING = "pending"
    NOT_APPLICABLE = "not_applicable"
    COMMITTED = "committed"
    ROLLED_BACK = "rolled_back"
    UNKNOWN = "unknown"


class FirstAction(str, Enum):
    NEW = "new"
    UNCHANGED = "unchanged"
    CHANGED = "changed"


class RunMode(str, Enum):
    SYNTHETIC = "synthetic"
    LIVE = "live"


class FeedFormat(str, Enum):
    JSON = "json"
    XML = "xml"


class ReasonCode(str, Enum):
    HTTP_DENIED = "HTTP_DENIED"
    HTTP_RATE_LIMIT = "HTTP_RATE_LIMIT"
    HTTP_NON_200 = "HTTP_NON_200"
    TRANSPORT_TIMEOUT = "TRANSPORT_TIMEOUT"
    BODY_LIMIT = "BODY_LIMIT"
    FEED_SCHEMA = "FEED_SCHEMA"
    ENTRY_SCHEMA = "ENTRY_SCHEMA"
    INVALID_TIMESTAMP = "INVALID_TIMESTAMP"
    JSON_ENTRY_ABSENT = "JSON_ENTRY_ABSENT"
    EMPTY_PAGE = "EMPTY_PAGE"
    INTRA_RUN_CONFLICT = "INTRA_RUN_CONFLICT"
    PAGE_DUPLICATE_ONLY = "PAGE_DUPLICATE_ONLY"
    DB_CONSTRAINT = "DB_CONSTRAINT"
    DB_UNAVAILABLE = "DB_UNAVAILABLE"
    REQUEST_OUTCOME_UNKNOWN = "REQUEST_OUTCOME_UNKNOWN"
    DETAIL_TRUNCATED = "DETAIL_TRUNCATED"
    REFERENCE_AGE_WARNING = "REFERENCE_AGE_WARNING"
    REFERENCE_CHAIN_RESTARTED = "REFERENCE_CHAIN_RESTARTED"
    OBSERVABLE_WINDOW_BELOW_COUNT_THRESHOLD = "OBSERVABLE_WINDOW_BELOW_COUNT_THRESHOLD"
    REFERENCE_WINDOW_BELOW_COUNT_THRESHOLD = "REFERENCE_WINDOW_BELOW_COUNT_THRESHOLD"
    LOW_ID_OVERLAP_COUNT = "LOW_ID_OVERLAP_COUNT"
    LOW_ID_OVERLAP_RATIO = "LOW_ID_OVERLAP_RATIO"
    MIN_LOGICAL_PAGES_NOT_MET = "MIN_LOGICAL_PAGES_NOT_MET"


class ReferenceExclusionReason(str, Enum):
    """Candidate defects; coverage insufficiency and age are not exclusions."""
    EXECUTION_NOT_SUCCEEDED = "EXECUTION_NOT_SUCCEEDED"
    EMPTY_OBSERVATIONS = "EMPTY_OBSERVATIONS"
    UNRESOLVED_ATTEMPTS = "UNRESOLVED_ATTEMPTS"
    PARSING_DEFECT = "PARSING_DEFECT"
    PERSISTENCE_DEFECT = "PERSISTENCE_DEFECT"
    IDENTITY_DEFECT = "IDENTITY_DEFECT"
    INCONSISTENT_OBSERVATIONS = "INCONSISTENT_OBSERVATIONS"
    INCOMPATIBLE_CONTRACT = "INCOMPATIBLE_CONTRACT"
    RUN_MODE_MISMATCH = "RUN_MODE_MISMATCH"
    TARGET_MISMATCH = "TARGET_MISMATCH"
    NOT_FINISHED_EARLIER = "NOT_FINISHED_EARLIER"


def _text(name: str, value: Any, *, optional: bool = False,
          nonblank: bool = True) -> None:
    if optional and value is None:
        return
    if type(value) is not str or (nonblank and not value.strip()):
        raise ContractError(f"{name} must be {'nullable ' if optional else ''}text"
                            + (" and nonblank" if nonblank else ""))
    # NUL cannot be represented in PostgreSQL text. Do not otherwise alter text.
    if "\x00" in value:
        raise ContractError(f"{name} must not contain NUL")


def _integer(name: str, value: Any, minimum: int = 1) -> None:
    if type(value) is not int or value < minimum:
        raise ContractError(f"{name} must be an integer >= {minimum}")


def _number(name: str, value: Any, *, minimum: float = 0,
            positive: bool = False) -> None:
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ContractError(f"{name} must be a finite number")
    if value < minimum or (positive and value == minimum):
        raise ContractError(f"{name} is outside its allowed range")


def _exact_keys(value: Any, cls: type) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ContractError(f"{cls.__name__} must be an object")
    expected = {field.name for field in fields(cls)}
    if set(value) != expected:
        raise ContractError(f"{cls.__name__} has missing or unknown fields")
    return dict(value)


@dataclass(frozen=True)
class ReviewRecord:
    source_review_id: str
    title: str | None
    body: str
    rating: int
    application_version: str | None = None
    source_updated_at: datetime | None = None

    def __post_init__(self) -> None:
        _text("source_review_id", self.source_review_id)
        _text("title", self.title, optional=True, nonblank=False)
        _text("body", self.body, nonblank=False)
        _integer("rating", self.rating)
        if self.rating > 5:
            raise ContractError("rating must be between 1 and 5")
        _text("application_version", self.application_version,
              optional=True, nonblank=False)
        if self.source_updated_at is not None:
            value = self.source_updated_at
            if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
                raise ContractError("source_updated_at must be an aware datetime or null")


@dataclass(frozen=True)
class IngestionConfig:
    """Effective settings, not runtime permission. Defaults are the pilot policy."""
    interval_hours: int = 24
    min_pages: int = 2
    max_pages: int = 5
    min_overlap_count: int = 20
    min_overlap_ratio: float = 0.20
    max_http_requests: int = 10
    retry_count: int = 0
    global_spacing_seconds: float = 2.0
    connect_timeout_seconds: float = 10.0
    read_timeout_seconds: float = 25.0
    max_response_bytes: int = 2_000_000
    target_deadline_seconds: float = 900.0
    reference_max_age_hours: int = 72
    reference_age_policy: str = "warn_only"
    formats: tuple[FeedFormat, ...] = (FeedFormat.JSON, FeedFormat.XML)
    fallback_policy: str = "json_no_review_entries_then_xml_once"
    allowed_host: str = "itunes.apple.com"
    scheme: str = "https"
    allow_redirects: bool = False
    ambient_credentials: bool = False

    def __post_init__(self) -> None:
        for name in ("interval_hours", "min_pages", "max_pages", "max_http_requests",
                     "max_response_bytes", "reference_max_age_hours"):
            _integer(name, getattr(self, name))
        for name in ("min_overlap_count", "retry_count"):
            _integer(name, getattr(self, name), 0)
        if self.max_pages < self.min_pages:
            raise ContractError("max_pages must be >= min_pages")
        _number("min_overlap_ratio", self.min_overlap_ratio)
        if self.min_overlap_ratio > 1:
            raise ContractError("min_overlap_ratio must be <= 1")
        _number("global_spacing_seconds", self.global_spacing_seconds)
        for name in ("connect_timeout_seconds", "read_timeout_seconds", "target_deadline_seconds"):
            _number(name, getattr(self, name), positive=True)
        if type(self.formats) is not tuple or self.formats != (FeedFormat.JSON, FeedFormat.XML) or any(
                type(value) is not FeedFormat for value in self.formats):
            raise ContractError("formats must be the immutable JSON/XML format policy")
        for name, expected in (("reference_age_policy", "warn_only"),
                               ("fallback_policy", "json_no_review_entries_then_xml_once"),
                               ("allowed_host", "itunes.apple.com"), ("scheme", "https")):
            if type(getattr(self, name)) is not str or getattr(self, name) != expected:
                raise ContractError(f"{name} does not match the pilot contract")
        for name in ("allow_redirects", "ambient_credentials"):
            if type(getattr(self, name)) is not bool or getattr(self, name):
                raise ContractError(f"{name} must be false")

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["formats"] = [value.value for value in self.formats]
        return result

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> IngestionConfig:
        data = _exact_keys(value, cls)
        if type(data["formats"]) is not list or any(type(v) is not str for v in data["formats"]):
            raise ContractError("formats must be a JSON array of strings")
        try:
            data["formats"] = tuple(FeedFormat(v) for v in data["formats"])
        except ValueError as exc:
            raise ContractError("formats contains an unsupported format") from exc
        return cls(**data)


@dataclass(frozen=True)
class ConfigSnapshot:
    application_id: int
    source_application_id: str
    target_id: int
    software_revision: str
    parser_version: str
    run_mode: RunMode = RunMode.SYNTHETIC
    access_decision_ref: str | None = None
    retention_policy_ref: str | None = None
    config: IngestionConfig = IngestionConfig()
    source: str = "apple_app_store"
    storefront: str = "us"
    sort_by: str = "mostrecent"
    hash_contract_version: str = "apple-observed-v1"
    schema_version: str = "apple-ingestion-config/1"

    def __post_init__(self) -> None:
        _integer("application_id", self.application_id)
        _integer("target_id", self.target_id)
        for name in ("source_application_id", "software_revision", "parser_version", "hash_contract_version"):
            _text(name, getattr(self, name))
        for name in ("access_decision_ref", "retention_policy_ref"):
            _text(name, getattr(self, name), optional=True)
        for name, expected in (("source", "apple_app_store"), ("storefront", "us"),
                               ("sort_by", "mostrecent"), ("schema_version", "apple-ingestion-config/1")):
            if type(getattr(self, name)) is not str or getattr(self, name) != expected:
                raise ContractError(f"{name} does not match the pilot contract")
        if type(self.config) is not IngestionConfig:
            raise ContractError("config must be an IngestionConfig")
        if type(self.run_mode) is not RunMode:
            raise ContractError("run_mode must be a RunMode")

    def to_dict(self) -> dict[str, Any]:
        """Return a fresh JSON-safe object; mutations cannot alter this snapshot."""
        result = asdict(self)
        result["run_mode"] = self.run_mode.value
        result["config"] = self.config.to_dict()
        return result

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> ConfigSnapshot:
        """Require every versioned field; never fill omitted serialized defaults."""
        data = _exact_keys(value, cls)
        if type(data["run_mode"]) is not str:
            raise ContractError("run_mode must be a JSON string")
        try:
            data["run_mode"] = RunMode(data["run_mode"])
        except ValueError as exc:
            raise ContractError("run_mode is unsupported") from exc
        data["config"] = IngestionConfig.from_dict(data["config"])
        return cls(**data)

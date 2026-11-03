"""Deterministic comparison eligibility and coverage; no network or DB writes.

Coverage sufficiency and reference eligibility are separate decisions. Age is a
warning only. IDs in metrics are internal, application-scoped review primary
keys; opaque source IDs and review text never appear in these result objects.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from typing import Mapping
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.engine import Connection

from .contracts import ConfigSnapshot, IngestionConfig
from .models import Application, CollectionTarget, CollectionRun, FetchAttempt, ReviewObservation

RUN = CollectionRun.__table__
ATTEMPT = FetchAttempt.__table__
OBSERVATION = ReviewObservation.__table__
_DEFECT_CODES = frozenset({"INTRA_RUN_CONFLICT", "DB_CONSTRAINT", "DB_UNAVAILABLE", "PAGE_PERSISTENCE_FAILED",
                           "FEED_SCHEMA", "ENTRY_SCHEMA", "INVALID_TIMESTAMP", "REQUEST_OUTCOME_UNKNOWN",
                           "IDENTITY_DEFECT", "APPLICATION_SESSION_LOST", "PERSISTENCE_ERROR"})


@dataclass(frozen=True)
class Eligibility:
    eligible: bool
    reasons: tuple[str, ...]
    review_ids: frozenset[int]
    snapshot: ConfigSnapshot | None


@dataclass(frozen=True)
class CandidateExclusion:
    run_id: UUID
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class ReferenceDecision:
    reference_run_id: UUID | None
    review_ids: frozenset[int]
    reference_finished_at: datetime | None
    age_hours: float | None
    age_warning: bool
    had_usable_history: bool
    exclusions: tuple[CandidateExclusion, ...]

    @property
    def chain_restart(self) -> bool:
        return self.reference_run_id is None and self.had_usable_history

    def diagnostic(self) -> dict:
        counts = Counter(reason for candidate in self.exclusions for reason in candidate.reasons)
        return {"code": "REFERENCE_SELECTION", "reference_run_id": str(self.reference_run_id) if self.reference_run_id else None,
                "reference_age_hours": self.age_hours, "reference_age_warning": self.age_warning,
                "had_usable_history": self.had_usable_history, "excluded_candidate_count": len(self.exclusions),
                "excluded_reason_counts": dict(counts), "detail_truncated": len(self.exclusions) > 20,
                "excluded_candidates": [{"run_id": str(item.run_id), "reasons": list(item.reasons)}
                                        for item in self.exclusions[:20]]}


def diagnostic_codes(anomalies: list) -> set[str]:
    """Include exact totals even when individual anomaly details were truncated."""
    result = set()
    for item in anomalies:
        code = item.get("code")
        if isinstance(code, str):
            result.add(code)
        if code == "DIAGNOSTIC_TOTALS":
            result.update(key for key, value in item.get("counts", {}).items() if value)
        if code == "CONTROLLER_SUMMARY":
            result.update(item.get("reason_codes", ()))
        if code == "RECONCILIATION_SUMMARY" and item.get("conflict_count", 0):
            result.add("INTRA_RUN_CONFLICT")
    return result


def comparison_eligibility(connection: Connection, run: Mapping) -> Eligibility:
    """Assess one stored/proposed terminal row using its committed evidence.

    The caller owns the read transaction. A proposed terminal row can be used
    by Controller within its finalization transaction, before updating the row.
    No minimum page count, coverage classification or age filter is applied.
    """
    reasons = []
    if run["execution_status"] != "succeeded" or run["finished_at"] is None:
        reasons.append("EXECUTION_NOT_SUCCEEDED")
    if run["execution_status"] == "succeeded" and run["coverage_status"] == "pending":
        reasons.append("INCONSISTENT_OBSERVATIONS")
    try:
        snapshot = ConfigSnapshot.from_dict(run["config_snapshot"])
        target = CollectionTarget.__table__
        application = Application.__table__
        identity = connection.execute(select(application.c.source_application_id, application.c.source,
            target.c.storefront, target.c.sort_by).select_from(target.join(application,
                target.c.application_id == application.c.id)).where(
            target.c.id == run["target_id"], target.c.application_id == run["application_id"])).mappings().one_or_none()
        if (snapshot.application_id != run["application_id"] or snapshot.target_id != run["target_id"]
                or identity is None or any(getattr(snapshot, key) != identity[key] for key in
                ("source_application_id", "source", "storefront", "sort_by"))):
            reasons.append("IDENTITY_DEFECT")
    except (ValueError, TypeError, KeyError):
        snapshot = None
        reasons.append("IDENTITY_DEFECT")
    observations = list(connection.execute(select(OBSERVATION).where(OBSERVATION.c.run_id == run["id"])).mappings())
    review_ids = frozenset(row["review_id"] for row in observations)
    if not review_ids:
        reasons.append("EMPTY_OBSERVATIONS")
    if any(row["application_id"] != run["application_id"] for row in observations):
        reasons.append("IDENTITY_DEFECT")
    if any(row["conflict_count"] for row in observations):
        reasons.append("INCONSISTENT_OBSERVATIONS")
    attempts = list(connection.execute(select(ATTEMPT).where(ATTEMPT.c.run_id == run["id"])).mappings())
    selected = {row["page_number"]: row for row in attempts if row["persistence_status"] == "committed"}
    if any(row["finished_at"] is None or row["parsing_status"] == "pending"
           or row["persistence_status"] in {"pending", "unknown"} for row in attempts):
        reasons.append("UNRESOLVED_ATTEMPTS")
    if any(row["parsing_status"] != "succeeded" or row["entry_count"] is None for row in attempts):
        reasons.append("PARSING_DEFECT")
    coverage_codes = {"EMPTY_PAGE", "JSON_ENTRY_ABSENT", "PAGE_DUPLICATE_ONLY", "JSON_FALLBACK",
                      "SAME_PAGE_DUPLICATE", "CROSS_PAGE_DUPLICATE", "REFERENCE_AGE_WARNING",
                      "OBSERVABLE_WINDOW_BELOW_COUNT_THRESHOLD", "REFERENCE_WINDOW_BELOW_COUNT_THRESHOLD",
                      "LOW_ID_OVERLAP_COUNT", "LOW_ID_OVERLAP_RATIO", "MIN_LOGICAL_PAGES_NOT_MET"}
    if any(row["persistence_status"] not in {"committed", "not_applicable"}
           or any(code not in coverage_codes for code in row["error_codes"])
           or row["http_status"] != 200 for row in attempts):
        reasons.append("PERSISTENCE_DEFECT")
    # The only nonselected success is valid empty JSON with a selected XML for
    # that page. This is recovered format fallback, not a persistence defect.
    if any(row["persistence_status"] == "not_applicable" and not (
            row["format"] == "json" and row["entry_count"] == 0 and row["page_number"] in selected
            and selected[row["page_number"]]["format"] == "xml") for row in attempts):
        reasons.append("PERSISTENCE_DEFECT")
    if snapshot is not None and (len(attempts) > snapshot.config.max_http_requests
            or any(row["page_number"] > snapshot.config.max_pages for row in attempts)):
        reasons.append("INCONSISTENT_OBSERVATIONS")
    pages = set(selected)
    if (not pages or pages != set(range(1, max(pages, default=0) + 1))
            or sum(row["entry_count"] or 0 for row in selected.values()) != sum(row["occurrence_count"] for row in observations)
            or any(row["first_observed_page"] not in selected or row["first_observed_position"] > (
                selected[row["first_observed_page"]]["entry_count"] or 0) for row in observations)):
        reasons.append("INCONSISTENT_OBSERVATIONS")
    codes = diagnostic_codes(run["anomalies"])
    for attempt in attempts:
        codes.update(diagnostic_codes(attempt["anomalies"]))
    if codes & _DEFECT_CODES:
        reasons.append("INCONSISTENT_OBSERVATIONS")
    return Eligibility(not reasons, tuple(dict.fromkeys(reasons)), review_ids, snapshot)


def _compatible(candidate: ConfigSnapshot, requested: ConfigSnapshot) -> bool:
    names = ("schema_version", "application_id", "source_application_id", "target_id", "source",
             "storefront", "sort_by", "parser_version", "hash_contract_version")
    return all(getattr(candidate, name) == getattr(requested, name) for name in names)


def select_reference(connection: Connection, snapshot: ConfigSnapshot, started_at: datetime) -> ReferenceDecision:
    """Latest finished earlier, valid, nonempty compatible reference; warn at >72h.

    Usable incompatible earlier history triggers a new annotated anchor when
    no compatible predecessor remains. Failed/empty history establishes none.
    """
    candidates = connection.execute(select(RUN).where(
        RUN.c.target_id == snapshot.target_id, RUN.c.application_id == snapshot.application_id,
        RUN.c.started_at < started_at).order_by(RUN.c.finished_at.desc().nullslast(), RUN.c.started_at.desc(), RUN.c.id.desc())).mappings()
    exclusions = []
    usable_history = False
    chosen = None
    for run in candidates:
        eligibility = comparison_eligibility(connection, run)
        reasons = list(eligibility.reasons)
        earlier = run["finished_at"] is not None and run["finished_at"] < started_at
        if not earlier:
            reasons.append("NOT_FINISHED_EARLIER")
        if eligibility.eligible and earlier:
            if eligibility.snapshot.run_mode == snapshot.run_mode:
                usable_history = True
            else:
                reasons.append("RUN_MODE_MISMATCH")
            if not _compatible(eligibility.snapshot, snapshot):
                reasons.append("INCOMPATIBLE_CONTRACT")
        if reasons:
            exclusions.append(CandidateExclusion(run["id"], tuple(dict.fromkeys(reasons))))
        elif chosen is None:
            chosen = run, eligibility
    if chosen is None:
        return ReferenceDecision(None, frozenset(), None, None, False, usable_history, tuple(exclusions))
    run, eligibility = chosen
    age = (started_at - run["finished_at"]).total_seconds() / 3600
    return ReferenceDecision(run["id"], eligibility.review_ids, run["finished_at"], age,
                             age > snapshot.config.reference_max_age_hours, usable_history, tuple(exclusions))


@dataclass(frozen=True)
class CoverageMetrics:
    current_count: int
    reference_count: int | None
    overlap_count: int | None
    overlap_ratio: float | None
    max_possible_overlap: int | None
    committed_pages: int
    min_pages_met: bool
    overlap_count_met: bool
    overlap_ratio_met: bool
    reason_codes: tuple[str, ...]

    @property
    def thresholds_met(self) -> bool:
        return self.reference_count is not None and self.min_pages_met and self.overlap_count_met and self.overlap_ratio_met


def coverage_metrics(current_ids, reference_ids, committed_pages: int, config: IngestionConfig) -> CoverageMetrics:
    current = frozenset(current_ids)
    reference = None if reference_ids is None else frozenset(reference_ids)
    intersection = None if reference is None else len(current & reference)
    ratio = None if not current or reference is None else intersection / len(current)
    reasons = []
    if 0 < len(current) < config.min_overlap_count:
        reasons.append("OBSERVABLE_WINDOW_BELOW_COUNT_THRESHOLD")
    if reference is not None:
        if 0 < len(reference) < config.min_overlap_count:
            reasons.append("REFERENCE_WINDOW_BELOW_COUNT_THRESHOLD")
        if min(len(current), len(reference)) >= config.min_overlap_count and intersection < config.min_overlap_count:
            reasons.append("LOW_ID_OVERLAP_COUNT")
        if ratio is not None and ratio < config.min_overlap_ratio:
            reasons.append("LOW_ID_OVERLAP_RATIO")
    if committed_pages < config.min_pages:
        reasons.append("MIN_LOGICAL_PAGES_NOT_MET")
    return CoverageMetrics(len(current), None if reference is None else len(reference), intersection, ratio,
        None if reference is None else min(len(current), len(reference)), committed_pages,
        committed_pages >= config.min_pages, intersection is not None and intersection >= config.min_overlap_count,
        ratio is not None and ratio >= config.min_overlap_ratio, tuple(reasons))


def classify_coverage(metrics: CoverageMetrics, *, execution_status: str, conflict: bool,
                      coverage_caution: bool, had_usable_history: bool) -> str:
    if execution_status != "succeeded" or conflict:
        return "indeterminate"
    if not metrics.current_count:
        return "empty_window"
    if coverage_caution:
        return "indeterminate"
    if metrics.reference_count is None:
        return "no_reference" if had_usable_history else "baseline"
    return "overlap_sufficient" if metrics.thresholds_met else "overlap_insufficient"


__all__ = ["Eligibility", "ReferenceDecision", "CandidateExclusion", "CoverageMetrics", "diagnostic_codes",
           "comparison_eligibility", "select_reference", "coverage_metrics", "classify_coverage"]

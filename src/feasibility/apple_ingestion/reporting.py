"""Safe JSON reports from committed ingestion state; SELECT statements only.

The caller owns the Connection and transaction. For a stable view while another
process ingests, use a read-only REPEATABLE READ transaction. These functions
never commit, roll back, change roles/settings, repair state or request HTTP.
Routine output is an explicit allowlist; raw diagnostic objects and immutable
snapshots (including private policy references) are never copied into reports.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import asdict
from datetime import datetime, timezone
import math
import re
from uuid import UUID

from sqlalchemy import func, select

from .contracts import ConfigSnapshot, ReasonCode, ReferenceExclusionReason
from .models import Application, CollectionTarget, CollectionRun, FetchAttempt, Review, ReviewVersion, ReviewObservation
from .reference import comparison_eligibility, coverage_metrics, diagnostic_codes
from .transport import PILOT_APPLICATION_IDS
from .live import PROJECT_STOP_CODES

REPORT_CONTRACT_VERSION = "apple-ingestion-report/1"
A,T,R,F,I,V,O = (model.__table__ for model in (
    Application, CollectionTarget, CollectionRun, FetchAttempt, Review, ReviewVersion, ReviewObservation))
_TRANSPORT_FAILURES = {"TRANSPORT_TIMEOUT", "TRANSPORT_ERROR", "TRANSPORT_CLOCK", "BODY_LIMIT", "TARGET_DEADLINE", "INVALID_REQUEST"}
_PUBLIC_CODES = set(PROJECT_STOP_CODES) | {item.value for item in ReasonCode} | {item.value for item in ReferenceExclusionReason} | _TRANSPORT_FAILURES | {
    "PAGE_PERSISTENCE_FAILED", "PERSISTENCE_ERROR", "APPLICATION_SESSION_LOST", "OPERATOR_INTERRUPT",
    "BASELINE_ANCHOR", "COVERAGE_CAUTION", "JSON_FALLBACK", "SAME_PAGE_DUPLICATE", "CROSS_PAGE_DUPLICATE",
    "RUN_RECOVERED_INTERRUPTED", "APPLICATION_LOCKED", "SOURCE_DENIED", "INFRASTRUCTURE_UNAVAILABLE"}
_STOP_REASONS = {"overlap_met", "baseline_budget_complete", "page_budget", "request_budget", "empty_window_budget",
    "http_denied", "transport_error", "parse_error", "db_error", "consistency_anomaly", "operator_interrupt",
    "orphan_recovered", "recovered_interrupted", "target_deadline", "source_denied", "application_locked",
    "infrastructure_unavailable", "synthetic", "synthetic_fixture", "policy_stop", "project_policy_stopped"}
_SUMMARY_CODES = {"DIAGNOSTIC_TOTALS", "PAGE_SUMMARY", "RECONCILIATION_SUMMARY", "CONTROLLER_SUMMARY",
                  "REFERENCE_SELECTION", "SPOOL_REPLAYED", "SPOOL_RUN_REPLAYED"}


class ReportingError(ValueError):
    """Safe lookup/contract failure without supplied values or database text."""


def _uuid(value):
    try:
        return value if isinstance(value, UUID) else UUID(str(value))
    except (ValueError, TypeError, AttributeError):
        raise ReportingError("INVALID_REPORT_ID") from None


def _at(value):
    return value.astimezone(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z") if value is not None else None


def _version(value):
    return value if isinstance(value,str) and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._/-]{0,127}",value) else None


def _number(value):
    return value if type(value) in (int,float) and math.isfinite(value) and value >= 0 else None


def _count(value):
    return value if type(value) is int and value >= 0 else None


def _codes(anomalies, errors=()):
    values={code for code in errors if isinstance(code,str) and code in _PUBLIC_CODES}
    for item in anomalies:
        if not isinstance(item,dict):
            continue
        code=item.get("code")
        if isinstance(code,str) and code in _PUBLIC_CODES:
            values.add(code)
        if code=="DIAGNOSTIC_TOTALS" and isinstance(item.get("counts"),dict):
            values.update(key for key,value in item["counts"].items() if key in _PUBLIC_CODES and _count(value) and value>0)
        if code=="CONTROLLER_SUMMARY" and isinstance(item.get("reason_codes"),list):
            values.update(value for value in item["reason_codes"] if isinstance(value,str) and value in _PUBLIC_CODES)
        if code=="RECONCILIATION_SUMMARY" and _count(item.get("conflict_count")):
            values.add("INTRA_RUN_CONFLICT")
    return values


def _summary(anomalies,code):
    return next((item for item in anomalies if isinstance(item,dict) and item.get("code")==code),None)


def _data(connection, run_id):
    run=connection.execute(select(R).where(R.c.id==run_id)).mappings().one_or_none()
    if run is None:
        raise ReportingError("RUN_NOT_FOUND")
    attempts=list(connection.execute(select(F).where(F.c.run_id==run_id).order_by(F.c.request_number)).mappings())
    # Deliberately select no review source IDs, titles or bodies, including the
    # observed-version join: a parent's latest version is not this run's window.
    observations=list(connection.execute(select(O,V.c.source_updated_at).select_from(O.join(V,
        O.c.observed_version_id==V.c.id)).where(O.c.run_id==run_id)).mappings())
    return run,attempts,observations


def _cautions(attempts):
    result=set()
    for row in attempts:
        if row["persistence_status"] != "committed":
            continue
        if row["entry_count"]==0:
            result.add("EMPTY_PAGE")
        if "PAGE_DUPLICATE_ONLY" in _codes(row["anomalies"]):
            result.add("PAGE_DUPLICATE_ONLY")
    return sorted(result)


def _request_metrics(attempts):
    def codes(row): return _codes(row["anomalies"],row["error_codes"])
    unresolved=lambda row: row["finished_at"] is None or row["parsing_status"]=="pending" or row["persistence_status"] in {"pending","unknown"}
    unknown=lambda row: "REQUEST_OUTCOME_UNKNOWN" in codes(row) or (
        row["http_status"] is None and row["response_bytes"] is None and unresolved(row))
    known=lambda row: row["response_bytes"] is not None or (
        row["http_status"] is not None and row["parsing_status"] in {"succeeded","failed"})
    return {
        "intent_count":len(attempts),
        "known_sent_lower_bound":sum(row["http_status"] is not None for row in attempts),
        "known_http_response_count":sum(row["http_status"] is not None for row in attempts),
        "known_transport_result_count":sum(known(row) for row in attempts),
        "known_http_body_completed_count":sum(row["http_status"]==200 and row["parsing_status"] in {"succeeded","failed"} for row in attempts),
        "resolved_diagnostic_count":sum(not unresolved(row) for row in attempts),
        "http_200_count":sum(row["http_status"]==200 for row in attempts),
        "http_failure_count":sum(row["http_status"] is not None and row["http_status"]!=200 for row in attempts),
        "transport_failure_count":sum(bool(codes(row)&_TRANSPORT_FAILURES) for row in attempts),
        "parse_failure_count":sum(row["parsing_status"]=="failed" for row in attempts),
        "denied_count":sum(row["http_status"] in {401,403} for row in attempts),
        "rate_limited_count":sum(row["http_status"]==429 for row in attempts),
        "unknown_request_outcome_count":sum(unknown(row) for row in attempts),
        "unresolved_attempt_count":sum(unresolved(row) for row in attempts),
        "unresolved_persistence_count":sum(row["persistence_status"] in {"pending","unknown"} for row in attempts),
        "persistence_unknown_count":sum(row["persistence_status"]=="unknown" for row in attempts),
        "rolled_back_attempt_count":sum(row["persistence_status"]=="rolled_back" for row in attempts),
        "known_response_bytes":sum(row["response_bytes"] or 0 for row in attempts),
        "response_byte_count_missing_count":sum(row["response_bytes"] is None for row in attempts),
        "sent_evidence_basis":"durable_http_status_lower_bound; timeout_or_null_status_does_not_prove_send",
        "completion_evidence_basis":"transport_metadata_or_parse_result; recovered_finish_time_alone_is_not_response_completion",
    }


def _observation_metrics(attempts,observations):
    actions={action:{"total":0,"undisputed":0,"disputed":0} for action in ("new","changed","unchanged")}
    for row in observations:
        action=actions[row["first_action"]]
        action["total"]+=1
        action["disputed" if row["conflict_count"] else "undisputed"]+=1
    selected=[row for row in attempts if row["persistence_status"]=="committed"]
    summaries=[_summary(row["anomalies"],"PAGE_SUMMARY") for row in selected]
    available=all(summary is not None and all(_count(summary.get(name)) is not None for name in
        ("same_page_duplicate_count","cross_page_duplicate_count")) for summary in summaries)
    return {"committed_distinct_count":len(observations),"committed_occurrence_count":sum(row["occurrence_count"] for row in observations),
        "first_actions":actions,"first_action_partition_valid":sum(action["total"] for action in actions.values())==len(observations),
        "changed_observed":actions["changed"]["total"],"changed_undisputed":actions["changed"]["undisputed"],
        "changed_disputed":actions["changed"]["disputed"],
        "duplicate_occurrence_count":sum(row["occurrence_count"]-1 for row in observations),
        "same_page_duplicate_count":sum(item["same_page_duplicate_count"] for item in summaries) if available else None,
        "cross_page_duplicate_count":sum(item["cross_page_duplicate_count"] for item in summaries) if available else None,
        "same_and_cross_page_subsets_can_overlap":True,
        "conflict_occurrence_count":sum(row["conflict_count"] for row in observations),
        "disputed_review_count":sum(bool(row["conflict_count"]) for row in observations),
        "committed_page_summary_missing_count":sum(summary is None for summary in summaries),
        "uncommitted_parsed_occurrence_count":sum(row["entry_count"] or 0 for row in attempts if row["persistence_status"]!="committed"),
        "source_corpus_count":None}


def _selection_diagnostic(anomalies):
    stored=_summary(anomalies,"REFERENCE_SELECTION")
    if stored is None:
        return {"available":False,"excluded_candidate_count":None,"excluded_reason_counts":{},"excluded_candidates":[]}
    reasons={item.value for item in ReferenceExclusionReason}
    details=[]
    for candidate in stored.get("excluded_candidates",[])[:20]:
        try: run_id=str(_uuid(candidate.get("run_id")))
        except ReportingError: continue
        details.append({"run_id":run_id,"reasons":sorted(set(candidate.get("reasons",[]))&reasons)})
    return {"available":True,"excluded_candidate_count":_count(stored.get("excluded_candidate_count")),
        "excluded_reason_counts":{key:value for key,value in stored.get("excluded_reason_counts",{}).items()
                                  if key in reasons and _count(value) is not None},
        "excluded_candidates":details,"detail_truncated":stored.get("detail_truncated") is True}


def run_report(connection,run_id) -> dict:
    """Read one actual run; every count concerns durable/committed evidence."""
    run_id=_uuid(run_id)
    run,attempts,observations=_data(connection,run_id)
    eligibility=comparison_eligibility(connection,run)
    snapshot=eligibility.snapshot
    kind=snapshot.run_mode.value if snapshot else "unknown"
    public_app=connection.scalar(select(A.c.source_application_id).where(A.c.id==run["application_id"]))
    selected=[row for row in attempts if row["persistence_status"]=="committed"]
    committed_pages=sorted({row["page_number"] for row in selected})
    requests=_request_metrics(attempts)
    observed=_observation_metrics(attempts,observations)
    caution=_cautions(attempts)
    codes=_codes(run["anomalies"])
    for attempt in attempts: codes.update(_codes(attempt["anomalies"],attempt["error_codes"]))
    ref=None
    ref_ids=None
    age=None
    reference={"run_id":str(run["reference_run_id"]) if run["reference_run_id"] else None,
               "execution_status":None,"coverage_status":None,"coverage_cautions":[],"comparison_eligible_now":None,
               "exclusion_reasons_now":[],"age_hours":None,"age_warning":False,
               "age_warning_threshold_hours":snapshot.config.reference_max_age_hours if snapshot else None,
               "age_policy":"warn_only", "selection":_selection_diagnostic(run["anomalies"])}
    if run["reference_run_id"]:
        ref,ref_attempts,ref_observations=_data(connection,run["reference_run_id"])
        ref_eligibility=comparison_eligibility(connection,ref)
        ref_ids={row["review_id"] for row in ref_observations}
        age=(run["started_at"]-ref["finished_at"]).total_seconds()/3600 if ref["finished_at"] else None
        reference.update(execution_status=ref["execution_status"],coverage_status=ref["coverage_status"],
            coverage_cautions=_cautions(ref_attempts),comparison_eligible_now=ref_eligibility.eligible,
            exclusion_reasons_now=list(ref_eligibility.reasons),age_hours=_number(age),
            age_warning=bool(snapshot and age is not None and age>snapshot.config.reference_max_age_hours))
    if reference["age_warning"]: codes.add("REFERENCE_AGE_WARNING")
    metrics=coverage_metrics((row["review_id"] for row in observations),ref_ids,len(committed_pages),snapshot.config) if snapshot else None
    if metrics: codes.update(metrics.reason_codes)
    blocking_codes={"REQUEST_OUTCOME_UNKNOWN","INTRA_RUN_CONFLICT","DB_CONSTRAINT","DB_UNAVAILABLE",
                    "PAGE_PERSISTENCE_FAILED","PERSISTENCE_ERROR","APPLICATION_SESSION_LOST","OPERATOR_INTERRUPT"}
    execution_allows_stop=run["execution_status"] in {"running","succeeded"}
    no_failure=(execution_allows_stop and not codes & blocking_codes and requests["http_failure_count"]==
                requests["transport_failure_count"]==requests["parse_failure_count"]==requests["rolled_back_attempt_count"]==
                requests["unresolved_attempt_count"]==requests["unknown_request_outcome_count"]==0)
    predicates={"execution_allows_overlap_stop":execution_allows_stop,"reference_present":run["reference_run_id"] is not None,
        "nonempty_current_window":bool(observations),"min_logical_pages_met":metrics.min_pages_met if metrics else None,
        "overlap_count_met":metrics.overlap_count_met if metrics else None,
        "overlap_ratio_met":metrics.overlap_ratio_met if metrics else None,
        "no_conflicts":not observed["conflict_occurrence_count"],"no_coverage_caution":not caution,
        "no_unrecovered_attempt_failure":no_failure}
    source_times=[row["source_updated_at"] for row in observations if row["source_updated_at"] is not None]
    starts=[row["started_at"] for row in attempts]
    known_finishes=[row["finished_at"] for row in attempts if row["finished_at"] is not None
        and row["http_status"] is not None and row["parsing_status"] in {"succeeded","failed"}
        and not any(item.get("completion_time_unknown") is True for item in row["anomalies"])]
    def bound(values,fn): return _at(fn(values)) if values else None
    response_shapes={
        "json_entry_absent_count":sum(row["format"]=="json" and "JSON_ENTRY_ABSENT" in _codes(row["anomalies"]) for row in attempts),
        "json_explicit_empty_count":sum(row["format"]=="json" and row["parsing_status"]=="succeeded" and row["entry_count"]==0
                                       and "JSON_ENTRY_ABSENT" not in _codes(row["anomalies"]) for row in attempts),
        "xml_empty_count":sum(row["format"]=="xml" and row["parsing_status"]=="succeeded" and row["entry_count"]==0 for row in attempts),
        "json_fallback_selected_count":sum(row["format"]=="json" and "JSON_FALLBACK" in _codes(row["anomalies"]) for row in attempts),
        "xml_fallback_intent_count":sum(row["format"]=="xml" for row in attempts),
        "invalid_envelope_count":sum("FEED_SCHEMA" in _codes(row["anomalies"],row["error_codes"]) for row in attempts),
        "invalid_entry_count":sum("ENTRY_SCHEMA" in _codes(row["anomalies"],row["error_codes"]) for row in attempts),
        "invalid_timestamp_count":sum("INVALID_TIMESTAMP" in _codes(row["anomalies"],row["error_codes"]) for row in attempts)}
    limitations=["BOUNDED_OBSERVED_WINDOW_ONLY","NO_DELETION_OR_COMPLETENESS_INFERENCE","SOURCE_EDIT_IDENTITY_AND_ORDER_UNVERIFIED"]
    if kind=="synthetic": limitations.append("SYNTHETIC_NOT_LIVE_SOURCE_EVIDENCE")
    if run["execution_status"]!="succeeded": limitations.append("INCOMPLETE_EXECUTION")
    if requests["unknown_request_outcome_count"]: limitations.append("UNKNOWN_PHYSICAL_REQUEST_OUTCOMES")
    if caution: limitations.append("COVERAGE_CAUTION")
    if reference["age_warning"]: limitations.append("CONTINUITY_GAP_WARNING")
    return {"report_contract_version":REPORT_CONTRACT_VERSION,"evidence_kind":kind,
        "run_id":str(run_id),"batch_id":str(run["batch_id"]),"application_id":run["application_id"],"target_id":run["target_id"],
        "source_application_id":public_app if public_app in PILOT_APPLICATION_IDS else None,
        "source":"apple_app_store","storefront":snapshot.storefront if snapshot else None,
        "sort_by":snapshot.sort_by if snapshot else None,
        "software_revision":_version(snapshot.software_revision) if snapshot else None,
        "parser_version":_version(snapshot.parser_version) if snapshot else None,
        "hash_contract_version":_version(snapshot.hash_contract_version) if snapshot else None,
        "snapshot_valid":snapshot is not None,"started_at":_at(run["started_at"]),"finished_at":_at(run["finished_at"]),
        "execution_status":run["execution_status"],"coverage_status":run["coverage_status"],
        "stop_reason":run["stop_reason"] if run["stop_reason"] in _STOP_REASONS else "UNRECOGNIZED_STOP_REASON" if run["stop_reason"] else None,
        "requests":requests,"pages":{"attempted_numbers":sorted({row["page_number"] for row in attempts}),
            "committed_numbers":committed_pages,"committed_count":len(committed_pages),
            "committed_entry_count":sum(row["entry_count"] or 0 for row in selected)},
        "observations":observed,"response_shapes":response_shapes,"reference":reference,
        "budgets":{"min_logical_pages":snapshot.config.min_pages,"max_logical_pages":snapshot.config.max_pages,
            "max_http_requests":snapshot.config.max_http_requests,"automatic_retries":snapshot.config.retry_count,
            "min_overlap_count":snapshot.config.min_overlap_count,"min_overlap_ratio":snapshot.config.min_overlap_ratio,
            "target_deadline_seconds":snapshot.config.target_deadline_seconds} if snapshot else None,
        "comparison_eligibility":{"eligible":eligibility.eligible,"exclusion_reasons":list(eligibility.reasons)},
        "coverage":{"metrics":asdict(metrics) if metrics else None,"stop_predicates":predicates,
            "can_stop_on_overlap":bool(metrics and metrics.thresholds_met and all(value is True for value in predicates.values())),
            "cautions":caution,"reason_codes":list(metrics.reason_codes) if metrics else [],
            "low_volume_interpretation":"bounded_successful_window" if run["execution_status"]=="succeeded" else "measured_partial_only"},
        "anchor":{"baseline":"BASELINE_ANCHOR" in codes or run["coverage_status"]=="baseline","chain_restarted":"REFERENCE_CHAIN_RESTARTED" in codes},
        "window":{"source_updated_at_min":bound(source_times,min),"source_updated_at_max":bound(source_times,max),
            "source_updated_at_missing_count":len(observations)-len(source_times),
            "intent_started_at_min":bound(starts,min),"intent_started_at_max":bound(starts,max),
            "known_response_completed_at_min":bound(known_finishes,min),"known_response_completed_at_max":bound(known_finishes,max),
            "has_committed_observations":bool(observations),"bounds_kind":"observed_version_update_times_not_creation_or_latency"},
        "reason_codes":sorted(codes),"limitations":limitations}


def batch_report(connection,batch_id,expected_target_ids=None,*,outcomes=()) -> dict:
    """Read actual rows; optional Controller outcomes distinguish skips/missing.

    Mixed evidence kinds are tallied separately. An intended run UUID supplied
    by an outcome never fabricates a persisted run or its observation counts.
    """
    batch_id=_uuid(batch_id)
    runs=connection.execute(select(R.c.id,R.c.target_id).where(R.c.batch_id==batch_id).order_by(R.c.started_at,R.c.id)).all()
    targets=set(connection.scalars(select(T.c.id).join(A,T.c.application_id==A.c.id).where(
        A.c.source_application_id.in_(sorted(PILOT_APPLICATION_IDS))))) if expected_target_ids is None else set(expected_target_ids)
    if any(type(value) is not int or value<=0 for value in targets): raise ReportingError("INVALID_EXPECTED_TARGET_IDS")
    expected_targets=frozenset(targets)
    targets.update(row.target_id for row in runs)
    reports={row.id:run_report(connection,row.id) for row in runs}
    actual_by_target={target:[reports[row.id] for row in runs if row.target_id==target] for target in targets}
    supplied={}
    for outcome in outcomes:
        if getattr(outcome,"batch_id",None)!=batch_id: raise ReportingError("OUTCOME_BATCH_MISMATCH")
        target=getattr(outcome,"target_id",None)
        if type(target) is not int or target<=0: raise ReportingError("INVALID_OUTCOME_TARGET")
        supplied[target]=outcome; targets.add(target)
    entries=[]
    for target in sorted(targets):
        actual=actual_by_target.get(target,[]); outcome=supplied.get(target)
        state="recorded" if actual else "missing"
        safe_outcome=None
        if outcome is not None:
            run_id=getattr(outcome,"run_id",None)
            stop=getattr(outcome,"stop_reason",None)
            safe_outcome={"intended_run_id":str(_uuid(run_id)) if run_id is not None else None,
                "stop_reason":stop if stop in _STOP_REASONS else "UNRECOGNIZED_STOP_REASON",
                "finalized":getattr(outcome,"finalized",None) is True,
                "recovery_required":getattr(outcome,"recovery_required",None) is True,
                "run_persisted":getattr(outcome,"run_persisted",None) if getattr(outcome,"run_persisted",None) in (True,False,None) else None}
            if not actual: state="skipped" if run_id is None else "persistence_unknown" if safe_outcome["run_persisted"] is None else "unpersisted"
        entries.append({"target_id":target,"expected":target in expected_targets,"state":state,"runs":actual,"reported_outcome":safe_outcome})
    by_kind={}
    for report in reports.values():
        totals=by_kind.setdefault(report["evidence_kind"],dict(run_count=0,request_intents=0,committed_pages=0,committed_observations=0,committed_occurrences=0))
        totals["run_count"]+=1; totals["request_intents"]+=report["requests"]["intent_count"]
        totals["committed_pages"]+=report["pages"]["committed_count"]
        totals["committed_observations"]+=report["observations"]["committed_distinct_count"]
        totals["committed_occurrences"]+=report["observations"]["committed_occurrence_count"]
    kinds=set(by_kind)
    return {"report_contract_version":REPORT_CONTRACT_VERSION,"batch_id":str(batch_id),
        "evidence_kind":next(iter(kinds)) if len(kinds)==1 else "mixed" if kinds else "unknown",
        "expected_target_count":len(expected_targets),
        "recorded_target_count":sum(entry["expected"] and entry["state"]=="recorded" for entry in entries),
        "skipped_target_count":sum(entry["expected"] and entry["state"]=="skipped" for entry in entries),
        "missing_target_count":sum(entry["expected"] and entry["state"]=="missing" for entry in entries),
        "unpersisted_target_count":sum(entry["expected"] and entry["state"] in {"unpersisted","persistence_unknown"} for entry in entries),
        "unexpected_target_count":len(targets-expected_targets),"unexpected_target_ids":sorted(targets-expected_targets),
        "totals_scope":"all_actual_runs_in_batch_including_unexpected_targets",
        "totals_by_evidence_kind":by_kind,"targets":entries}


def integrity_report(connection) -> dict:
    """Return safe issue counts, never repair state or infer source deletion."""
    history=select(V.c.review_id,func.max(V.c.version_number).label("max_number"),
        func.count().label("version_count")).group_by(V.c.review_id).subquery()
    not_latest=connection.scalar(select(func.count()).select_from(I.join(V,I.c.current_version_id==V.c.id)
        .join(history,history.c.review_id==I.c.id)).where(V.c.version_number!=history.c.max_number))
    gaps=connection.scalar(select(func.count()).select_from(history).where(history.c.version_count!=history.c.max_number))
    counts={"CURRENT_VERSION_NOT_LATEST":not_latest,"VERSION_NUMBER_GAPS":gaps,
            "TERMINAL_PENDING_ATTEMPTS":0,"TERMINAL_PENDING_COVERAGE":0,
            "PAGE_OBSERVATION_COUNT_MISMATCH":0,"COMMITTED_PAGE_SUMMARY_MISSING":0}
    running_pending=0
    for run_id in connection.scalars(select(R.c.id)):
        run,attempts,observations=_data(connection,run_id)
        unresolved=sum(row["finished_at"] is None or row["parsing_status"]=="pending" or row["persistence_status"] in {"pending","unknown"} for row in attempts)
        if run["execution_status"]!="running":
            counts["TERMINAL_PENDING_ATTEMPTS"]+=unresolved
            counts["TERMINAL_PENDING_COVERAGE"]+=run["coverage_status"]=="pending"
        else: running_pending+=unresolved
        selected={row["page_number"]:row for row in attempts if row["persistence_status"]=="committed"}
        mismatch=sum(row["entry_count"] or 0 for row in selected.values())!=sum(row["occurrence_count"] for row in observations)
        mismatch=mismatch or bool(selected and set(selected)!=set(range(1,max(selected)+1)))
        mismatch=mismatch or any(row["first_observed_page"] not in selected or row["first_observed_position"]>(
            selected[row["first_observed_page"]]["entry_count"] or 0) for row in observations)
        for page,row in selected.items():
            summary=_summary(row["anomalies"],"PAGE_SUMMARY")
            if summary is None:
                counts["COMMITTED_PAGE_SUMMARY_MISSING"]+=1
                continue
            new_observations=sum(obs["first_observed_page"]==page for obs in observations)
            action_counts=[_count(summary.get(name)) for name in ("new_count","changed_count","unchanged_count")]
            mismatch=mismatch or summary.get("entry_count")!=row["entry_count"] or None in action_counts or sum(
                value or 0 for value in action_counts)!=new_observations
            mismatch=mismatch or summary.get("duplicate_count")!=(row["entry_count"] or 0)-new_observations
        counts["PAGE_OBSERVATION_COUNT_MISMATCH"]+=bool(mismatch)
    return {"report_contract_version":REPORT_CONTRACT_VERSION,"read_only":True,"ok":not any(counts.values()),
        "issue_counts":counts,"running_pending_attempt_count":running_pending,
        "running_pending_requires_application_lock_check":bool(running_pending),
        "source_deletion_inferred":False}


__all__=["REPORT_CONTRACT_VERSION","ReportingError","run_report","batch_report","integrity_report"]

"""Read-only report correctness and privacy on disposable PostgreSQL."""
from dataclasses import replace
from datetime import timedelta
import json
from uuid import uuid4

import pytest
pytest.importorskip("sqlalchemy")
from sqlalchemy import event, insert, select, text, update

from feasibility.apple_ingestion.contracts import ConfigSnapshot, RunMode
from feasibility.apple_ingestion.models import CollectionRun, FetchAttempt, Review, ReviewVersion, ReviewObservation
from feasibility.apple_ingestion.reporting import REPORT_CONTRACT_VERSION, ReportingError, batch_report, integrity_report, run_report
from feasibility.apple_ingestion.transport import FetchResponse
from test_apple_ingestion_controller import Clock, controller, feed, stored, xml
from test_apple_ingestion_reference import NOW, create_history, make_snapshot

R,F,I,V,O=(model.__table__ for model in (CollectionRun,FetchAttempt,Review,ReviewVersion,ReviewObservation))


def report(engine,rid):
    with engine.connect() as c: return run_report(c,rid)


def test_partition_duplicates_conflicts_and_safe_report_from_committed_pages(apple_database,tmp_path):
    engine=apple_database; snapshot=make_snapshot(engine)
    c=controller(engine,tmp_path,[feed(("one","one","two")),feed(("one","one"),body="PRIVATE-ALTERNATE-BODY")])
    result=c.run_target(snapshot,uuid4())
    value=report(engine,result.run_id)
    observations=value["observations"]
    assert observations["committed_distinct_count"]==2 and observations["committed_occurrence_count"]==5
    assert observations["first_actions"]["new"]=={"total":2,"undisputed":1,"disputed":1}
    assert observations["first_action_partition_valid"]
    assert observations["duplicate_occurrence_count"]==3
    assert observations["cross_page_duplicate_count"]==2 and observations["same_page_duplicate_count"]==2
    assert observations["conflict_occurrence_count"]==2
    assert value["evidence_kind"]=="synthetic" and value["report_contract_version"]==REPORT_CONTRACT_VERSION
    assert value["pages"]["committed_count"]==2 and not value["comparison_eligibility"]["eligible"]
    assert "PRIVATE-ALTERNATE-BODY" not in json.dumps(value)
    assert "SYNTHETIC_NOT_LIVE_SOURCE_EVIDENCE" in value["limitations"]


def test_changed_observed_and_changed_undisputed_remain_separate(apple_database,tmp_path):
    engine=apple_database; snapshot=make_snapshot(engine)
    create_history(engine,snapshot,pages=(("one",),),at=NOW-timedelta(days=1))
    c=controller(engine,tmp_path,[feed(("one",),body="synthetic new"),feed(("one",),body="synthetic conflicting")])
    result=c.run_target(snapshot,uuid4())
    value=report(engine,result.run_id)
    assert value["observations"]["changed_observed"]==1
    assert value["observations"]["changed_undisputed"]==0 and value["observations"]["changed_disputed"]==1
    assert value["observations"]["first_actions"]["changed"]["total"]==1


def test_failed_page_candidates_are_not_committed_metrics(apple_database,tmp_path,monkeypatch):
    import feasibility.apple_ingestion.controller as implementation
    from feasibility.apple_ingestion.reconcile import ReconciliationError
    engine=apple_database; snapshot=make_snapshot(engine)
    original=implementation.persist_page
    def fail_second(connection,rid,aid,records,at):
        if records[0].source_review_id=="uncommitted-private-id":
            raise ReconciliationError("PAGE_PERSISTENCE_FAILED")
        return original(connection,rid,aid,records,at)
    monkeypatch.setattr(implementation,"persist_page",fail_second)
    c=controller(engine,tmp_path,[feed(("committed",)),feed(("uncommitted-private-id","other-uncommitted"))])
    result=c.run_target(snapshot,uuid4())
    value=report(engine,result.run_id)
    assert result.execution_status=="partial"
    assert value["pages"]["committed_numbers"]==[1] and value["pages"]["attempted_numbers"]==[1,2]
    assert value["observations"]["committed_occurrence_count"]==1
    assert value["observations"]["uncommitted_parsed_occurrence_count"]==2
    assert value["requests"]["rolled_back_attempt_count"]==1
    assert value["coverage"]["low_volume_interpretation"]=="measured_partial_only"
    assert "uncommitted-private-id" not in json.dumps(value)


def test_http_200_parse_failure_is_not_http_failure(apple_database,tmp_path):
    engine=apple_database; snapshot=make_snapshot(engine)
    c=controller(engine,tmp_path,[FetchResponse(200,b"PRIVATE-BAD-FEED",16)])
    value=report(engine,c.run_target(snapshot,uuid4()).run_id)
    assert value["requests"]["intent_count"]==value["requests"]["http_200_count"]==1
    assert value["requests"]["parse_failure_count"]==1 and value["requests"]["http_failure_count"]==0
    assert value["response_shapes"]["invalid_envelope_count"]==1
    assert value["observations"]["committed_distinct_count"]==0
    assert value["observations"]["source_corpus_count"] is None
    assert not value["window"]["has_committed_observations"]


def test_timeout_does_not_prove_physical_send_and_pending_intent_is_unknown(apple_database,tmp_path):
    engine=apple_database; snapshot=make_snapshot(engine)
    c=controller(engine,tmp_path,[FetchResponse(None,b"",0,"TRANSPORT_TIMEOUT")])
    rid=c.run_target(snapshot,uuid4()).run_id
    known=report(engine,rid)
    assert known["requests"]["known_sent_lower_bound"]==0
    assert known["requests"]["known_transport_result_count"]==1
    assert known["requests"]["transport_failure_count"]==1
    assert known["requests"]["unknown_request_outcome_count"]==0
    with engine.begin() as conn:
        conn.execute(update(F).where(F.c.run_id==rid).values(finished_at=None,response_bytes=None,
            parsing_status="pending",persistence_status="unknown",error_codes=[],anomalies=[]))
    unknown=report(engine,rid)
    assert unknown["requests"]["unknown_request_outcome_count"]==1
    assert unknown["requests"]["unresolved_attempt_count"]==1
    assert unknown["requests"]["known_transport_result_count"]==0
    assert unknown["window"]["known_response_completed_at_max"] is None


def test_recovery_finish_time_is_not_response_completion(apple_database,tmp_path):
    engine=apple_database; snapshot=make_snapshot(engine)
    c=controller(engine,tmp_path,[KeyboardInterrupt()])
    rid=c.run_target(snapshot,uuid4()).run_id
    value=report(engine,rid)
    assert value["requests"]["resolved_diagnostic_count"]==1
    assert value["requests"]["known_transport_result_count"]==0
    assert value["requests"]["unknown_request_outcome_count"]==1
    assert value["window"]["known_response_completed_at_min"] is None


def test_empty_json_missing_explicit_and_xml_fallback_are_distinct(apple_database,tmp_path):
    engine=apple_database; snapshot=make_snapshot(engine)
    absent=b'{"feed":{}}'
    c=controller(engine,tmp_path,[FetchResponse(200,absent,len(absent)),xml(("one",)),feed(()),xml(())])
    value=report(engine,c.run_target(snapshot,uuid4()).run_id)
    shapes=value["response_shapes"]
    assert shapes["json_entry_absent_count"]==1 and shapes["json_explicit_empty_count"]==1
    assert shapes["xml_empty_count"]==1 and shapes["xml_fallback_intent_count"]==shapes["json_fallback_selected_count"]==2
    assert value["requests"]["intent_count"]==4 and value["pages"]["committed_count"]==2
    assert value["comparison_eligibility"]["eligible"] and value["coverage_status"]=="indeterminate"


def test_reference_age_own_cautions_metrics_and_every_stop_predicate(apple_database,tmp_path):
    engine=apple_database; snapshot=make_snapshot(engine)
    first=controller(engine,tmp_path,[feed(("one",)),feed(("one",))]).run_target(snapshot,uuid4())
    next_controller=controller(engine,tmp_path,[feed(("one",)),feed(("two",))],clock=Clock(NOW+timedelta(hours=73)))
    second=next_controller.run_target(snapshot,uuid4())
    value=report(engine,second.run_id)
    assert value["reference"]["run_id"]==str(first.run_id)
    assert value["reference"]["coverage_status"]=="indeterminate"
    assert value["reference"]["comparison_eligible_now"]
    assert value["reference"]["coverage_cautions"]==["PAGE_DUPLICATE_ONLY"]
    assert value["reference"]["age_warning"] and value["reference"]["age_policy"]=="warn_only"
    metrics=value["coverage"]["metrics"]
    assert (metrics["current_count"],metrics["reference_count"],metrics["overlap_count"],metrics["max_possible_overlap"])==(2,1,1,1)
    predicates=value["coverage"]["stop_predicates"]
    assert predicates["min_logical_pages_met"] and not predicates["overlap_count_met"]
    assert predicates["overlap_ratio_met"] and not value["coverage"]["can_stop_on_overlap"]
    assert value["budgets"]["min_overlap_count"]==20 and value["budgets"]["min_overlap_ratio"]==.2


def test_no_reference_comparison_values_are_null_and_restart_details_are_safe(apple_database,tmp_path):
    engine=apple_database; snapshot=make_snapshot(engine)
    create_history(engine,replace(snapshot,parser_version="old-fixture"))
    c=controller(engine,tmp_path,[feed(("one",)),feed(("two",))],clock=Clock(NOW+timedelta(days=1)))
    value=report(engine,c.run_target(snapshot,uuid4()).run_id)
    assert value["coverage_status"]=="no_reference" and value["anchor"]["chain_restarted"]
    metrics=value["coverage"]["metrics"]
    assert metrics["reference_count"] is metrics["overlap_count"] is metrics["overlap_ratio"] is metrics["max_possible_overlap"] is None
    assert value["reference"]["selection"]["excluded_reason_counts"]["INCOMPATIBLE_CONTRACT"]==1


def test_bounds_use_observed_version_not_parent_current_version(apple_database,tmp_path):
    engine=apple_database; snapshot=make_snapshot(engine)
    first=controller(engine,tmp_path,[feed(("one",)),feed(("two",))]).run_target(snapshot,uuid4())
    with engine.begin() as c:
        first_versions=c.scalars(select(O.c.observed_version_id).where(O.c.run_id==first.run_id)).all()
        c.execute(update(V).where(V.c.id==first_versions[0]).values(source_updated_at=NOW-timedelta(days=5)))
    second=controller(engine,tmp_path,[feed(("one",),body="later"),feed(("two",),body="later")],clock=Clock(NOW+timedelta(days=1))).run_target(snapshot,uuid4())
    with engine.begin() as c:
        current=c.scalars(select(I.c.current_version_id)).all()
        c.execute(update(V).where(V.c.id.in_(current)).values(source_updated_at=NOW+timedelta(days=100)))
    value=report(engine,first.run_id)
    assert value["window"]["source_updated_at_min"]=="2026-10-29T12:00:00.000000Z"
    assert value["window"]["source_updated_at_max"]==value["window"]["source_updated_at_min"]
    assert value["window"]["source_updated_at_missing_count"]==1
    assert value["window"]["intent_started_at_min"]=="2026-11-03T12:00:00.000000Z"


def test_privacy_allowlist_never_echoes_raw_diagnostics_policy_or_source_review_id(apple_database,tmp_path):
    engine=apple_database
    snapshot=replace(make_snapshot(engine),access_decision_ref="PRIVATE-ACCESS-POLICY",retention_policy_ref="PRIVATE-RETENTION-POLICY")
    c=controller(engine,tmp_path,[feed(("PRIVATE-SOURCE-REVIEW-ID",),body="PRIVATE-BODY"),feed(("second",))])
    rid=c.run_target(snapshot,uuid4()).run_id
    with engine.begin() as conn:
        conn.execute(update(R).where(R.c.id==rid).values(stop_reason="PRIVATE-EXCEPTION",
            anomalies=[{"code":"PRIVATE-EXCEPTION","body":"PRIVATE-BODY","author":"PRIVATE-AUTHOR"},
                {"code":"DIAGNOSTIC_TOTALS","counts":{"PRIVATE-COUNT-KEY":9,"EMPTY_PAGE":1}},
                {"code":"REFERENCE_SELECTION","excluded_candidate_count":1,"excluded_reason_counts":{"PRIVATE-EXCLUSION":1},
                    "excluded_candidates":[{"run_id":str(uuid4()),"reasons":["PRIVATE-REASON","INCOMPATIBLE_CONTRACT"]}]}]))
    value=report(engine,rid)
    encoded=json.dumps(value,ensure_ascii=False,allow_nan=False)
    assert "PRIVATE-" not in encoded
    assert value["stop_reason"]=="UNRECOGNIZED_STOP_REASON" and value["source_application_id"]=="572688855"


def test_batch_records_skipped_missing_and_unpersisted_without_fabricating_runs(apple_database,tmp_path):
    from feasibility.apple_ingestion.controller import RunResult
    engine=apple_database; snapshot=make_snapshot(engine)
    batch=uuid4()
    completed=controller(engine,tmp_path,[feed(("one",)),feed(("two",))]).run_target(snapshot,batch)
    skipped=RunResult(42,42,batch,None,None,None,"source_denied",run_persisted=False)
    intended=RunResult(43,43,batch,uuid4(),None,None,"db_error",finalized=False,recovery_required=True,run_persisted=None)
    with engine.connect() as c:
        value=batch_report(c,batch,(snapshot.target_id,42,43,44),outcomes=(completed,skipped,intended))
    assert value["recorded_target_count"]==value["skipped_target_count"]==value["missing_target_count"]==value["unpersisted_target_count"]==1
    assert value["expected_target_count"]==4 and value["evidence_kind"]=="synthetic"
    assert value["totals_by_evidence_kind"]["synthetic"]["run_count"]==1
    assert next(row for row in value["targets"] if row["target_id"]==43)["runs"]==[]
    json.dumps(value,allow_nan=False)


def batch_history(engine,snapshot,batch_id,at):
    from test_apple_ingestion_reconcile import locked
    from feasibility.apple_ingestion.contracts import ReviewRecord
    from feasibility.apple_ingestion.reconcile import persist_page
    rid=uuid4()
    with locked(engine,snapshot.application_id) as c:
        with c.begin():
            c.execute(insert(R).values(id=rid,target_id=snapshot.target_id,application_id=snapshot.application_id,
                batch_id=batch_id,started_at=at,execution_status="running",coverage_status="pending",config_snapshot=snapshot.to_dict()))
            aid=c.scalar(insert(F).values(run_id=rid,request_number=1,page_number=1,format="xml",attempt_number=1,
                started_at=at,finished_at=at,http_status=200,parsing_status="succeeded",persistence_status="pending",entry_count=1).returning(F.c.id))
        persist_page(c,rid,aid,(ReviewRecord("synthetic-one",None,"synthetic",4),),at)
        with c.begin():
            c.execute(update(R).where(R.c.id==rid).values(execution_status="succeeded",coverage_status="baseline",
                finished_at=at,stop_reason="synthetic_fixture"))
    return rid


def test_mixed_modes_are_tallied_separately_and_same_batch_multiple_runs_are_retained(apple_database):
    engine=apple_database; snapshot=make_snapshot(engine)
    live=replace(snapshot,run_mode=RunMode.LIVE,access_decision_ref="private",retention_policy_ref="private")
    batch=uuid4()
    first=batch_history(engine,snapshot,batch,NOW)
    second=batch_history(engine,live,batch,NOW+timedelta(days=1))
    with engine.connect() as c: value=batch_report(c,batch,(snapshot.target_id,))
    assert value["evidence_kind"]=="mixed"
    assert value["totals_by_evidence_kind"]["synthetic"]["run_count"]==1
    assert value["totals_by_evidence_kind"]["live"]["run_count"]==1
    assert len(value["targets"][0]["runs"])==2 and "totals" not in value


def test_unexpected_target_does_not_change_expected_denominator(apple_database,tmp_path):
    engine=apple_database; planned=make_snapshot(engine)
    unexpected=make_snapshot(engine,source_id="570060128")
    batch=uuid4()
    controller(engine,tmp_path,[feed(("one",)),feed(("two",))]).run_target(unexpected,batch)
    with engine.connect() as c: value=batch_report(c,batch,(planned.target_id,))
    assert value["expected_target_count"]==1 and value["recorded_target_count"]==0 and value["missing_target_count"]==1
    assert value["unexpected_target_ids"]==[unexpected.target_id] and value["unexpected_target_count"]==1
    assert len(value["targets"])==2 and value["totals_by_evidence_kind"]["synthetic"]["run_count"]==1


def test_terminal_or_unknown_outcome_blocks_stop_even_when_overlap_thresholds_met(apple_database,tmp_path):
    from feasibility.apple_ingestion.contracts import IngestionConfig
    engine=apple_database; snapshot=make_snapshot(engine,config=IngestionConfig(min_pages=1,min_overlap_count=1,min_overlap_ratio=1))
    prior=create_history(engine,snapshot,at=NOW-timedelta(days=1),pages=(("one",),))
    rid=controller(engine,tmp_path,[feed(("one",))]).run_target(snapshot,uuid4()).run_id
    assert report(engine,rid)["coverage"]["can_stop_on_overlap"]
    with engine.begin() as c:
        c.execute(update(R).where(R.c.id==rid).values(execution_status="interrupted",coverage_status="indeterminate"))
        c.execute(update(F).where(F.c.run_id==rid).values(error_codes=["REQUEST_OUTCOME_UNKNOWN"]))
    value=report(engine,rid)
    assert value["coverage"]["metrics"]["overlap_count_met"] and value["coverage"]["metrics"]["overlap_ratio_met"]
    assert not value["coverage"]["can_stop_on_overlap"]
    assert not value["coverage"]["stop_predicates"]["execution_allows_overlap_stop"]
    assert not value["coverage"]["stop_predicates"]["no_unrecovered_attempt_failure"]


def test_integrity_detects_service_invariants_without_repairs(apple_database,tmp_path):
    engine=apple_database; snapshot=make_snapshot(engine)
    rid=controller(engine,tmp_path,[feed(("one",)),feed(("two",))]).run_target(snapshot,uuid4()).run_id
    with engine.connect() as c: assert integrity_report(c)["ok"]
    with engine.begin() as c:
        version=dict(c.execute(select(V).order_by(V.c.id)).mappings().first())
        version.pop("id"); version["version_number"]=3
        c.execute(insert(V).values(**version))  # leaves valid owned pointer at V1
        c.execute(update(R).where(R.c.id==rid).values(coverage_status="pending"))
        c.execute(update(F).where(F.c.run_id==rid,F.c.page_number==2).values(parsing_status="pending",persistence_status="pending",finished_at=None))
        c.execute(update(O).where(O.c.run_id==rid).values(occurrence_count=O.c.occurrence_count+1))
    before={table.name:stored(engine,table) for table in (R,F,I,V,O)}
    with engine.connect() as c: value=integrity_report(c)
    assert not value["ok"]
    issues=value["issue_counts"]
    assert issues["CURRENT_VERSION_NOT_LATEST"]==issues["VERSION_NUMBER_GAPS"]==1
    assert issues["TERMINAL_PENDING_ATTEMPTS"]==issues["TERMINAL_PENDING_COVERAGE"]==1
    assert issues["PAGE_OBSERVATION_COUNT_MISMATCH"]==1
    assert before=={table.name:stored(engine,table) for table in (R,F,I,V,O)}
    assert value["source_deletion_inferred"] is False


def test_missing_committed_page_summary_is_unknown_not_zero_duplicate_positions(apple_database,tmp_path):
    engine=apple_database; snapshot=make_snapshot(engine)
    rid=controller(engine,tmp_path,[feed(("one",)),feed(("two",))]).run_target(snapshot,uuid4()).run_id
    with engine.begin() as c: c.execute(update(F).where(F.c.run_id==rid,F.c.page_number==1).values(anomalies=[]))
    value=report(engine,rid)
    assert value["observations"]["cross_page_duplicate_count"] is None
    assert value["observations"]["same_page_duplicate_count"] is None
    with engine.connect() as c:
        assert integrity_report(c)["issue_counts"]["COMMITTED_PAGE_SUMMARY_MISSING"]==1


def test_reports_work_under_report_role_and_execute_selects_only(apple_database,tmp_path):
    from feasibility.apple_ingestion.permissions import RoleConfig,apply_permissions
    engine=apple_database; snapshot=make_snapshot(engine)
    batch=uuid4(); rid=controller(engine,tmp_path,[feed(("one",)),feed(("two",))]).run_target(snapshot,batch).run_id
    suffix=uuid4().hex[:12]; runtime="report_test_writer_"+suffix; reader="report_test_reader_"+suffix
    with engine.begin() as c:
        owner=c.scalar(text("SELECT current_user"))
        c.exec_driver_sql(f'CREATE ROLE "{runtime}" NOLOGIN')
        c.exec_driver_sql(f'CREATE ROLE "{reader}" NOLOGIN')
        apply_permissions(c,RoleConfig(runtime,owner,reader))
    statements=[]
    def record_sql(conn,cursor,statement,parameters,context,executemany): statements.append(statement.lstrip().split(None,1)[0].upper())
    try:
        with engine.begin() as c:
            c.exec_driver_sql(f'SET LOCAL ROLE "{reader}"')
            c.exec_driver_sql('SET TRANSACTION READ ONLY')
            event.listen(c,"before_cursor_execute",record_sql)
            assert run_report(c,rid)["run_id"]==str(rid)
            assert batch_report(c,batch)["recorded_target_count"]==1
            assert integrity_report(c)["ok"]
            event.remove(c,"before_cursor_execute",record_sql)
        assert statements and set(statements)=={"SELECT"}
    finally:
        with engine.begin() as c:
            for role in (runtime,reader):
                c.exec_driver_sql(f'DROP OWNED BY "{role}"')
                c.exec_driver_sql(f'DROP ROLE "{role}"')


def test_lookup_errors_do_not_echo_supplied_identity(apple_database):
    with apple_database.connect() as c:
        with pytest.raises(ReportingError,match="INVALID_REPORT_ID"):
            run_report(c,"PRIVATE-INVALID-ID")
        with pytest.raises(ReportingError,match="RUN_NOT_FOUND"):
            run_report(c,uuid4())

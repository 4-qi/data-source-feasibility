"""Controller rehearsal uses fake byte responses and disposable PostgreSQL."""
from dataclasses import replace
from datetime import timedelta
import json
from pathlib import Path
from uuid import uuid4

import pytest
pytest.importorskip("sqlalchemy")
from sqlalchemy import event, select, text

from feasibility.apple_ingestion.contracts import IngestionConfig, RunMode
from feasibility.apple_ingestion.controller import Controller, ControllerError
from feasibility.apple_ingestion.models import Application, CollectionRun, FetchAttempt, ReviewObservation
from feasibility.apple_ingestion.transport import FetchResponse
from test_apple_ingestion_reference import NOW, create_history, make_snapshot

R,F,O=(model.__table__ for model in (CollectionRun,FetchAttempt,ReviewObservation))


def feed(ids,*,body="synthetic body"):
    entries=[{key:{"label":value} for key,value in {"id":value,"content":body,"im:rating":"4","title":"synthetic title"}.items()} for value in ids]
    payload=json.dumps({"feed":{"entry":entries}}).encode()
    return FetchResponse(200,payload,len(payload))


def xml(ids):
    payload=('<feed xmlns="http://www.w3.org/2005/Atom" xmlns:im="http://itunes.apple.com/rss">'+
        ''.join(f'<entry><id>{source_id}</id><content>synthetic body</content><im:rating>4</im:rating><title>synthetic title</title></entry>' for source_id in ids)+
        '</feed>').encode()
    return FetchResponse(200,payload,len(payload))


class Clock:
    def __init__(self,at=NOW): self.at=at
    def __call__(self): return self.at
    def advance(self,**kwargs): self.at+=timedelta(**kwargs)


class ScriptedTransport:
    def __init__(self,engine,responses,callback=None):
        self.engine,self.responses,self.callback=engine,list(responses),callback
        self.calls=[]
    def fetch(self,app,page,format,config,*,deadline=None):
        # A second connection must see the intent before the fake HTTP begins.
        with self.engine.connect() as c:
            intent=c.execute(select(F).where(F.c.parsing_status=="pending",F.c.persistence_status=="pending")).mappings().one()
            assert intent["page_number"]==page and intent["format"]==format.value
        self.calls.append((app,page,format.value))
        if self.callback: self.callback(len(self.calls))
        if not self.responses: raise AssertionError("unexpected synthetic request")
        value=self.responses.pop(0)
        if isinstance(value,BaseException): raise value
        return value


def controller(engine,tmp_path,responses,*,clock=None,callback=None,monotonic=None):
    from feasibility.apple_ingestion.recovery import DiagnosticSpool
    transport=ScriptedTransport(engine,responses,callback)
    spool=DiagnosticSpool(tmp_path/"private-diagnostics.jsonl")
    kwargs={"now":clock or Clock()}
    if monotonic is not None: kwargs["monotonic"]=monotonic
    return Controller(engine,transport,spool,**kwargs)


def stored(engine,table):
    with engine.connect() as c:
        return [dict(row) for row in c.execute(select(table)).mappings()]


def assert_terminal(engine):
    for run in stored(engine,R):
        assert run["execution_status"]!="running" and run["coverage_status"]!="pending"
    for attempt in stored(engine,F):
        assert attempt["parsing_status"]!="pending" and attempt["persistence_status"] not in {"pending","unknown"}


def test_json_empty_falls_back_once_and_commits_one_logical_page(apple_database,tmp_path):
    engine=apple_database; snapshot=make_snapshot(engine)
    c=controller(engine,tmp_path,[feed(()),xml(("id-1",)),feed(("id-2",))])
    result=c.run_target(snapshot,uuid4())
    assert (result.execution_status,result.coverage_status,result.request_count,result.committed_pages)==("succeeded","baseline",3,2)
    assert result.comparison_eligible
    assert [(page,fmt) for _,page,fmt in c.transport.calls]==[(1,"json"),(1,"xml"),(2,"json")]
    attempts=stored(engine,F)
    assert [row["persistence_status"] for row in attempts]==["not_applicable","committed","committed"]
    assert_terminal(engine)


def test_all_empty_keeps_five_pages_ten_requests_and_reports_no_anchor(apple_database,tmp_path):
    engine=apple_database; snapshot=make_snapshot(engine,config=IngestionConfig())
    c=controller(engine,tmp_path,[value for _ in range(5) for value in (feed(()),xml(()))])
    result=c.run_target(snapshot,uuid4())
    assert result.execution_status=="succeeded" and result.coverage_status=="empty_window"
    assert not result.comparison_eligible and result.committed_pages==5 and result.request_count==10
    assert len(stored(engine,O))==0
    assert_terminal(engine)


@pytest.mark.parametrize("response,stop,reason",[
    (FetchResponse(403,b"",0),"http_denied","HTTP_DENIED"),
    (FetchResponse(429,b"",0),"http_denied","HTTP_RATE_LIMIT"),
    (FetchResponse(500,b"",0),"transport_error","HTTP_NON_200"),
    (FetchResponse(None,b"",0,"TRANSPORT_TIMEOUT"),"transport_error","TRANSPORT_TIMEOUT"),
    (FetchResponse(200,b"malformed private text",22),"parse_error","FEED_SCHEMA"),
])
def test_unrecovered_failure_never_retries_or_falls_back(apple_database,tmp_path,response,stop,reason):
    engine=apple_database; snapshot=make_snapshot(engine)
    c=controller(engine,tmp_path,[response])
    result=c.run_target(snapshot,uuid4())
    assert result.execution_status=="failed" and result.coverage_status=="indeterminate"
    assert result.stop_reason==stop and reason in result.reason_codes
    assert result.request_count==1 and not result.comparison_eligible
    assert len(c.transport.calls)==1
    assert "malformed private text" not in json.dumps(stored(engine,R),default=str)
    assert_terminal(engine)


def test_prior_page_survives_later_parse_failure_as_partial(apple_database,tmp_path):
    engine=apple_database; snapshot=make_snapshot(engine)
    c=controller(engine,tmp_path,[feed(("first",)),FetchResponse(200,b"bad",3)])
    result=c.run_target(snapshot,uuid4())
    assert result.execution_status=="partial" and result.committed_pages==1
    assert len(stored(engine,O))==1 and not result.comparison_eligible
    assert_terminal(engine)


@pytest.mark.parametrize("empty,execution,pages,coverage",[(True,"failed",0,"indeterminate"),(False,"succeeded",1,"baseline")])
def test_request_budget_distinguishes_incomplete_fallback_from_between_pages(apple_database,tmp_path,empty,execution,pages,coverage):
    engine=apple_database; snapshot=make_snapshot(engine,config=IngestionConfig(max_http_requests=1))
    c=controller(engine,tmp_path,[feed(() if empty else ("one",))])
    result=c.run_target(snapshot,uuid4())
    assert (result.execution_status,result.committed_pages,result.coverage_status)==(execution,pages,coverage)
    assert result.stop_reason=="request_budget" and result.request_count==1
    assert result.comparison_eligible is (not empty)
    assert_terminal(engine)


def test_insufficient_reference_chain_uses_latest_run_without_lowering_thresholds(apple_database,tmp_path):
    engine=apple_database; snapshot=make_snapshot(engine)
    clock=Clock(); previous=None
    for day in range(4):
        c=controller(engine,tmp_path,[feed((f"id-{day}",)),feed((f"other-{day}",))],clock=clock)
        result=c.run_target(snapshot,uuid4())
        assert result.reference_run_id==previous
        assert result.coverage_status==("baseline" if previous is None else "overlap_insufficient")
        assert result.comparison_eligible
        previous=result.run_id
        clock.advance(days=1)
    assert len(stored(engine,R))==4


def test_exact_overlap_thresholds_stop_at_minimum_pages_even_with_old_reference(apple_database,tmp_path):
    engine=apple_database; snapshot=make_snapshot(engine,config=IngestionConfig())
    refs=tuple(f"id-{n}" for n in range(20))
    baseline=create_history(engine,snapshot,pages=(refs,),at=NOW)
    clock=Clock(NOW+timedelta(hours=73))
    c=controller(engine,tmp_path,[feed(refs[:10]),feed(refs[10:])],clock=clock)
    result=c.run_target(snapshot,uuid4())
    assert result.reference_run_id==baseline and result.stop_reason=="overlap_met"
    assert result.committed_pages==2 and result.coverage_status=="overlap_sufficient"
    assert "REFERENCE_AGE_WARNING" in result.reason_codes and result.comparison_eligible


def test_cross_page_conflict_blocks_early_stop_and_reference_eligibility(apple_database,tmp_path):
    engine=apple_database; snapshot=make_snapshot(engine)
    c=controller(engine,tmp_path,[feed(("id-1",)),feed(("id-1",),body="synthetic alternate")])
    result=c.run_target(snapshot,uuid4())
    assert result.execution_status=="partial" and result.coverage_status=="indeterminate"
    assert result.stop_reason=="consistency_anomaly" and not result.comparison_eligible
    assert stored(engine,O)[0]["conflict_count"]==1
    clock=Clock(NOW+timedelta(days=1))
    next_controller=controller(engine,tmp_path,[feed(("new-a",)),feed(("new-b",))],clock=clock)
    assert next_controller.run_target(snapshot,uuid4()).reference_run_id is None


def test_coverage_only_duplicate_page_remains_usable_next_reference(apple_database,tmp_path):
    engine=apple_database; snapshot=make_snapshot(engine)
    c=controller(engine,tmp_path,[feed(("id-1",)),feed(("id-1",))])
    first=c.run_target(snapshot,uuid4())
    assert first.execution_status=="succeeded" and first.coverage_status=="indeterminate" and first.comparison_eligible
    next_controller=controller(engine,tmp_path,[feed(("id-1",)),feed(("new-id",))],clock=Clock(NOW+timedelta(days=1)))
    assert next_controller.run_target(snapshot,uuid4()).reference_run_id==first.run_id


def test_incompatible_history_creates_annotated_anchor_then_next_run_compares(apple_database,tmp_path):
    engine=apple_database; snapshot=make_snapshot(engine)
    create_history(engine,replace(snapshot,parser_version="old-synthetic-parser"))
    c=controller(engine,tmp_path,[feed(("one",)),feed(("two",))],clock=Clock(NOW+timedelta(days=1)))
    first=c.run_target(snapshot,uuid4())
    assert first.coverage_status=="no_reference" and "REFERENCE_CHAIN_RESTARTED" in first.reason_codes
    c=controller(engine,tmp_path,[feed(("one",)),feed(("two",))],clock=Clock(NOW+timedelta(days=2)))
    assert c.run_target(snapshot,uuid4()).reference_run_id==first.run_id


def test_operator_interruption_resolves_pending_intent_without_fake_http_outcome(apple_database,tmp_path):
    engine=apple_database; snapshot=make_snapshot(engine)
    c=controller(engine,tmp_path,[KeyboardInterrupt()])
    result=c.run_target(snapshot,uuid4())
    assert result.execution_status=="interrupted" and result.coverage_status=="indeterminate"
    attempt=stored(engine,F)[0]
    assert attempt["http_status"] is None and attempt["parsing_status"]=="not_attempted"
    assert "REQUEST_OUTCOME_UNKNOWN" in attempt["error_codes"]
    assert_terminal(engine)


def test_deadline_after_response_marks_uncommitted_page_failed(apple_database,tmp_path):
    engine=apple_database; snapshot=make_snapshot(engine)
    tick=[0.0]
    c=controller(engine,tmp_path,[feed(("one",))],monotonic=lambda:tick[0],callback=lambda n:tick.__setitem__(0,1000.0))
    result=c.run_target(snapshot,uuid4())
    assert result.execution_status=="failed" and result.stop_reason=="target_deadline"
    assert len(stored(engine,O))==0 and stored(engine,F)[0]["persistence_status"]=="rolled_back"
    assert_terminal(engine)


def test_live_and_wrong_identity_rejected_without_transport_or_run(apple_database,tmp_path):
    engine=apple_database; snapshot=make_snapshot(engine)
    c=controller(engine,tmp_path,[])
    live=replace(snapshot,run_mode=RunMode.LIVE,access_decision_ref="fixture",retention_policy_ref="fixture")
    with pytest.raises(ControllerError,match="LIVE_MODE_DISABLED"): c.run_target(live,uuid4())
    with pytest.raises(ControllerError,match="TARGET_SNAPSHOT_IDENTITY_MISMATCH"):
        c.run_target(replace(snapshot,source_application_id="570060128"),uuid4())
    assert c.transport.calls==[] and stored(engine,R)==[]


def test_lock_busy_skips_without_run_or_request(apple_database,tmp_path):
    from feasibility.apple_ingestion.recovery import application_session
    engine=apple_database; snapshot=make_snapshot(engine)
    c=controller(engine,tmp_path,[])
    with application_session(engine,snapshot.application_id):
        result=c.run_target(snapshot,uuid4())
    assert result.skipped and result.stop_reason=="application_locked"
    assert not result.recovery_required and c.transport.calls==[] and stored(engine,R)==[]


def test_batch_denial_stops_source_and_preserves_all_eight_target_outcomes(apple_database,tmp_path):
    from feasibility.apple_ingestion.seed import seed_defaults
    from feasibility.apple_ingestion.contracts import ConfigSnapshot
    from feasibility.apple_ingestion.parser import PARSER_VERSION
    root=Path(__file__).resolve().parents[1]
    with apple_database.begin() as conn:
        seeded=seed_defaults(conn,root/"results/mainstream/app_sample_manifest.json")
        app_ids={row.id:row.source_application_id for row in conn.execute(select(Application.__table__))}
    snapshots=tuple(ConfigSnapshot(app,app_ids[app],target,"synthetic",PARSER_VERSION)
        for app,target in zip(seeded.application_ids,seeded.target_ids))
    c=controller(apple_database,tmp_path,[FetchResponse(401,b"",0)])
    results=c.run_batch(snapshots,uuid4())
    assert len(results)==8 and results[0].source_stop and all(item.skipped for item in results[1:])
    assert len(c.transport.calls)==1 and len(stored(apple_database,R))==1


def test_attempt_intent_database_failure_spools_without_sending_request(apple_database,tmp_path):
    engine=apple_database; snapshot=make_snapshot(engine)
    c=controller(engine,tmp_path,[])
    def fail_insert(conn,cursor,statement,parameters,context,executemany):
        if statement.startswith("INSERT INTO fetch_attempt"):
            raise RuntimeError("PRIVATE_DATABASE_FAILURE")
    event.listen(engine,"before_cursor_execute",fail_insert)
    try: result=c.run_target(snapshot,uuid4())
    finally: event.remove(engine,"before_cursor_execute",fail_insert)
    assert not result.finalized and result.recovery_required
    assert c.transport.calls==[] and stored(engine,F)==[]
    spool=(tmp_path/"private-diagnostics.jsonl").read_text()
    assert "DB_UNAVAILABLE" in spool and "PRIVATE_DATABASE_FAILURE" not in spool


def test_database_and_spool_failure_surfaces_non_durable_operational_error(apple_database,tmp_path,monkeypatch):
    engine=apple_database; snapshot=make_snapshot(engine)
    c=controller(engine,tmp_path,[])
    monkeypatch.setattr(c.spool,"append",lambda *args: (_ for _ in ()).throw(OSError("PRIVATE_DISK_FAILURE")))
    def fail_insert(conn,cursor,statement,parameters,context,executemany):
        if statement.startswith("INSERT INTO fetch_attempt"): raise RuntimeError("PRIVATE_DB_FAILURE")
    event.listen(engine,"before_cursor_execute",fail_insert)
    try:
        with pytest.raises(ControllerError,match="DIAGNOSTIC_DURABILITY_FAILED") as caught:
            c.run_target(snapshot,uuid4())
    finally: event.remove(engine,"before_cursor_execute",fail_insert)
    assert not caught.value.diagnostics_durable and c.transport.calls==[]


def test_explicit_configuration_is_frozen_and_used_without_replacing_defaults(apple_database,tmp_path):
    config=IngestionConfig(min_pages=1,max_pages=3,min_overlap_count=1,min_overlap_ratio=1,max_http_requests=3)
    snapshot=make_snapshot(apple_database,config=config)
    prior=create_history(apple_database,snapshot,at=NOW-timedelta(days=1),pages=(("one",),))
    c=controller(apple_database,tmp_path,[feed(("one",))])
    result=c.run_target(snapshot,uuid4())
    assert result.reference_run_id==prior and result.stop_reason=="overlap_met" and result.committed_pages==1
    stored_snapshot=next(row for row in stored(apple_database,R) if row["id"]==result.run_id)["config_snapshot"]
    assert stored_snapshot["config"]==config.to_dict()
    defaults=IngestionConfig()
    assert (defaults.min_pages,defaults.max_pages,defaults.min_overlap_count,defaults.min_overlap_ratio,defaults.max_http_requests)==(2,5,20,.2,10)


def test_failure_before_lock_still_has_spoolable_intended_uuid(apple_database,tmp_path,monkeypatch):
    engine=apple_database; snapshot=make_snapshot(engine)
    c=controller(engine,tmp_path,[])
    with monkeypatch.context() as scoped:
        scoped.setattr(engine,"connect",lambda: (_ for _ in ()).throw(RuntimeError("PRIVATE_CONNECT_FAILURE")))
        result=c.run_target(snapshot,uuid4())
    assert result.run_id is not None and not result.run_persisted and not result.finalized
    assert result.recovery_required and c.transport.calls==[] and stored(engine,R)==[]
    saved=json.loads((tmp_path/"private-diagnostics.jsonl").read_text().strip())
    assert saved["run_id"]==str(result.run_id) and saved["stage"]=="intent"
    assert "PRIVATE_CONNECT_FAILURE" not in json.dumps(saved)


def test_run_intent_commit_failure_does_not_claim_database_row_or_send_http(apple_database,tmp_path):
    engine=apple_database; snapshot=make_snapshot(engine)
    c=controller(engine,tmp_path,[])
    def mark_run(conn,cursor,statement,parameters,context,executemany):
        if statement.startswith("INSERT INTO collection_run"): conn.info["fail_test_run_commit"]=True
    def fail_commit(conn):
        if conn.info.pop("fail_test_run_commit",False): raise RuntimeError("PRIVATE_COMMIT_FAILURE")
    event.listen(engine,"after_cursor_execute",mark_run); event.listen(engine,"commit",fail_commit)
    try: result=c.run_target(snapshot,uuid4())
    finally:
        event.remove(engine,"after_cursor_execute",mark_run); event.remove(engine,"commit",fail_commit)
    assert not result.finalized and not result.run_persisted and result.recovery_required
    assert c.transport.calls==[] and stored(engine,R)==[]
    assert (tmp_path/"private-diagnostics.jsonl").exists()
    # Replaying an intended UUID without a DB row never fabricates that row.
    next_controller=controller(engine,tmp_path,[feed(("one",)),feed(("two",))])
    assert next_controller.run_target(snapshot,uuid4()).execution_status=="succeeded"
    assert len(stored(engine,R))==1


def test_session_loss_during_second_response_preserves_first_page_and_restarts_page_one(apple_database,tmp_path):
    engine=apple_database; snapshot=make_snapshot(engine)
    def lose_session(number):
        if number==2:
            with engine.begin() as admin:
                pid=admin.scalar(text("SELECT pid FROM pg_locks WHERE locktype='advisory' AND pid<>pg_backend_pid()"))
                assert admin.scalar(text("SELECT pg_terminate_backend(:pid)"),{"pid":pid})
    c=controller(engine,tmp_path,[feed(("one",)),feed(("two",))],callback=lose_session)
    result=c.run_target(snapshot,uuid4())
    assert result.recovery_required and not result.finalized and result.committed_pages==1 and result.request_count==2
    assert len(stored(engine,O))==1
    assert next(row for row in stored(engine,R) if row["id"]==result.run_id)["execution_status"]=="running"
    next_controller=controller(engine,tmp_path,[feed(("one",)),feed(("two",))],clock=Clock(NOW+timedelta(days=1)))
    resumed=next_controller.run_target(snapshot,uuid4())
    assert resumed.run_id!=result.run_id and resumed.execution_status=="succeeded"
    assert next_controller.transport.calls[0][1]==1
    old=next(row for row in stored(engine,R) if row["id"]==result.run_id)
    assert old["execution_status"]=="interrupted" and resumed.reference_run_id is None
    old_attempt=next(row for row in stored(engine,F) if row["run_id"]==result.run_id and row["page_number"]==2)
    assert old_attempt["http_status"] is None and "REQUEST_OUTCOME_UNKNOWN" in old_attempt["error_codes"]
    assert_terminal(engine)


def test_session_loss_after_page_commit_keeps_marker_and_prevents_another_request(apple_database,tmp_path,monkeypatch):
    import feasibility.apple_ingestion.controller as implementation
    engine=apple_database; snapshot=make_snapshot(engine)
    original=implementation.persist_page
    def commit_then_lose(connection,*args,**kwargs):
        result=original(connection,*args,**kwargs)
        connection.invalidate()
        return result
    c=controller(engine,tmp_path,[feed(("one",))])
    with monkeypatch.context() as scoped:
        scoped.setattr(implementation,"persist_page",commit_then_lose)
        result=c.run_target(snapshot,uuid4())
    assert result.recovery_required and result.committed_pages==1 and len(c.transport.calls)==1
    first=stored(engine,F)[0]
    assert first["persistence_status"]=="committed" and len(stored(engine,O))==1
    next_controller=controller(engine,tmp_path,[feed(("one",)),feed(("two",))],clock=Clock(NOW+timedelta(days=1)))
    assert next_controller.run_target(snapshot,uuid4()).execution_status=="succeeded"
    original_attempt=next(row for row in stored(engine,F) if row["id"]==first["id"])
    assert original_attempt["persistence_status"]=="committed"


def test_commit_acknowledgement_error_is_resolved_by_marker_without_replay(apple_database,tmp_path,monkeypatch):
    import feasibility.apple_ingestion.controller as implementation
    from feasibility.apple_ingestion.reconcile import ReconciliationError
    engine=apple_database; snapshot=make_snapshot(engine)
    original=implementation.persist_page
    calls=[]
    def commit_then_unknown(*args,**kwargs):
        calls.append(args[2]); original(*args,**kwargs)
        raise ReconciliationError("DB_UNAVAILABLE")
    monkeypatch.setattr(implementation,"persist_page",commit_then_unknown)
    c=controller(engine,tmp_path,[feed(("one",)),feed(("two",))])
    result=c.run_target(snapshot,uuid4())
    assert result.execution_status=="succeeded" and result.comparison_eligible
    assert len(calls)==2 and len(c.transport.calls)==2
    assert [row["occurrence_count"] for row in stored(engine,O)]==[1,1]
    assert_terminal(engine)

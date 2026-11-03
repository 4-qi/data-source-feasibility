"""Reference eligibility and coverage are independent synthetic decisions."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
pytest.importorskip("sqlalchemy")
from sqlalchemy import insert, select, text, update

from feasibility.apple_ingestion.contracts import ConfigSnapshot, IngestionConfig, ReviewRecord, RunMode
from feasibility.apple_ingestion.models import Application, CollectionTarget, CollectionRun, FetchAttempt
from feasibility.apple_ingestion.parser import PARSER_VERSION
from feasibility.apple_ingestion.reconcile import application_lock_key, persist_page
from feasibility.apple_ingestion.reference import (
    classify_coverage, comparison_eligibility, coverage_metrics, select_reference,
)

A,T,R,F = (model.__table__ for model in (Application, CollectionTarget, CollectionRun, FetchAttempt))
NOW = datetime(2026,11,3,12,tzinfo=timezone.utc)


def make_snapshot(engine, *, config=None, source_id="572688855"):
    config = config or IngestionConfig(max_pages=2)
    with engine.begin() as c:
        app = c.scalar(insert(A).values(source="apple_app_store", source_application_id=source_id,
            name="Synthetic", analytical_category="education").returning(A.c.id))
        target = c.scalar(insert(T).values(application_id=app, storefront="us", sort_by="mostrecent",
            **{name:getattr(config,name) for name in ("interval_hours", "min_pages", "max_pages", "min_overlap_count",
                "min_overlap_ratio", "max_http_requests", "reference_max_age_hours")}).returning(T.c.id))
    return ConfigSnapshot(app,source_id,target,"synthetic-test",PARSER_VERSION,config=config)


def create_history(engine,snapshot,*,at=NOW,pages=(("id-1",),),coverage="baseline",status="succeeded"):
    rid=uuid4()
    with engine.connect() as c:
        key=application_lock_key(snapshot.application_id)
        c.execute(text("SELECT pg_advisory_lock(:key)"),{"key":key}); c.commit()
        try:
            with c.begin():
                c.execute(insert(R).values(id=rid,target_id=snapshot.target_id,application_id=snapshot.application_id,
                    batch_id=uuid4(),started_at=at,execution_status="running",coverage_status="pending",config_snapshot=snapshot.to_dict()))
            for page,ids in enumerate(pages,1):
                records=tuple(ReviewRecord(source_id,None,"synthetic",4) for source_id in ids)
                observed=at+timedelta(seconds=page)
                with c.begin():
                    aid=c.scalar(insert(F).values(run_id=rid,request_number=page,page_number=page,format="xml",
                        attempt_number=1,started_at=at,finished_at=observed,http_status=200,parsing_status="succeeded",
                        persistence_status="pending",entry_count=len(records)).returning(F.c.id))
                persist_page(c,rid,aid,records,observed)
            with c.begin():
                c.execute(update(R).where(R.c.id==rid).values(execution_status=status,coverage_status=coverage,
                    finished_at=at+timedelta(seconds=len(pages)+1),stop_reason="synthetic"))
        finally:
            c.rollback(); c.execute(text("SELECT pg_advisory_unlock(:key)"),{"key":key}); c.commit()
    return rid


def decision(engine,snapshot,at=NOW+timedelta(days=10)):
    with engine.connect() as c:
        return select_reference(c,snapshot,at)


def test_latest_successful_insufficient_reference_keeps_chain_moving(apple_database):
    engine=apple_database; snapshot=make_snapshot(engine)
    ids=[]
    for day in range(4):
        ids.append(create_history(engine,snapshot,at=NOW+timedelta(days=day),coverage="baseline" if day==0 else "overlap_insufficient"))
        assert decision(engine,snapshot,NOW+timedelta(days=day+1)).reference_run_id==ids[-1]
    newer_failed=create_history(engine,snapshot,at=NOW+timedelta(days=5),status="partial",coverage="indeterminate")
    result=decision(engine,snapshot)
    assert result.reference_run_id==ids[-1]
    assert any(item.run_id==newer_failed for item in result.exclusions)


def test_successful_nonempty_empty_and_duplicate_only_cautions_are_eligible(apple_database):
    engine=apple_database; snapshot=make_snapshot(engine,config=IngestionConfig(max_pages=3))
    rid=create_history(engine,snapshot,pages=(("id-1",),(),("id-1",)),coverage="indeterminate")
    with engine.begin() as c:
        c.execute(update(F).where(F.c.run_id==rid).values(error_codes=["EMPTY_PAGE"]))
    assert decision(engine,snapshot).reference_run_id==rid


@pytest.mark.parametrize("hours,warn",[(72,False),(72.0001,True)])
def test_reference_age_is_strict_warning_not_cutoff(apple_database,hours,warn):
    engine=apple_database; snapshot=make_snapshot(engine)
    rid=create_history(engine,snapshot)
    at=NOW+timedelta(seconds=2,hours=hours)
    result=decision(engine,snapshot,at)
    assert result.reference_run_id==rid and result.age_warning is warn
    assert result.age_hours==pytest.approx(hours)


def test_only_other_run_mode_history_does_not_create_restart(apple_database):
    engine=apple_database; snapshot=make_snapshot(engine)
    other=replace(snapshot,run_mode=RunMode.LIVE,access_decision_ref="synthetic-record-only",retention_policy_ref="synthetic-record-only")
    create_history(engine,other)
    result=decision(engine,snapshot)
    assert result.reference_run_id is None and not result.had_usable_history and not result.chain_restart
    assert "RUN_MODE_MISMATCH" in result.exclusions[0].reasons


def test_same_mode_incompatible_parser_history_restarts_then_new_anchor_is_usable(apple_database):
    engine=apple_database; snapshot=make_snapshot(engine)
    create_history(engine,replace(snapshot,parser_version="old-fixture-contract"))
    result=decision(engine,snapshot)
    assert result.chain_restart and result.had_usable_history
    rid=create_history(engine,snapshot,at=NOW+timedelta(days=1),coverage="no_reference")
    assert decision(engine,snapshot).reference_run_id==rid


@pytest.mark.parametrize("defect",["pending_coverage","snapshot_identity","unresolved","parse_failure","rolled_back","unknown_time"])
def test_defective_candidates_do_not_become_reference(apple_database,defect):
    engine=apple_database; snapshot=make_snapshot(engine)
    baseline=create_history(engine,snapshot)
    candidate=replace(snapshot,source_application_id="wrong-app") if defect=="snapshot_identity" else snapshot
    bad=create_history(engine,candidate,at=NOW+timedelta(days=1))
    with engine.begin() as c:
        if defect=="pending_coverage": c.execute(update(R).where(R.c.id==bad).values(coverage_status="pending"))
        if defect=="unresolved": c.execute(update(F).where(F.c.run_id==bad).values(persistence_status="pending"))
        if defect=="parse_failure": c.execute(update(F).where(F.c.run_id==bad).values(parsing_status="failed",persistence_status="not_applicable"))
        if defect=="rolled_back": c.execute(update(F).where(F.c.run_id==bad).values(persistence_status="rolled_back"))
        if defect=="unknown_time": c.execute(update(F).where(F.c.run_id==bad).values(finished_at=None))
    result=decision(engine,snapshot)
    assert result.reference_run_id==baseline
    assert any(item.run_id==bad and item.reasons for item in result.exclusions)


def test_empty_history_is_not_an_anchor_and_future_finish_is_not_earlier(apple_database):
    engine=apple_database; snapshot=make_snapshot(engine)
    create_history(engine,snapshot,pages=((),),coverage="empty_window")
    assert not decision(engine,snapshot).had_usable_history
    future=create_history(engine,snapshot,at=NOW+timedelta(days=1))
    result=decision(engine,snapshot,NOW+timedelta(days=1,seconds=1))
    assert result.reference_run_id is None and not result.had_usable_history
    assert any(item.run_id==future and "NOT_FINISHED_EARLIER" in item.reasons for item in result.exclusions)


@pytest.mark.parametrize("current,reference,overlap,expected",[
    (12,12,12,{"OBSERVABLE_WINDOW_BELOW_COUNT_THRESHOLD","REFERENCE_WINDOW_BELOW_COUNT_THRESHOLD"}),
    (50,50,5,{"LOW_ID_OVERLAP_COUNT","LOW_ID_OVERLAP_RATIO"}),
    (10,50,1,{"OBSERVABLE_WINDOW_BELOW_COUNT_THRESHOLD","LOW_ID_OVERLAP_RATIO"}),
])
def test_low_volume_and_low_overlap_are_independent(current,reference,overlap,expected):
    metrics=coverage_metrics(range(current),list(range(overlap))+list(range(1000,1000+reference-overlap)),2,IngestionConfig())
    assert set(metrics.reason_codes)==expected
    assert metrics.max_possible_overlap==min(current,reference)
    assert classify_coverage(metrics,execution_status="succeeded",conflict=False,coverage_caution=False,had_usable_history=True)=="overlap_insufficient"


def test_all_thresholds_and_coverage_priority_are_exact():
    config=IngestionConfig()
    refs=set(range(20))
    current=set(range(100))
    met=coverage_metrics(current,refs,2,config)
    assert met.thresholds_met and met.overlap_ratio==.2
    assert not coverage_metrics(current,refs,1,config).thresholds_met
    assert not coverage_metrics(current|{100},refs,2,config).thresholds_met
    assert not coverage_metrics(current,range(19),2,config).thresholds_met
    for status,conflict,caution,expected in [("succeeded",False,False,"overlap_sufficient"),("partial",False,False,"indeterminate"),
        ("succeeded",True,False,"indeterminate"),("succeeded",False,True,"indeterminate")]:
        assert classify_coverage(met,execution_status=status,conflict=conflict,coverage_caution=caution,had_usable_history=True)==expected
    empty=coverage_metrics((),refs,2,config)
    assert empty.overlap_ratio is None
    assert classify_coverage(empty,execution_status="succeeded",conflict=False,coverage_caution=True,had_usable_history=True)=="empty_window"
    no_ref=coverage_metrics((1,),None,1,config)
    assert no_ref.reference_count is no_ref.overlap_count is no_ref.overlap_ratio is no_ref.max_possible_overlap is None

"""Offline project-policy tests; no real access confirmation or HTTP sockets."""
from dataclasses import replace
from datetime import timedelta
import json
from uuid import uuid4

import pytest
pytest.importorskip("sqlalchemy")

from feasibility.apple_ingestion.contracts import IngestionConfig
from feasibility.apple_ingestion.live import (
    LivePolicyError,ProjectExecutionConfig,ProjectExecutionPolicy,project_policy_template,prepare_project_controller,
)
from test_apple_ingestion_live_readiness import ready,OfflineAdapter,factory_for,rows,R,F
from test_apple_ingestion_deployment import deployed_roles
from test_apple_ingestion_phase_c_integration import Clock,feed,assert_terminal_resolved
from test_apple_ingestion_reference import NOW


def configured(ready,tmp_path,*,file_backed=False):
    config,engines,env,legacy_snapshot,spool=ready
    value=ProjectExecutionConfig(policy_id=uuid4(),operator="offline-fixture-operator",execution_enabled=True,
        access_arrangement_confirmed=True,access_basis_ref="offline-fixture-project-basis-not-real-confirmation",
        valid_from=NOW,valid_until=NOW+timedelta(days=7),source_application_ids=(legacy_snapshot.source_application_id,),
        config=legacy_snapshot.config)
    path=tmp_path/"offline-project-policy.json"
    if file_backed:
        path.write_text(json.dumps(value.to_dict()))
        policy=ProjectExecutionPolicy(config_path=path)
    else: policy=ProjectExecutionPolicy(value)
    snapshot=policy.make_snapshot(application_id=legacy_snapshot.application_id,source_application_id=legacy_snapshot.source_application_id,
        target_id=legacy_snapshot.target_id,software_revision="offline-project-policy",retention_policy_ref=config.retention.policy_ref)
    return value,policy,snapshot,path


def prepare(ready,policy,clock,session_factory):
    config,engines,env,_,spool=ready
    return prepare_project_controller(engines["runtime"],spool,policy=policy,deployment_config=config,audit_engine=engines["owner"],
        environ=env,session_factory=session_factory,now=clock.now,clock=clock.monotonic,sleep=clock.sleep)


def test_pending_smoke_and_pilot_templates_are_strict_and_do_not_authorize():
    for purpose,count in (("smoke",1),("pilot",8)):
        payload=project_policy_template(purpose=purpose)
        value=ProjectExecutionConfig.from_dict(payload)
        assert value.policy_id is value.valid_from is value.valid_until is None
        assert not value.execution_enabled
        assert "access_arrangement_confirmed" not in payload and "access_basis_ref" not in payload
        assert len(value.source_application_ids)==count and value.config.interval_hours==24
    assert project_policy_template()["source_application_ids"]==["572688855"]
    policy=ProjectExecutionPolicy(ProjectExecutionConfig.from_dict(project_policy_template()))
    with pytest.raises(LivePolicyError,match="PROJECT_EXECUTION_DISABLED"):
        with prepare_project_controller(object(),object(),policy=policy,session_factory=lambda:pytest.fail("pending Session")): pass


@pytest.mark.parametrize("change",[
    {"valid_from":NOW,"valid_until":NOW+timedelta(days=7,seconds=1)},
    {"source_application_ids":("572688855","570060128")},
    {"config":IngestionConfig(global_spacing_seconds=1)},
    {"config":IngestionConfig(max_http_requests=11)},
    {"config":IngestionConfig(interval_hours=12)},
    {"config":IngestionConfig(min_pages=1)},
    {"config":IngestionConfig(min_overlap_count=1)},
    {"config":IngestionConfig(min_overlap_ratio=.1)},
])
def test_project_scope_window_and_original_operational_caps_cannot_expand(change):
    with pytest.raises(LivePolicyError,match="PROJECT_POLICY_INVALID"):
        ProjectExecutionConfig(**change)


def test_one_project_configuration_supports_multiple_runs_without_receipts_and_keeps_spacing(ready,tmp_path):
    value,policy,snapshot,_=configured(ready,tmp_path)
    _,engines,_,_,_=ready; clock=Clock()
    adapter=OfflineAdapter(engines["runtime"],clock,[(200,feed(("one",))),(200,feed(("two",)))]*2)
    factory,sessions=factory_for(adapter)
    with prepare(ready,policy,clock,factory) as controller:
        first=controller.run_target(snapshot,uuid4())
        clock.seconds+=.1  # strictly finished-earlier reference, not a 24h embargo
        second=controller.run_target(snapshot,uuid4())
    assert first.execution_status==second.execution_status=="succeeded"
    assert second.reference_run_id==first.run_id
    assert [call[3] for call in adapter.calls]==[0,2,4,6] and len(sessions)==1
    assert not (tmp_path/"private-approval-receipts").exists()
    saved=rows(engines["runtime"],R)
    assert len(saved)==2
    assert all(row["config_snapshot"]["access_decision_ref"]==policy.access_decision_ref for row in saved)
    assert str(value.policy_id) in policy.access_decision_ref and ":sha256:" in policy.access_decision_ref
    assert_terminal_resolved(engines["runtime"])


def test_smoke_cannot_automatically_expand_to_batch(ready,tmp_path):
    _,policy,snapshot,_=configured(ready,tmp_path); _,engines,_,_,_=ready; clock=Clock()
    adapter=OfflineAdapter(engines["runtime"],clock,[]); factory,sessions=factory_for(adapter)
    with prepare(ready,policy,clock,factory) as controller:
        with pytest.raises(LivePolicyError,match="PROJECT_SMOKE_ONE_APP_ONLY"):
            controller.run_batch((snapshot,)*8,uuid4())
        with pytest.raises(LivePolicyError,match="PROJECT_POLICY_SCOPE_MISMATCH"):
            policy.make_snapshot(application_id=2,source_application_id="570060128",target_id=2,
                software_revision="offline",retention_policy_ref="fixture")
    assert sessions==[] and rows(engines["runtime"],R)==[]


@pytest.mark.parametrize("changed",["disable","digest"])
def test_file_policy_is_rechecked_before_each_http_and_fallback(ready,tmp_path,changed):
    value,policy,snapshot,path=configured(ready,tmp_path,file_backed=True)
    _,engines,_,_,_=ready; clock=Clock()
    def change(number):
        if number==1:
            replacement=replace(value,execution_enabled=False) if changed=="disable" else replace(value,valid_until=NOW+timedelta(days=6))
            path.write_text(json.dumps(replacement.to_dict()))
    adapter=OfflineAdapter(engines["runtime"],clock,[(200,b'{"feed":{}}')],change)
    factory,_=factory_for(adapter)
    with prepare(ready,policy,clock,factory) as controller: result=controller.run_target(snapshot,uuid4())
    expected="PROJECT_EXECUTION_DISABLED" if changed=="disable" else "PROJECT_POLICY_CHANGED"
    assert result.execution_status=="failed" and result.stop_reason=="policy_stop"
    assert expected in result.reason_codes and len(adapter.calls)==1
    assert rows(engines["runtime"],R)[0]["config_snapshot"]["access_decision_ref"]==snapshot.access_decision_ref
    from feasibility.apple_ingestion.reporting import run_report
    with engines["runtime"].connect() as connection:
        report=run_report(connection,result.run_id)
    assert report["stop_reason"]=="policy_stop" and expected in report["reason_codes"]
    assert report["requests"]["known_sent_lower_bound"]==len(adapter.calls)
    assert_terminal_resolved(engines["runtime"])


def test_revocation_during_spacing_is_checked_immediately_before_real_session_get(ready,tmp_path):
    value,policy,snapshot,path=configured(ready,tmp_path,file_backed=True)
    _,engines,_,_,_=ready; clock=Clock()
    original_sleep=clock.sleep
    def revoke_after_sleep(seconds):
        original_sleep(seconds)
        path.write_text(json.dumps(replace(value,execution_enabled=False).to_dict()))
    clock.sleep=revoke_after_sleep
    adapter=OfflineAdapter(engines["runtime"],clock,[(200,feed(("one",)))])
    factory,_=factory_for(adapter)
    with prepare(ready,policy,clock,factory) as controller: result=controller.run_target(snapshot,uuid4())
    assert result.execution_status=="partial" and result.committed_pages==1
    assert result.stop_reason=="policy_stop" and "PROJECT_EXECUTION_DISABLED" in result.reason_codes
    assert len(adapter.calls)==1
    assert_terminal_resolved(engines["runtime"])


def test_expired_or_disabled_project_refuses_before_session_or_run(ready,tmp_path):
    value,_,_,_=configured(ready,tmp_path); _,engines,_,_,_=ready; clock=Clock()
    for record,code in ((replace(value,execution_enabled=False),"PROJECT_EXECUTION_DISABLED"),
                        (replace(value,valid_from=NOW-timedelta(days=1),valid_until=NOW),"PROJECT_POLICY_OUTSIDE_VALIDITY")):
        with pytest.raises(LivePolicyError,match=code):
            with prepare(ready,ProjectExecutionPolicy(record),clock,lambda:pytest.fail("unconfirmed Session")): pass
    assert rows(engines["runtime"],R)==[]


def test_project_runs_without_access_or_retention_documents(ready,tmp_path):
    value,_,_,_=configured(ready,tmp_path)
    policy=ProjectExecutionPolicy(replace(value,access_arrangement_confirmed=False,access_basis_ref=None))
    config,engines,env,previous,spool=ready
    retention=replace(config.retention,state="pending",owner=None,duration_days=None,policy_ref=None,
        backup_handling_ref=None,export_handling_ref=None,expiry_review_ref=None,mode="long_term",arrangement_confirmed=False)
    operational=replace(config,retention=retention)
    snapshot=policy.make_snapshot(application_id=previous.application_id,source_application_id=previous.source_application_id,
        target_id=previous.target_id,software_revision="offline-technical-policy")
    assert snapshot.retention_policy_ref is None
    clock=Clock(); adapter=OfflineAdapter(engines["runtime"],clock,[(200,feed(("one",))),(200,feed(("two",)))])
    factory,sessions=factory_for(adapter)
    with prepare((operational,engines,env,snapshot,spool),policy,clock,factory) as controller:
        result=controller.run_target(snapshot,uuid4())
    assert result.execution_status=="succeeded" and len(adapter.calls)==2 and len(sessions)==1
    assert rows(engines["runtime"],R)[0]["config_snapshot"]["retention_policy_ref"] is None
    assert_terminal_resolved(engines["runtime"])


def test_old_administrative_fields_are_readable_but_absent_from_trace_and_serialization(ready,tmp_path):
    value,_,_,path=configured(ready,tmp_path)
    old=value.to_dict()
    old.update(access_arrangement_confirmed=False,access_basis_ref=None)
    changed={**old,"access_arrangement_confirmed":True,"access_basis_ref":"deprecated-fixture-metadata"}
    parsed=ProjectExecutionConfig.from_dict(old)
    assert parsed.to_dict()==ProjectExecutionConfig.from_dict(changed).to_dict()==value.to_dict()
    assert "access_arrangement_confirmed" not in parsed.to_dict() and "access_basis_ref" not in parsed.to_dict()
    assert ProjectExecutionPolicy(parsed).access_decision_ref==ProjectExecutionPolicy(ProjectExecutionConfig.from_dict(changed)).access_decision_ref
    path.write_text(json.dumps(old))
    policy=ProjectExecutionPolicy(config_path=path)
    _,engines,_,previous,_=ready
    snapshot=policy.make_snapshot(application_id=previous.application_id,source_application_id=previous.source_application_id,
        target_id=previous.target_id,software_revision="offline-deprecated-fields")
    clock=Clock()
    def change_metadata(number):
        if number==1: path.write_text(json.dumps(changed))
    adapter=OfflineAdapter(engines["runtime"],clock,[(200,feed(("one",))),(200,feed(("two",)))],change_metadata)
    factory,_=factory_for(adapter)
    with prepare(ready,policy,clock,factory) as controller: result=controller.run_target(snapshot,uuid4())
    assert result.execution_status=="succeeded" and len(adapter.calls)==2
    assert rows(engines["runtime"],R)[0]["config_snapshot"]["access_decision_ref"]==policy.access_decision_ref


def test_old_context_and_used_batch_cannot_bypass_current_binding(ready,tmp_path):
    _,policy,snapshot,_=configured(ready,tmp_path); _,engines,_,_,_=ready; clock=Clock()
    adapter=OfflineAdapter(engines["runtime"],clock,[(200,feed(("one",))),(200,feed(("two",)))])
    factory,sessions=factory_for(adapter); batch=uuid4()
    with prepare(ready,policy,clock,factory) as old_controller:
        old_controller.run_target(snapshot,batch)
        with pytest.raises(LivePolicyError,match="PROJECT_BATCH_ALREADY_USED"):
            old_controller.run_target(snapshot,batch)
    with prepare(ready,policy,clock,lambda:pytest.fail("old context Session")):
        with pytest.raises(LivePolicyError,match="PROJECT_POLICY_NOT_PREPARED"):
            old_controller.run_target(snapshot,uuid4())
    assert len(rows(engines["runtime"],R))==1 and len(adapter.calls)==2


def test_pilot_reuses_one_project_and_transport_for_two_eight_app_batches(ready,tmp_path):
    """Sixteen offline fixture runs; this does not start a real pilot."""
    from sqlalchemy import select,update
    from feasibility.apple_ingestion.models import Application,CollectionTarget
    from feasibility.apple_ingestion.transport import PILOT_APPLICATION_IDS
    base,_,_,_=configured(ready,tmp_path)
    config,engines,_,_,_=ready
    project=replace(base,purpose="pilot",source_application_ids=tuple(sorted(PILOT_APPLICATION_IDS)))
    policy=ProjectExecutionPolicy(project)
    application,target=Application.__table__,CollectionTarget.__table__
    # This maintenance write is restricted to the disposable fixture database.
    with engines["owner"].begin() as connection:
        connection.execute(update(target).values(enabled=True,max_pages=project.config.max_pages))
        identities=connection.execute(select(application.c.id,application.c.source_application_id,
            target.c.id.label("target_id")).join(target,target.c.application_id==application.c.id)
            .order_by(application.c.id)).all()
    assert len(identities)==8 and {row.source_application_id for row in identities}==PILOT_APPLICATION_IDS
    snapshots=tuple(policy.make_snapshot(application_id=row.id,source_application_id=row.source_application_id,
        target_id=row.target_id,software_revision="offline-pilot-project-fixture",retention_policy_ref=config.retention.policy_ref)
        for row in identities)
    clock=Clock()
    adapter=OfflineAdapter(engines["runtime"],clock,[(200,feed(("one",))),(200,feed(("two",)))]*16)
    factory,sessions=factory_for(adapter)
    first_batch,second_batch=uuid4(),uuid4()
    with prepare(ready,policy,clock,factory) as controller:
        first=controller.run_batch(snapshots,first_batch)
        bounded_transport=controller.transport.transport
        clock.seconds+=24*3600
        second=controller.run_batch(snapshots,second_batch)
        assert controller.transport.transport is bounded_transport
    assert len(first)==len(second)==8 and len(sessions)==1
    assert all(result.execution_status=="succeeded" and result.comparison_eligible for result in (*first,*second))
    assert all(result.committed_pages==2 and result.request_count==2 for result in (*first,*second))
    assert all(result.coverage_status=="baseline" and result.reference_run_id is None for result in first)
    first_by_app={result.application_id:result.run_id for result in first}
    assert all(result.coverage_status=="overlap_insufficient" and result.reference_run_id==first_by_app[result.application_id] for result in second)
    assert {call[0] for call in adapter.calls}==PILOT_APPLICATION_IDS and len(adapter.calls)==32
    times=[call[3] for call in adapter.calls]
    assert all(later-earlier>=project.config.global_spacing_seconds for earlier,later in zip(times,times[1:]))
    assert times[16]-times[15]==24*3600
    actual=rows(engines["runtime"],R)
    assert len(actual)==16 and {row["batch_id"] for row in actual}=={first_batch,second_batch}
    assert all(row["config_snapshot"]["access_decision_ref"]==policy.access_decision_ref for row in actual)
    assert all(row["config_snapshot"]["config"]==project.config.to_dict() for row in actual)
    assert len(rows(engines["runtime"],F))==32 and not (tmp_path/"private-approval-receipts").exists()
    assert_terminal_resolved(engines["runtime"])

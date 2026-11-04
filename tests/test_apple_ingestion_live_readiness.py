"""Offline fixtures only: actual requests.Session/Response, no real approval.

An in-process BaseAdapter intercepts PreparedRequest.send; Session.request,
prepare_request, send and Response streaming are genuine requests code. The TCP
socket guard remains enabled; test PostgreSQL uses only its private Unix socket.
"""
from dataclasses import replace
from datetime import timedelta
from io import BytesIO
import json
from pathlib import Path
import re
from uuid import uuid4

import pytest
pytest.importorskip("sqlalchemy")
import requests
from requests.adapters import BaseAdapter
from sqlalchemy import select,text,update

from feasibility.apple_ingestion.contracts import ConfigSnapshot,IngestionConfig,RunMode
from feasibility.apple_ingestion.controller import Controller,ControllerError
from feasibility.apple_ingestion.deployment import RetentionConfig,DiagnosticsConfig
from feasibility.apple_ingestion.live import (
    LiveExecutionApproval,LiveExecutionPolicy,LivePolicyError,approval_template,prepare_live_controller,
)
from feasibility.apple_ingestion.models import Application,CollectionTarget,CollectionRun,FetchAttempt,ReviewVersion
from feasibility.apple_ingestion.parser import PARSER_VERSION
from feasibility.apple_ingestion.recovery import DiagnosticSpool,application_session
from test_apple_ingestion_deployment import deployed_roles,provision
from test_apple_ingestion_phase_c_integration import Clock,feed,inspect_intent,assert_terminal_resolved
from test_apple_ingestion_reference import NOW,create_history

A,T,R,F,V=(model.__table__ for model in (Application,CollectionTarget,CollectionRun,FetchAttempt,ReviewVersion))


class OfflineAdapter(BaseAdapter):
    def __init__(self,engine,clock,responses,callback=None):
        self.engine,self.clock,self.responses,self.callback=engine,clock,list(responses),callback
        self.calls=[]; self.closed=False
    def send(self,request,**kwargs):
        assert isinstance(request,requests.PreparedRequest)
        match=re.fullmatch(r"https://itunes\.apple\.com/us/rss/customerreviews/page=(\d+)/id=(\d+)/sortby=mostrecent/(json|xml)",request.url)
        assert match is not None
        page,app,format=int(match[1]),match[2],match[3]
        inspect_intent(self.engine,app,page,format)
        assert kwargs["stream"] is True and kwargs["verify"] is True and kwargs["cert"] is None
        assert kwargs["proxies"]=={} and kwargs["timeout"]==(10.0,25.0)
        assert "PRIVATE" not in repr(dict(request.headers))
        assert request.headers["User-Agent"].startswith("DataSourceFeasibility/") and self.max_retries.total==0
        self.calls.append((app,page,format,self.clock.monotonic()))
        if self.callback: self.callback(len(self.calls))
        assert self.responses,"unexpected offline HTTP send"
        value=self.responses.pop(0)
        if isinstance(value,BaseException): raise value
        status,body=value
        response=requests.Response()
        response.status_code=status; response.url=request.url; response.request=request
        response.raw=BytesIO(body); response.encoding="utf-8"
        response.headers["Content-Type"]="application/json" if format=="json" else "application/atom+xml"
        response.headers["Set-Cookie"]="PRIVATE_COOKIE=PRIVATE_RESPONSE_COOKIE"
        if status in {301,302}: response.headers["Location"]="https://example.invalid/PRIVATE_REDIRECT"
        return response
    def close(self): self.closed=True


def xml(ids,body="OFFLINE_FIXTURE_BODY"):
    from xml.sax.saxutils import escape
    payload='<feed xmlns="http://www.w3.org/2005/Atom" xmlns:im="http://itunes.apple.com/rss">'
    # XML normalizes literal CRLF before parsing. Character references express
    # an actual decoded CR so the full-text CRLF preservation assertion tests
    # the stored parsed string rather than XML's source-byte spelling.
    encoded_body=escape(body).replace("\r","&#13;")
    payload+=''.join(f'<entry><id>{escape(str(i))}</id><title>OFFLINE_FIXTURE_TITLE</title><content>{encoded_body}</content><im:rating>4</im:rating></entry>' for i in ids)
    return (payload+'</feed>').encode()


@pytest.fixture
def ready(deployed_roles,tmp_path):
    config,engines,env=deployed_roles
    provision(config,engines)
    config=replace(config,retention=RetentionConfig("documented","offline-fixture-retention-owner",7,
        "OFFLINE_FIXTURE_RETENTION_NOT_REAL_APPROVAL","fixture-backup","fixture-export","fixture-expiry"),
        diagnostics=DiagnosticsConfig(config.diagnostics.spool_path_env,"offline-fixture-operator"))
    cfg=IngestionConfig(max_pages=2)
    with engines["owner"].begin() as c:
        row=c.execute(select(A.c.id,T.c.id.label("target")).join(T,T.c.application_id==A.c.id).where(A.c.source_application_id=="572688855")).one()
        c.execute(update(T).where(T.c.id==row.target).values(enabled=True,max_pages=2))
    snapshot=ConfigSnapshot(row.id,"572688855",row.target,"offline-live-fixture",PARSER_VERSION,run_mode=RunMode.LIVE,
        access_decision_ref="OFFLINE_FIXTURE_ACCESS_NOT_REAL_APPROVAL",retention_policy_ref=config.retention.policy_ref,config=cfg)
    spool=DiagnosticSpool(env[config.diagnostics.spool_path_env])
    return config,engines,env,snapshot,spool


def record(snapshot,clock,**changes):
    now=clock.now()
    value=LiveExecutionApproval(approval_id=uuid4(),operator="offline-fixture-operator",approved_by="offline-fixture-approver",
        approved_at=now-timedelta(minutes=2),valid_from=now-timedelta(minutes=1),valid_until=now+timedelta(hours=1),
        source_application_ids=(snapshot.source_application_id,),max_http_requests=snapshot.config.max_http_requests,
        access_basis_ref=snapshot.access_decision_ref,retention_policy_ref=snapshot.retention_policy_ref,
        status="approved",readiness_confirmed=True,execution_authorized=True)
    return replace(value,**changes)


def policy_for(tmp_path,approval):
    directory=tmp_path/"private-approval-receipts"; directory.mkdir(mode=0o700,exist_ok=True)
    return LiveExecutionPolicy(approval,directory)


def factory_for(adapter):
    sessions=[]
    def factory():
        session=requests.Session()
        session.auth=("PRIVATE_USER","PRIVATE_PASSWORD"); session.headers["X-Api-Key"]="PRIVATE_TOKEN"
        session.params={"PRIVATE_QUERY":"PRIVATE_VALUE"}; session.cookies.set("PRIVATE_COOKIE","PRIVATE_VALUE")
        session.proxies={"https":"http://PRIVATE_PROXY.invalid"}; session.verify=False
        session.hooks={"response":[lambda *args,**kwargs:pytest.fail("ambient hook must be cleared")]}
        session.mount("https://",adapter); sessions.append(session)
        return session
    return factory,sessions


def prepare(ready,policy,clock,batch,session_factory):
    config,engines,env,snapshot,spool=ready
    return prepare_live_controller(engines["runtime"],snapshot,batch,spool,policy=policy,deployment_config=config,
        audit_engine=engines["owner"],environ=env,session_factory=session_factory,
        now=clock.now,clock=clock.monotonic,sleep=clock.sleep)


def execute(ready,tmp_path,responses,*,clock=None,approval=None,callback=None):
    config,engines,env,snapshot,spool=ready
    clock=clock or Clock(); policy=policy_for(tmp_path,approval or record(snapshot,clock))
    adapter=OfflineAdapter(engines["runtime"],clock,responses,callback)
    factory,sessions=factory_for(adapter); batch=uuid4()
    with prepare(ready,policy,clock,batch,factory) as controller:
        result=controller.run_target(snapshot,batch)
    return result,adapter,policy,sessions


def rows(engine,table):
    with engine.connect() as c: return list(c.execute(select(table)).mappings())


def test_pending_template_and_default_gate_refuse_before_session_or_database(tmp_path):
    snapshot=ConfigSnapshot(1,"572688855",1,"offline-test",PARSER_VERSION,run_mode=RunMode.LIVE,
        access_decision_ref="fixture",retention_policy_ref="fixture")
    template=approval_template()
    assert template["status"]=="pending" and not template["execution_authorized"] and not template["readiness_confirmed"]
    pending=policy_for(tmp_path,LiveExecutionApproval.from_dict(template))
    for policy in (None,pending):
        with pytest.raises(ControllerError,match="LIVE_MODE_DISABLED"):
            with prepare_live_controller(object(),snapshot,uuid4(),object(),policy=policy,
                    session_factory=lambda:pytest.fail("Session before approval"),now=lambda:NOW): pass


@pytest.mark.parametrize("change,code",[
    ({"status":"revoked"},"LIVE_MODE_DISABLED"),({"readiness_confirmed":False},"LIVE_MODE_DISABLED"),
    ({"valid_until":NOW},"LIVE_APPROVAL_OUTSIDE_VALIDITY"),
    ({"source_application_ids":("570060128",)},"LIVE_APPROVAL_SCOPE_MISMATCH"),
    ({"max_http_requests":1},"LIVE_APPROVAL_SCOPE_MISMATCH"),
])
def test_invalid_authorization_never_constructs_http_session_or_writes_run(ready,tmp_path,change,code):
    config,engines,env,snapshot,_=ready; clock=Clock()
    policy=policy_for(tmp_path,record(snapshot,clock,**change))
    with pytest.raises(ControllerError,match=code):
        with prepare(ready,policy,clock,uuid4(),lambda:pytest.fail("Session before approval")): pass
    assert rows(engines["runtime"],R)==[] and list(policy.receipt_directory.iterdir())==[]


def test_disabled_target_blocks_even_with_pending_retention_metadata(ready,tmp_path):
    config,engines,env,snapshot,spool=ready; clock=Clock()
    pending=replace(config,retention=RetentionConfig("pending",None,None,None,None,None,None))
    policy=policy_for(tmp_path,record(snapshot,clock))
    with engines["owner"].begin() as c: c.execute(update(T).where(T.c.id==snapshot.target_id).values(enabled=False))
    with pytest.raises(LivePolicyError,match="LIVE_TARGET_DISABLED"):
        with prepare((pending,engines,env,snapshot,spool),policy,clock,uuid4(),lambda:pytest.fail("disabled target Session")): pass
    assert not rows(engines["owner"],T)[0]["enabled"] and rows(engines["runtime"],R)==[]
    assert list(policy.receipt_directory.iterdir())==[]


def test_actual_requests_adapter_fallback_runtime_login_and_full_text(ready,tmp_path,monkeypatch,caplog):
    config,engines,env,snapshot,_=ready
    monkeypatch.setenv("HTTPS_PROXY","http://PRIVATE_AMBIENT_PROXY.invalid")
    monkeypatch.setenv("REQUESTS_CA_BUNDLE","/PRIVATE_CA_PATH")
    body="OFFLINE_FIXTURE_FULL_TEXT🙂汉字\r\n"*2000
    result,adapter,policy,sessions=execute(ready,tmp_path,[(200,b'{"feed":{}}'),(200,xml(("000opaque-id",),body)),(200,feed(("second",)))])
    assert result.execution_status=="succeeded" and result.request_count==3 and result.committed_pages==2
    assert [(page,format) for _,page,format,_ in adapter.calls]==[(1,"json"),(1,"xml"),(2,"json")]
    assert [call[3] for call in adapter.calls]==[0,2,4]
    assert rows(engines["runtime"],R)[0]["config_snapshot"]["run_mode"]=="live"
    assert any(row["body"]==body and row["title"]=="OFFLINE_FIXTURE_TITLE" for row in rows(engines["runtime"],V))
    with engines["runtime"].connect() as c:
        assert c.execute(text("SELECT current_user,session_user")).one()==(config.roles.runtime_role,)*2
    assert adapter.closed and len(sessions)==1 and not sessions[0].cookies and "PRIVATE" not in caplog.text
    assert_terminal_resolved(engines["runtime"])


@pytest.mark.parametrize("status",[403,429])
def test_partial_denial_preserves_page_without_retry_or_fallback(ready,tmp_path,status):
    _,engines,_,_,_=ready
    result,adapter,*_=execute(ready,tmp_path,[(200,feed(("first",))),(status,b"PRIVATE_DENIAL_BODY")])
    assert result.execution_status=="partial" and result.source_stop and result.committed_pages==1
    assert len(adapter.calls)==2 and len(rows(engines["runtime"],V))==1
    assert "PRIVATE" not in json.dumps([dict(row) for row in rows(engines["runtime"],F)],default=str)
    assert_terminal_resolved(engines["runtime"])


@pytest.mark.parametrize("response,code",[
    (requests.exceptions.ReadTimeout("PRIVATE_TIMEOUT"),"TRANSPORT_TIMEOUT"),
    ((302,b"PRIVATE_REDIRECT_BODY"),"HTTP_NON_200"),((200,b"PRIVATE_BAD_FEED"),"FEED_SCHEMA"),
])
def test_actual_response_errors_have_safe_terminal_metadata(ready,tmp_path,response,code):
    _,engines,_,_,_=ready
    result,adapter,*_=execute(ready,tmp_path,[response])
    assert result.execution_status=="failed" and len(adapter.calls)==1
    assert code in rows(engines["runtime"],F)[0]["error_codes"]
    assert "PRIVATE" not in json.dumps([dict(row) for row in rows(engines["runtime"],F)],default=str)
    assert_terminal_resolved(engines["runtime"])


def test_nested_xhtml_rejected_through_real_response_stream(ready,tmp_path):
    _,engines,_,_,_=ready
    nested=b'<feed xmlns="http://www.w3.org/2005/Atom" xmlns:im="http://itunes.apple.com/rss"><entry><id>one</id><content type="xhtml"><div xmlns="http://www.w3.org/1999/xhtml">PRIVATE_NESTED</div></content><im:rating>4</im:rating></entry></feed>'
    result,adapter,*_=execute(ready,tmp_path,[(200,b'{"feed":{}}'),(200,nested)])
    assert result.execution_status=="failed" and result.committed_pages==0 and len(adapter.calls)==2
    assert rows(engines["runtime"],F)[1]["error_codes"]==["ENTRY_SCHEMA"] and rows(engines["runtime"],V)==[]
    assert rows(engines["runtime"],F)[1]["anomalies"] == [{
        "code": "ENTRY_SCHEMA", "category": "unsupported_xhtml", "field": "content", "entry_index": 1,
    }]
    assert "PRIVATE_NESTED" not in json.dumps([dict(row) for row in rows(engines["runtime"],F)],default=str)


def test_single_run_reuse_and_live_batch_denied_before_consumption_or_http(ready,tmp_path):
    _,engines,_,snapshot,_=ready; clock=Clock(); approval=record(snapshot,clock)
    policy=policy_for(tmp_path,approval)
    adapter=OfflineAdapter(engines["runtime"],clock,[(200,feed(("one",))),(200,feed(("two",)))])
    factory,sessions=factory_for(adapter); batch=uuid4()
    with prepare(ready,policy,clock,batch,factory) as controller:
        with pytest.raises(ControllerError,match="LIVE_SINGLE_RUN_ONLY"): controller.run_batch((snapshot,)*8,batch)
        assert list(policy.receipt_directory.iterdir())==[] and sessions==[] and rows(engines["runtime"],R)==[]
        controller.run_target(snapshot,batch)
        with pytest.raises(LivePolicyError,match="LIVE_APPROVAL_CONSUMED"): controller.run_target(snapshot,batch)
    reused=LiveExecutionPolicy(approval,policy.receipt_directory); second_batch=uuid4()
    with prepare(ready,reused,clock,second_batch,lambda:pytest.fail("reused approval Session")) as controller:
        with pytest.raises(LivePolicyError,match="LIVE_APPROVAL_CONSUMED"): controller.run_target(snapshot,second_batch)
    assert len(rows(engines["runtime"],R))==1 and len(adapter.calls)==2
    receipt=next(policy.receipt_directory.iterdir())
    assert receipt.stat().st_mode & 0o777==0o600


def test_approval_window_caps_each_request_and_fallback_deadline(ready,tmp_path):
    _,engines,_,snapshot,_=ready; clock=Clock()
    approval=record(snapshot,clock,valid_until=NOW+timedelta(seconds=1))
    result,adapter,*_=execute(ready,tmp_path,[(200,b'{"feed":{}}')],clock=clock,approval=approval)
    assert result.execution_status=="failed" and result.stop_reason=="target_deadline"
    assert result.committed_pages==0 and len(adapter.calls)==1
    assert_terminal_resolved(engines["runtime"])


def test_live_mode_reference_isolation_and_same_and_stop_predicate(ready,tmp_path):
    _,engines,_,snapshot,_=ready
    create_history(engines["owner"],replace(snapshot,run_mode=RunMode.SYNTHETIC),at=NOW-timedelta(days=1),pages=(("synthetic-only",),))
    first,*_=execute(ready,tmp_path,[(200,feed(("first",))),(200,feed(("second",)))])
    assert first.reference_run_id is None and first.coverage_status=="baseline"
    ids=tuple(str(n) for n in range(20))
    create_history(engines["owner"],snapshot,at=NOW+timedelta(days=1),pages=(ids,))
    clock=Clock(); clock.seconds=2*24*3600
    result,adapter,*_=execute(ready,tmp_path,[(200,feed(ids[:10])),(200,feed(ids[10:]))],clock=clock)
    assert result.stop_reason=="overlap_met" and result.committed_pages==2 and len(adapter.calls)==2


def test_lock_busy_consumes_reservation_but_creates_no_http_session_or_run(ready,tmp_path):
    _,engines,_,snapshot,_=ready
    with application_session(engines["runtime"],snapshot.application_id):
        result,adapter,policy,sessions=execute(ready,tmp_path,[])
    assert result.skipped and result.stop_reason=="application_locked" and adapter.calls==[] and sessions==[]
    assert rows(engines["runtime"],R)==[] and len(list(policy.receipt_directory.iterdir()))==1


def test_session_loss_spools_and_new_record_restarts_page_one(ready,tmp_path):
    _,engines,_,_,spool=ready
    # Deterministic loss of the pinned handle after the actual first commit is
    # tested without giving an administrator connection to the collector.
    import feasibility.apple_ingestion.controller as implementation
    original=implementation.persist_page
    def commit_then_lose(connection,*args,**kwargs):
        result=original(connection,*args,**kwargs); connection.invalidate(); return result
    with pytest.MonkeyPatch.context() as scoped:
        scoped.setattr(implementation,"persist_page",commit_then_lose)
        first,adapter,*_=execute(ready,tmp_path,[(200,feed(("one",)))])
    assert first.recovery_required and first.committed_pages==1 and len(adapter.calls)==1
    assert "APPLICATION_SESSION_LOST" in spool.path.read_text()
    clock=Clock(); clock.seconds=24*3600
    second,next_adapter,*_=execute(ready,tmp_path,[(200,feed(("one",))),(200,feed(("two",)))],clock=clock)
    assert second.execution_status=="succeeded" and next_adapter.calls[0][1]==1
    assert next(row for row in rows(engines["runtime"],R) if row["id"]==first.run_id)["execution_status"]=="interrupted"
    assert_terminal_resolved(engines["runtime"])


def test_receipt_rejects_other_git_worktree_and_symlink_paths(tmp_path):
    snapshot=ConfigSnapshot(1,"572688855",1,"offline-test",PARSER_VERSION,run_mode=RunMode.LIVE,
        access_decision_ref="fixture",retention_policy_ref="fixture")
    approval=record(snapshot,Clock())
    foreign=tmp_path/"foreign-worktree"; foreign.mkdir(mode=0o700)
    (foreign/".git").mkdir(); (foreign/".git/HEAD").write_text("ref: refs/heads/offline-fixture\n")
    private=foreign/"private"; private.mkdir(mode=0o700)
    with pytest.raises(LivePolicyError,match="LIVE_PRIVATE_RECEIPT_DIRECTORY_REQUIRED"):
        LiveExecutionPolicy(approval,private).claim(snapshot,uuid4(),NOW)
    actual=tmp_path/"actual-private"; actual.mkdir(mode=0o700)
    link=tmp_path/"linked-private"; link.symlink_to(actual,target_is_directory=True)
    with pytest.raises(LivePolicyError,match="LIVE_PRIVATE_RECEIPT_DIRECTORY_REQUIRED"):
        LiveExecutionPolicy(approval,link).claim(snapshot,uuid4(),NOW)


@pytest.mark.parametrize("mutation",["snapshot","batch","runtime"])
def test_prepared_scope_cannot_be_changed_before_first_claim(ready,tmp_path,mutation):
    _,engines,_,snapshot,_=ready; clock=Clock()
    policy=policy_for(tmp_path,record(snapshot,clock))
    adapter=OfflineAdapter(engines["runtime"],clock,[]); factory,sessions=factory_for(adapter); batch=uuid4()
    with prepare(ready,policy,clock,batch,factory) as controller:
        selected=replace(snapshot,software_revision="changed-fixture-revision") if mutation=="snapshot" else snapshot
        selected_batch=uuid4() if mutation=="batch" else batch
        if mutation=="runtime": controller.engine=engines["owner"]
        with pytest.raises(LivePolicyError,match="LIVE_APPROVAL_SCOPE_MISMATCH"):
            controller.run_target(selected,selected_batch)
    assert list(policy.receipt_directory.iterdir())==[] and sessions==[] and rows(engines["runtime"],R)==[]


def test_deployment_is_freshly_rechecked_and_spool_path_is_read_only(ready,tmp_path):
    _,engines,env,snapshot,spool=ready; clock=Clock()
    assert spool.path==Path(next(value for key,value in env.items() if key=="TEST_DEPLOYMENT_SPOOL"))
    with pytest.raises(AttributeError): spool.path=tmp_path/"changed.jsonl"
    policy=policy_for(tmp_path,record(snapshot,clock)); batch=uuid4()
    adapter=OfflineAdapter(engines["runtime"],clock,[]); factory,sessions=factory_for(adapter)
    with prepare(ready,policy,clock,batch,factory) as controller:
        with engines["owner"].begin() as c:
            c.execute(update(T).where(T.c.id==snapshot.target_id).values(enabled=False))
        with pytest.raises(LivePolicyError,match="LIVE_TARGET_DISABLED"):
            controller.run_target(snapshot,batch)
    assert sessions==[] and rows(engines["runtime"],R)==[] and list(policy.receipt_directory.iterdir())==[]


def test_legacy_technical_run_does_not_require_document_references_or_arrangement_confirmation(ready,tmp_path):
    config,engines,env,old_snapshot,spool=ready
    retention=replace(config.retention,state="pending",owner=None,duration_days=None,policy_ref=None,
        backup_handling_ref=None,export_handling_ref=None,expiry_review_ref=None,mode="long_term",arrangement_confirmed=False)
    operational=replace(config,retention=retention)
    snapshot=replace(old_snapshot,access_decision_ref=None,retention_policy_ref=None)
    result,adapter,_,sessions=execute((operational,engines,env,snapshot,spool),tmp_path,
        [(200,feed(("one",))),(200,feed(("two",)))],approval=replace(record(snapshot,Clock()),approved_by=None))
    assert result.execution_status=="succeeded" and len(adapter.calls)==2 and len(sessions)==1
    assert rows(engines["runtime"],R)[0]["config_snapshot"]["retention_policy_ref"] is None
    assert_terminal_resolved(engines["runtime"])

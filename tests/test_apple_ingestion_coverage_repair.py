"""Regression of the live W0 defect; advancing UTC, real disposable PostgreSQL."""
from datetime import datetime, timedelta, timezone
from contextlib import nullcontext
import json
from pathlib import Path
import subprocess
import sys
import time
from uuid import UUID

import pytest
from sqlalchemy import text

from feasibility.apple_ingestion import coverage_runner as module
from feasibility.apple_ingestion import coverage_experiment as operator
from feasibility.apple_ingestion.recovery import application_session, replay_spool, recover_interrupted
from feasibility.apple_ingestion.reconcile import ReconciliationError
from test_apple_ingestion_phase_c_integration import Clock, Response, feed
from test_apple_ingestion_pagination_probe import atom
from test_apple_ingestion_coverage_experiment import setup_runner, run, assert_integrity, store_at, enable, START


class AdvancingClock(Clock):
    def now(self):
        self.seconds += .001
        return super().now()


class RealUTCClock(Clock):
    """Real UTC progresses between calls; synthetic transport spacing stays fast."""
    def now(self):
        time.sleep(.001)
        return datetime.now(timezone.utc)


@pytest.mark.parametrize('clock_type',[AdvancingClock,RealUTCClock])
@pytest.mark.parametrize('fallback',[False,True])
def test_advancing_response_timestamp_is_reused_for_commit(apple_database,tmp_path,clock_type,fallback):
    def respond(app,page,fmt):
        return Response(b'{"feed":{}}' if fallback and fmt=='json' else
                        atom([page]) if fallback else feed([page]))
    runner,snapshot,http,clock,outputs,_=setup_runner(apple_database,tmp_path,respond,clock=clock_type())
    result=run(runner,snapshot)
    assert result['overall_status']=='succeeded'
    assert result['requests']==len(http.calls)==(20 if fallback else 10)
    with apple_database.connect() as c:
        rows=c.execute(text('''SELECT a.finished_at,o.first_observed_at
            FROM fetch_attempt a JOIN review_observation o ON o.run_id=a.run_id
              AND o.first_observed_page=a.page_number WHERE a.persistence_status='committed'
            ORDER BY a.page_number''')).all()
        assert len(rows)==10 and all(finished==observed for finished,observed in rows)
        assert len({row[0] for row in rows})==10
        assert c.scalar(text('SELECT count(*) FROM review_version'))==10
    assert_integrity(apple_database)


def test_precondition_failure_remains_strict_and_terminal(apple_database,tmp_path,monkeypatch):
    original=module.persist_page
    def mismatch(connection,run_id,attempt_id,records,at):
        return original(connection,run_id,attempt_id,records,at+timedelta(microseconds=1))
    monkeypatch.setattr(module,'persist_page',mismatch)
    runner,snapshot,http,_,outputs,_=setup_runner(apple_database,tmp_path,
        lambda app,p,f:Response(feed([p])),clock=AdvancingClock())
    result=run(runner,snapshot)
    assert result['overall_status']=='failed' and len(http.calls)==1
    assert result['failure_detail']['code']=='ATTEMPT_NOT_READY_FOR_PAGE'
    assert result['result']['finalized'] and not result['result']['comparison_eligible']
    with apple_database.connect() as c:
        r=c.execute(text('SELECT execution_status,coverage_status,finished_at FROM collection_run')).one()
        assert r[0]=='failed' and r[1]=='indeterminate' and r[2] is not None
        a=c.execute(text('SELECT http_status,parsing_status,entry_count,persistence_status,anomalies FROM fetch_attempt')).one()
        assert a[:4]==(200,'succeeded',1,'rolled_back')
        assert any(x.get('precondition')=='ATTEMPT_NOT_READY_FOR_PAGE' for x in a[4])
        assert c.scalar(text('SELECT count(*) FROM review_observation'))==0
    assert 'SYNTHETIC_FULL_BODY' not in json.dumps(outputs)
    assert_integrity(apple_database)


def test_orphan_recovery_preserves_response_and_never_replays(apple_database,tmp_path,monkeypatch):
    def failed_page(*args,**kwargs):raise ReconciliationError('PERSISTENCE_ERROR')
    monkeypatch.setattr(module,'persist_page',failed_page)
    runner,snapshot,http,clock,outputs,spool=setup_runner(apple_database,tmp_path,
        lambda app,p,f:Response(feed(range(50))),clock=AdvancingClock())
    result=run(runner,snapshot)
    assert result['overall_status']=='recovery_required' and len(http.calls)==1
    with apple_database.connect() as c:
        before=c.execute(text('SELECT started_at,finished_at,http_status,parsing_status,entry_count FROM fetch_attempt')).one()
    with application_session(apple_database,snapshot.application_id) as locked:
        assert replay_spool(locked.connection,snapshot.application_id,spool,clock.now())==1
        assert recover_interrupted(locked.connection,snapshot.application_id,clock.now())==(UUID(result['run_id']),)
        assert replay_spool(locked.connection,snapshot.application_id,spool,clock.now())==0
        assert recover_interrupted(locked.connection,snapshot.application_id,clock.now())==()
    with apple_database.connect() as c:
        after=c.execute(text('SELECT started_at,finished_at,http_status,parsing_status,entry_count FROM fetch_attempt')).one()
        assert before==after and after[2:]==(200,'succeeded',50)
        assert c.scalar(text("SELECT persistence_status FROM fetch_attempt"))=='rolled_back'
        assert c.scalar(text("SELECT execution_status FROM collection_run"))=='interrupted'
        for table in ('review','review_version','review_observation'):
            assert c.scalar(text('SELECT count(*) FROM '+table))==0
        assert c.scalar(text('SELECT count(*) FROM fetch_attempt'))==1
    assert len(http.calls)==1
    assert_integrity(apple_database)


@pytest.mark.parametrize('mode,result,expected',[
    ('observe',{'status':'succeeded'},0),('observe',{'status':'failed'},1),
    ('observe',{'status':'partial'},1),('observe',{'status':'interrupted'},1),
    ('observe',{'status':'recovery_required'},1),('observe',{'status':'verification_failed'},1),
    ('observe',{'no_due_slot':True},2),
    ('verify',{'operational_ready':True,'clock':{'verified':True},'integrity':{'ok':True}},0),
    ('verify',{'operational_ready':True,'clock':{'verified':False},'integrity':{'ok':True}},1),
    ('verify',{'operational_ready':True,'clock':{'verified':True},'integrity':{'ok':True,'running_pending_attempt_count':1}},1),
    ('maintenance',{'maintenance':True,'retired':False},0),
])
def test_process_exit_status_is_real_os_status(tmp_path,mode,result,expected):
    store=store_at(tmp_path)
    program='''import json,sys
from feasibility.apple_ingestion import coverage_experiment as m
payload=json.loads(sys.argv[1]);state=sys.argv[2];mode=sys.argv[3]
m.operate=lambda store,mode:payload
sys.argv=['coverage_experiment','--state',state,mode]
m.main()
'''
    p=subprocess.run([sys.executable,'-c',program,json.dumps(result),str(store.directory),mode],
                     capture_output=True,text=True,timeout=20)
    assert p.returncode==expected,p.stderr
    assert json.loads(p.stdout)==result


def test_operator_cleanup_and_hold_when_session_construction_fails(tmp_path,monkeypatch):
    store=store_at(tmp_path);enable(store)
    (store.directory/'pilot-baseline.json').write_text('{}')
    original_enabled=store.enabled;original_reserve=store.reserve_slot
    monkeypatch.setattr(store,'enabled',lambda **kw:original_enabled(at=START))
    monkeypatch.setattr(store,'reserve_slot',lambda **kw:original_reserve(at=START))
    monkeypatch.setattr(operator,'load_config',lambda _:object())
    monkeypatch.setattr(operator,'environments',lambda *a:({},{}))
    monkeypatch.setattr(operator,'existing_operator_lock',lambda:nullcontext())
    disposed=[]
    class Engine:
        def dispose(self):disposed.append(True)
    monkeypatch.setattr(operator,'deployment_engine',lambda *a,**kw:Engine())
    monkeypatch.setattr(operator,'verify',lambda *a,**kw:{'clock':{'verified':True}})
    monkeypatch.setattr(operator,'pilot_digest',lambda *a:{})
    monkeypatch.setattr(operator,'make_snapshot',lambda *a:object())
    states=[]
    monkeypatch.setattr(operator,'target_state',lambda engine,enabled:states.append(enabled))
    def failed_session():raise RuntimeError('PRIVATE_SESSION_FAILURE')
    with pytest.raises(RuntimeError):operator.operate(store,'observe',session_factory=failed_session)
    assert states==[True,False] and len(disposed)==4
    assert store.load()['hold'] and store.load()['slots'][0]['requests']==0


def test_cli_exception_is_nonzero_without_unsafe_message(tmp_path):
    store=store_at(tmp_path)
    program='''import sys
from feasibility.apple_ingestion import coverage_experiment as m
def fail(*a):raise RuntimeError('PRIVATE_REVIEW_OR_PASSWORD')
m.operate=fail
sys.argv=['coverage_experiment','--state',sys.argv[1],'observe']
m.main()
'''
    p=subprocess.run([sys.executable,'-c',program,str(store.directory)],capture_output=True,text=True,timeout=20)
    assert p.returncode==1
    assert 'PRIVATE_REVIEW_OR_PASSWORD' not in p.stdout+p.stderr
    assert json.loads(p.stdout)['safe_error']=='RuntimeError'

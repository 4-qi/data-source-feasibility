"""Phase C cross-layer checks using real PostgreSQL and a synthetic HTTP session."""
from datetime import timedelta
from dataclasses import replace
import json
from pathlib import Path
import re
from uuid import uuid4

import pytest
import requests
from sqlalchemy import text
from sqlalchemy import event

from apple_ingestion_db_helpers import NOW
from feasibility.apple_ingestion.contracts import ConfigSnapshot, IngestionConfig
from feasibility.apple_ingestion.parser import PARSER_VERSION


class Clock:
    def __init__(self):
        self.seconds=0.0
        self.sleeps=[]

    def monotonic(self):
        return self.seconds

    def sleep(self,seconds):
        self.sleeps.append(seconds)
        self.seconds+=seconds

    def now(self):
        return NOW+timedelta(seconds=self.seconds)


class Response:
    def __init__(self,body,status=200):
        self.status_code=status
        self.headers={}
        self.body=body

    def __enter__(self):
        return self

    def __exit__(self,*args):
        self.close()

    def close(self):
        pass

    def iter_content(self,chunk_size):
        for start in range(0,len(self.body),chunk_size):
            yield self.body[start:start+chunk_size]


class SyntheticSession(requests.Session):
    def __init__(self,clock,respond,before_request=None):
        super().__init__()
        self.clock=clock
        self.respond=respond
        self.before_request=before_request
        self.calls=[]

    def request(self,method,url,**kwargs):
        match=re.search(r'/page=([0-9]+)/id=([0-9]+)/sortby=mostrecent/(json|xml)',url)
        assert match is not None,'unexpected transport URL'
        page,app,format=int(match[1]),match[2],match[3]
        if self.before_request is not None:
            self.before_request(app,page,format)
        self.calls.append((app,page,format,self.clock.monotonic()))
        return self.respond(app,page,format)


def feed(ids,*,body='SYNTHETIC_FULL_BODY🙂',rating=4):
    entries=[]
    for source_id in ids:
        entries.append({key:{'label':value} for key,value in {
            'id':str(source_id),'title':'SYNTHETIC_TITLE','content':body,
            'im:rating':str(rating),'im:version':'1.0',
            'updated':'2026-11-03T12:00:00Z',
        }.items()})
    return json.dumps({'feed':{'entry':entries}},ensure_ascii=False).encode()


def query(engine,sql,**params):
    with engine.connect() as c:
        return c.execute(text(sql),params).mappings().all()


def assert_terminal_resolved(engine):
    assert not query(engine,"""SELECT r.id FROM collection_run r
        WHERE r.execution_status <> 'running' AND (r.coverage_status='pending' OR
        EXISTS (SELECT 1 FROM fetch_attempt a WHERE a.run_id=r.id AND
          (a.parsing_status='pending' OR a.persistence_status IN ('pending','unknown'))))""")


def assert_safe_diagnostics(engine,*forbidden):
    records=query(engine,'SELECT anomalies FROM collection_run')
    records+=query(engine,'SELECT anomalies,error_codes FROM fetch_attempt')
    encoded=json.dumps([dict(row) for row in records],default=str,ensure_ascii=False)
    for value in forbidden:
        assert value not in encoded


def inspect_intent(engine,source_app,page,format):
    rows=query(engine,"""SELECT a.*,p.source_application_id FROM fetch_attempt a
        JOIN collection_run r ON r.id=a.run_id JOIN application p ON p.id=r.application_id
        WHERE r.execution_status='running' AND a.page_number=:page
          AND a.format=:format AND p.source_application_id=:source_app
        ORDER BY a.request_number DESC""",page=page,format=format,source_app=source_app)
    assert rows
    latest=rows[0]
    assert latest['finished_at'] is None and latest['http_status'] is None
    assert latest['parsing_status']=='pending' and latest['persistence_status']=='pending'
    locks=query(engine,"""SELECT a.state FROM pg_stat_activity a
        WHERE a.pid IN (SELECT pid FROM pg_locks WHERE locktype='advisory' AND granted)
          AND a.datname=current_database()""")
    assert locks and all(row['state']=='idle' for row in locks)


def setup(engine,tmp_path,respond,*,config=None,before_request=None):
    from feasibility.apple_ingestion.controller import Controller
    from feasibility.apple_ingestion.recovery import DiagnosticSpool
    from feasibility.apple_ingestion.seed import seed_defaults
    from feasibility.apple_ingestion.transport import BoundedTransport
    config=config or IngestionConfig(max_pages=2)
    with engine.begin() as c:
        seeded=seed_defaults(c,Path(__file__).resolve().parents[1]/'results/mainstream/app_sample_manifest.json')
        snapshots=[]
        for app,tid in zip(seeded.application_ids,seeded.target_ids):
            c.execute(text('''UPDATE collection_target SET max_pages=:pages,
                max_http_requests=:requests WHERE id=:tid'''),
                dict(pages=config.max_pages,requests=config.max_http_requests,tid=tid))
            source=c.execute(text('SELECT source_application_id FROM application WHERE id=:app'),dict(app=app)).scalar_one()
            snapshots.append(ConfigSnapshot(application_id=app,source_application_id=source,
                target_id=tid,software_revision='synthetic-phase-c-integration',
                parser_version=PARSER_VERSION,config=config))
    clock=Clock()
    session=SyntheticSession(clock,respond,before_request)
    transport=BoundedTransport(session,clock=clock.monotonic,sleep=clock.sleep)
    spool=DiagnosticSpool(tmp_path/'diagnostics.jsonl')
    controller=Controller(engine,transport,spool,now=clock.now,monotonic=clock.monotonic)
    return controller,snapshots,clock,session,spool


def test_insufficient_chain_age_boundary_and_committed_intent(apple_database,tmp_path):
    engine=apple_database
    ctl,snapshots,clock,http,_=setup(engine,tmp_path,
        lambda app,page,format:Response(feed(range((page-1)*6,page*6))),
        before_request=lambda app,page,format:inspect_intent(engine,app,page,format))
    snap=snapshots[0]
    previous=None
    for index,gap in enumerate([0,24*3600,24*3600,72*3600,72*3600+1]):
        clock.seconds+=gap
        result=ctl.run_target(snap,uuid4())
        assert result.execution_status=='succeeded'
        assert result.coverage_status==('baseline' if index==0 else 'overlap_insufficient')
        assert result.reference_run_id==previous
        assert result.comparison_eligible and result.committed_pages==2
        assert result.request_count==2
        assert 'SYNTHETIC_FULL_BODY' not in repr(result)
        assert ('REFERENCE_AGE_WARNING' in result.reason_codes)==(index==4)
        if index:
            assert {'OBSERVABLE_WINDOW_BELOW_COUNT_THRESHOLD','REFERENCE_WINDOW_BELOW_COUNT_THRESHOLD'} <= set(result.reason_codes)
        previous=result.run_id
    assert len(http.calls)==10
    assert all(b[3]-a[3]>=2 for a,b in zip(http.calls,http.calls[1:]))
    assert len(query(engine,'SELECT * FROM review_version'))==12
    assert len(query(engine,'SELECT * FROM review_observation'))==60
    assert_terminal_resolved(engine)
    assert_safe_diagnostics(engine,'SYNTHETIC_FULL_BODY🙂','SYNTHETIC_TITLE')


@pytest.mark.parametrize('caution',['duplicate_only','empty_xml'])
def test_successful_coverage_caution_remains_reference(apple_database,tmp_path,caution):
    engine=apple_database
    def respond(app,page,format):
        if caution=='empty_xml' and page==1:
            return Response(b'<feed xmlns="http://www.w3.org/2005/Atom"/>' if format=='xml' else feed([]))
        return Response(feed(range(12)))
    ctl,snaps,clock,http,_=setup(engine,tmp_path,respond)
    first=ctl.run_target(snaps[0],uuid4())
    assert first.execution_status=='succeeded' and first.coverage_status=='indeterminate'
    assert first.comparison_eligible and first.committed_pages==2
    assert 'COVERAGE_CAUTION' in first.reason_codes
    clock.seconds+=24*3600
    http.respond=lambda app,page,format:Response(feed(range((page-1)*6,page*6)))
    second=ctl.run_target(snaps[0],uuid4())
    assert second.reference_run_id==first.run_id and second.comparison_eligible
    assert second.coverage_status=='overlap_insufficient'
    assert_terminal_resolved(engine)


def test_denial_stops_eight_target_batch_without_fallback(apple_database,tmp_path):
    ctl,snaps,_,http,_=setup(apple_database,tmp_path,lambda app,page,format:Response(b'',429))
    results=ctl.run_batch(snaps,uuid4())
    assert len(results)==8 and len(http.calls)==1
    assert results[0].execution_status=='failed' and results[0].source_stop
    assert all(row.skipped and row.run_id is None for row in results[1:])
    assert len(query(apple_database,'SELECT * FROM collection_run'))==1
    assert_terminal_resolved(apple_database)


def test_fallback_budget_does_not_count_unresolved_page_as_success(apple_database,tmp_path):
    ctl,snaps,_,http,_=setup(apple_database,tmp_path,
        lambda app,page,format:Response(feed([]) if format=='json' else
            b'<feed xmlns="http://www.w3.org/2005/Atom"/>'),
        config=IngestionConfig(max_pages=2,max_http_requests=1))
    result=ctl.run_target(snaps[0],uuid4())
    assert result.execution_status=='failed' and result.coverage_status=='indeterminate'
    assert result.committed_pages==0 and result.request_count==1
    assert len(http.calls)==1 and not result.comparison_eligible
    assert not query(apple_database,'SELECT * FROM review_observation')
    assert_terminal_resolved(apple_database)


def test_application_contention_skips_without_intent_or_request(apple_database,tmp_path):
    from feasibility.apple_ingestion.recovery import application_session
    ctl,snaps,_,http,_=setup(apple_database,tmp_path,lambda app,page,format:Response(feed([page])))
    with application_session(apple_database,snaps[0].application_id):
        result=ctl.run_target(snaps[0],uuid4())
    assert result.skipped and result.stop_reason=='application_locked'
    assert not http.calls and not query(apple_database,'SELECT * FROM collection_run')


def test_empty_spool_startup_recovers_without_inventing_run(apple_database,tmp_path):
    from feasibility.apple_ingestion.recovery import application_session,recover_interrupted,replay_spool
    _,snaps,clock,http,spool=setup(apple_database,tmp_path,lambda *args:pytest.fail('unexpected HTTP'))
    with application_session(apple_database,snaps[0].application_id) as session:
        assert replay_spool(session.connection,snaps[0].application_id,spool,clock.now())==0
        assert recover_interrupted(session.connection,snaps[0].application_id,clock.now())==()
        session.assert_alive()
    assert not http.calls and not query(apple_database,'SELECT * FROM collection_run')


def test_session_loss_after_fetch_spools_unknown_then_restarts_page_one(apple_database,tmp_path):
    engine=apple_database
    def terminate(app,page,format):
        pids=query(engine,"""SELECT DISTINCT pid FROM pg_locks
            WHERE locktype='advisory' AND granted AND pid<>pg_backend_pid()""")
        assert len(pids)==1
        with engine.begin() as c:
            assert c.execute(text('SELECT pg_terminate_backend(:pid)'),dict(pid=pids[0]['pid'])).scalar_one()
    ctl,snaps,clock,http,spool=setup(engine,tmp_path,
        lambda app,page,format:Response(feed(range((page-1)*6,page*6))),before_request=terminate)
    broken=ctl.run_target(snaps[0],uuid4())
    assert broken.recovery_required and not broken.finalized
    assert len(http.calls)==1 and http.calls[0][1]==1
    assert not query(engine,'SELECT * FROM review_observation')
    events=spool.entries()
    assert events and 'APPLICATION_SESSION_LOST' in {entry['code'] for entry in events}
    assert {entry['run_id'] for entry in events}=={str(broken.run_id)}
    assert len({entry['attempt_id'] for entry in events})==1
    assert 'SYNTHETIC_FULL_BODY' not in json.dumps(events)
    http.before_request=None
    clock.seconds+=10
    recovered=ctl.run_target(snaps[0],uuid4())
    assert recovered.execution_status=='succeeded' and recovered.reference_run_id is None
    assert recovered.run_id!=broken.run_id and [call[1] for call in http.calls]==[1,1,2]
    old=query(engine,'SELECT * FROM collection_run WHERE id=:rid',rid=broken.run_id)[0]
    old_attempt=query(engine,'SELECT * FROM fetch_attempt WHERE run_id=:rid',rid=broken.run_id)[0]
    assert old['execution_status']=='interrupted' and old['coverage_status']=='indeterminate'
    assert old_attempt['http_status'] is None and old_attempt['parsing_status']=='not_attempted'
    assert 'REQUEST_OUTCOME_UNKNOWN' in old_attempt['error_codes']
    assert_terminal_resolved(engine)


def test_commit_acknowledgement_loss_reads_marker_without_replaying(apple_database,tmp_path,monkeypatch):
    from feasibility.apple_ingestion import controller as module
    from feasibility.apple_ingestion.reconcile import ReconciliationError
    original=module.persist_page
    calls=[]
    def lose_ack(connection,run_id,attempt_id,records,observed_at):
        result=original(connection,run_id,attempt_id,records,observed_at)
        calls.append(attempt_id)
        if len(calls)==1:
            raise ReconciliationError('DB_UNAVAILABLE',diagnostics_persisted=False)
        return result
    monkeypatch.setattr(module,'persist_page',lose_ack)
    ctl,snaps,_,http,_=setup(apple_database,tmp_path,
        lambda app,page,format:Response(feed(range((page-1)*6,page*6))))
    result=ctl.run_target(snaps[0],uuid4())
    assert result.execution_status=='succeeded' and result.comparison_eligible
    assert result.committed_pages==2 and len(calls)==len(http.calls)==2
    assert query(apple_database,'SELECT sum(occurrence_count) AS count FROM review_observation')[0]['count']==12
    assert len(query(apple_database,'SELECT * FROM review_version'))==12
    assert_terminal_resolved(apple_database)


def test_overlap_waits_for_all_conditions_and_stops_before_budget(apple_database,tmp_path):
    config=IngestionConfig(max_pages=3)
    ctl,snaps,clock,http,_=setup(apple_database,tmp_path,
        lambda app,page,format:Response(feed(range((page-1)*20,page*20))),config=config)
    first=ctl.run_target(snaps[0],uuid4())
    assert first.execution_status=='succeeded' and first.committed_pages==3
    clock.seconds+=24*3600
    before=len(http.calls)
    second=ctl.run_target(snaps[0],uuid4())
    assert second.reference_run_id==first.run_id
    assert second.coverage_status=='overlap_sufficient' and second.stop_reason=='overlap_met'
    # The first page already has 20 overlaps and 100%, but min_pages still blocks.
    assert second.committed_pages==2 and len(http.calls)-before==2
    assert_terminal_resolved(apple_database)


@pytest.mark.parametrize('stage',['lock','run_intent'])
def test_failure_before_run_persistence_keeps_intended_id_and_sends_nothing(apple_database,tmp_path,stage):
    engine=apple_database
    ctl,snaps,_,http,spool=setup(engine,tmp_path,lambda *args:pytest.fail('unexpected HTTP'))
    def fail_insert(connection,cursor,statement,parameters,context,executemany):
        if statement.startswith('INSERT INTO collection_run'):
            raise RuntimeError('SYNTHETIC_DATABASE_FAILURE')
    if stage=='lock':
        class UnavailableEngine:
            def connect(self):
                raise RuntimeError('SYNTHETIC_DATABASE_FAILURE')
        ctl.engine=UnavailableEngine()
    else:
        event.listen(engine,'before_cursor_execute',fail_insert)
    try:
        result=ctl.run_target(snaps[0],uuid4())
    finally:
        if stage=='run_intent':
            event.remove(engine,'before_cursor_execute',fail_insert)
    assert result.recovery_required and not result.finalized
    assert not result.run_persisted
    assert result.run_id is not None
    assert not http.calls and not query(engine,'SELECT * FROM collection_run')
    events=spool.entries()
    assert len(events)==1 and events[0]['run_id']==str(result.run_id)
    assert events[0]['stage']==('intent' if stage=='lock' else stage)
    assert 'SYNTHETIC_DATABASE_FAILURE' not in json.dumps(events)


@pytest.mark.parametrize('stage',['run_intent','second_page'])
def test_driver_commit_before_send_failure_never_later_commits_pending_writes(apple_database,tmp_path,monkeypatch,stage):
    import psycopg
    engine=apple_database
    ctl,snaps,_,http,_=setup(engine,tmp_path,
        lambda app,page,format:Response(feed(range((page-1)*6,page*6))))
    candidates=set()
    fired=[]
    original=psycopg.Connection.commit
    def mark_driver(connection,cursor,statement,parameters,context,executemany):
        matches=(stage=='run_intent' and statement.startswith('INSERT INTO collection_run'))
        matches|=(stage=='second_page' and len(http.calls)==2 and statement.startswith('INSERT INTO review_version'))
        if matches:
            candidates.add(connection.connection.driver_connection)
    def fail_before_send(driver):
        if driver in candidates and not fired:
            fired.append(driver)
            raise psycopg.OperationalError('SYNTHETIC_DRIVER_COMMIT_FAILURE')
        return original(driver)
    event.listen(engine,'after_cursor_execute',mark_driver)
    monkeypatch.setattr(psycopg.Connection,'commit',fail_before_send)
    try:
        result=ctl.run_target(snaps[0],uuid4())
    finally:
        event.remove(engine,'after_cursor_execute',mark_driver)
    assert len(fired)==1
    if stage=='run_intent':
        assert result.recovery_required and not result.run_persisted
        assert not http.calls and not query(engine,'SELECT * FROM collection_run')
        assert not query(engine,'SELECT * FROM review_version')
    else:
        assert result.execution_status=='partial' and result.committed_pages==1
        assert len(http.calls)==2
        assert len(query(engine,'SELECT * FROM review_version'))==6
        assert len(query(engine,'SELECT * FROM review_observation'))==6
        states=query(engine,'SELECT page_number,persistence_status FROM fetch_attempt ORDER BY page_number')
        assert [(row['page_number'],row['persistence_status']) for row in states]==[(1,'committed'),(2,'rolled_back')]
        assert_terminal_resolved(engine)

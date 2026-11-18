"""Independent fixed-depth acquisition and pure comparison; synthetic only."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import text

from feasibility.apple_ingestion import coverage_runner as runner_module
from feasibility.apple_ingestion.coverage_runner import FixedDepthRunner, CoverageError
from feasibility.apple_ingestion.coverage_comparison import compare, pair, window
from feasibility.apple_ingestion.coverage_schedule import StudyStore, new_plan, save_json
from feasibility.apple_ingestion.coverage_experiment import clock_check
from feasibility.apple_ingestion.contracts import ConfigSnapshot, IngestionConfig
from feasibility.apple_ingestion.parser import PARSER_VERSION
from feasibility.apple_ingestion.recovery import DiagnosticSpool
from feasibility.apple_ingestion.reporting import integrity_report
from feasibility.apple_ingestion.transport import BoundedTransport
from test_apple_ingestion_phase_c_integration import Clock, SyntheticSession, Response, feed, inspect_intent
from test_apple_ingestion_pagination_probe import atom

START = datetime(2026,11,13,17,tzinfo=timezone.utc)


def observation(index, *, fail=None, shift=0):
    pages = [{'page':p,'status':'valid','records':[{'review_id':str(shift+i)}
              for i in range((p-1)*50,p*50)]} for p in range(1,11)]
    status = 'succeeded'
    if fail:
        pages = pages[:fail-1]+[{'page':fail,'status':'incomplete'}]
        status = 'partial'
    return {'started_at':(START+timedelta(hours=12*index)).isoformat(),
            'pages':pages,'overall_status':status,
            'attempt_timings':[{'page':p} for p in range(1,(fail or 10)+1)]}


def test_strategy_references_intervals_cost_and_common_endpoints():
    items = [observation(i,shift=i*30) for i in range(7)]
    items[2]['started_at'] = (START+timedelta(hours=24,minutes=3)).isoformat()
    report = compare(items)
    assert [r['reference_observation'] for r in report['strategies']['A']['primary']] == [0,2,4]
    assert [r['reference_observation'] for r in report['strategies']['C']['primary']] == list(range(6))
    assert report['strategies']['A']['primary'][0]['interval_hours'] == 24.05
    assert report['strategies']['C']['primary'][1]['interval_hours'] == 12.05
    assert report['strategies']['A']['fixed_depth_requests_observed'] == 20
    assert report['strategies']['D']['fixed_depth_requests_observed'] == 70
    assert [r['observation'] for r in report['common_current_endpoints']['C']] == [2,4,6]
    assert report['strategies']['A']['primary'][0]['relative_new_ids'] == 60
    assert len(report['strategies']['A']['supplementary_24h']) == 2
    assert not report['completeness_established']


def test_five_prefix_survives_tail_failure_but_not_cross_prefix_conflict():
    items = [observation(i) for i in range(7)]
    items[2] = observation(2,fail=6)
    result = compare(items)
    assert result['strategies']['A']['primary'][0]['status'] == 'sufficient'
    assert result['strategies']['B']['primary'][0]['status'] == 'indeterminate'
    assert result['acquisition_failures'] == [{'observation':2,'status':'partial'}]
    assert result['strategies']['B']['replay'][1]['status'] == 'sufficient'
    assert result['strategies']['B']['replay'][1]['actual_acquisition_status'] == 'partial'
    items[2]['pages'][-1]['invalidated_pages'] = [2]
    assert window(items[2],5) is None


def test_replay_uses_own_early_stopped_reference_and_missing_is_not_backfilled():
    items = [observation(i) for i in range(7)]
    result = compare(items)['strategies']['D']['replay']
    assert [r['stopped_depth'] for r in result] == [10,2,2,2,2,2,2]
    assert result[2]['metrics']['reference_count'] == 100
    items[2] = None
    result = compare(items)
    assert result['strategies']['A']['primary'][0]['status'] == 'indeterminate'
    assert result['strategies']['C']['replay'][3]['virtual_reference_observation'] == 1
    assert result['strategies']['C']['replay'][3]['interval_hours'] == 24
    assert result['strategies']['A']['startup_inclusive_requests_per_actual_day'] is None


def store_at(tmp_path):
    directory = tmp_path/'state'
    directory.mkdir(mode=0o700)
    store = StudyStore(directory)
    value = new_plan('2026-11-13T09:00:00','apple_coverage_main_fixture',now=START-timedelta(days=1))
    store.save(value)
    return store


def enable(store):
    value = store.load()
    value.update(enabled=True,clock_verified=True)
    store.save(value)


def test_disabled_source_changed_and_scope_validation(tmp_path,monkeypatch):
    store = store_at(tmp_path)
    with pytest.raises(CoverageError,match='DISABLED'):
        store.reserve_slot(at=START)
    enable(store)
    monkeypatch.setattr('feasibility.apple_ingestion.coverage_schedule.source_hash',lambda:'0'*64)
    with pytest.raises(CoverageError,match='SOURCE_CHANGED'):
        store.reserve_slot(at=START)
    value = store.load(); value['slots'][1]['requests'] = 21; store.save(value)
    with pytest.raises(CoverageError,match='INVALID_STUDY_MANIFEST'):
        store.load()


def test_schedule_exact_future_local_utc_and_dst_rejection():
    plan = new_plan('2026-11-13T09:00:00','apple_coverage_main_fixture',now=START-timedelta(days=1))
    assert [s['planned_utc'] for s in plan['slots']] == [
        (START+timedelta(hours=12*i)).isoformat() for i in range(7)]
    assert not plan['enabled'] and not plan['clock_verified']
    with pytest.raises(CoverageError,match='FUTURE'):
        new_plan('2026-11-13T09:00:00','apple_coverage_main_fixture',now=START)
    with pytest.raises(CoverageError,match='DST'):
        new_plan('2026-10-31T09:00:00','apple_coverage_main_fixture',now=START-timedelta(days=20))


def test_duplicate_unknown_reservation_and_no_missed_slot_replay(tmp_path):
    store = store_at(tmp_path); enable(store)
    with pytest.raises(CoverageError,match='OUTSIDE_WINDOW'):
        store.reserve_slot(at=START-timedelta(seconds=1))
    slot = store.reserve_slot(at=START)
    assert slot['index']==0
    with pytest.raises(CoverageError,match='INTERRUPTED'):
        store.reserve_slot(at=START+timedelta(seconds=1))
    assert store.load()['hold']


def test_seven_slots_total_budget_and_retirement(tmp_path):
    store = store_at(tmp_path); enable(store)
    with pytest.raises(CoverageError,match='NOT_TERMINAL'):
        store.retire()
    for i in range(7):
        at = START+timedelta(hours=12*i)
        assert store.reserve_slot(at=at)['index'] == i
        for j in range(20):
            store.reserve_request(i,j//2+1,'xml' if j%2 else 'json',at=at)
        with pytest.raises(CoverageError,match='BUDGET'):
            store.reserve_request(i,10,'xml',at=at)
        store.finish(i,{'overall_status':'succeeded'})
    assert sum(s['requests'] for s in store.load()['slots']) == 140
    store.retire()
    assert store.load()['retired'] and not store.load()['enabled']
    with pytest.raises(CoverageError,match='DISABLED'):
        store.reserve_slot(at=START+timedelta(hours=72))


def test_missed_slots_recorded_without_backfill_and_failure_hold(tmp_path):
    store=store_at(tmp_path); enable(store)
    assert store.reserve_slot(at=START+timedelta(hours=12))['index'] == 1
    assert store.load()['slots'][0]['status'] == 'missed'
    store.finish(1,{'overall_status':'partial'})
    with pytest.raises(CoverageError,match='DISABLED'):
        store.reserve_slot(at=START+timedelta(hours=24))
    store.maintenance(at=START+timedelta(days=4))
    assert store.load()['slots'][-1]['status'] == 'missed'
    store.retire()


def test_clock_steps_and_rate_drift_detected():
    def check(wall_values,mono_values,raw_values):
        w,m,r=map(iter,(wall_values,mono_values,raw_values))
        return clock_check(sleep=lambda _:None,wall=lambda:next(w),mono=lambda:next(m),raw=lambda:next(r))
    assert check([0,2],[0,2],[0,2])['verified']
    assert not check([0,.41],[0,2.11],[0,2])['verified']
    assert not check([0,2.11],[0,2.11],[0,2])['verified']


def setup_runner(engine,tmp_path,respond,*,before=None,database=None,guard=None,reserve=None,clock=None):
    from feasibility.apple_ingestion.seed import seed_defaults
    config = replace(IngestionConfig(),interval_hours=12,max_pages=10,max_http_requests=20)
    with engine.begin() as c:
        seed_defaults(c,Path(__file__).resolve().parents[1]/'results/mainstream/app_sample_manifest.json')
        row = c.execute(text("SELECT a.id,t.id FROM application a JOIN collection_target t ON t.application_id=a.id WHERE a.source_application_id='570060128'")).one()
        c.execute(text('UPDATE collection_target SET interval_hours=12,max_pages=10,max_http_requests=20 WHERE id=:id'),{'id':row[1]})
        actual = c.scalar(text('SELECT current_database()'))
    snapshot=ConfigSnapshot(row[0],'570060128',row[1],'synthetic-coverage',PARSER_VERSION,config=config)
    clock=clock or Clock(); http=SyntheticSession(clock,respond,before)
    spool=DiagnosticSpool(tmp_path/'diagnostics.jsonl')
    outputs=[]; reservations=[]
    runner=FixedDepthRunner(engine,BoundedTransport(http,clock=clock.monotonic,sleep=clock.sleep),spool,
        database=database or actual,guard=guard or (lambda:None),reserve=reserve or (lambda p,f:reservations.append((p,f))),
        checkpoint=lambda o:outputs.append(json.loads(json.dumps(o,default=str))),now=clock.now,monotonic=clock.monotonic)
    return runner,snapshot,http,clock,outputs,spool


def run(runner,snapshot):
    return runner.run(snapshot,uuid4())


def assert_integrity(engine):
    with engine.connect() as c:
        assert integrity_report(c)['ok']


def test_ten_contiguous_pages_database_fulltext_and_no_transaction_during_http(apple_database,tmp_path):
    runner,snapshot,http,clock,outputs,_=setup_runner(apple_database,tmp_path,
        lambda app,p,f:Response(feed(range(p*50,p*50+50))),
        before=lambda app,p,f:inspect_intent(apple_database,app,p,f))
    result=run(runner,snapshot)
    assert result['overall_status']=='succeeded' and result['requests']==10
    assert [call[1] for call in http.calls]==list(range(1,11))
    assert [call[3] for call in http.calls]==list(range(0,20,2))
    with apple_database.connect() as c:
        assert c.scalar(text('SELECT count(*) FROM review_version'))==500
        assert c.scalar(text("SELECT count(*) FROM review_version WHERE body='SYNTHETIC_FULL_BODY🙂'"))==500
    assert 'SYNTHETIC_FULL_BODY' not in json.dumps(outputs)
    assert_integrity(apple_database)
    # A later reference already overlaps, but experimental acquisition still reaches ten.
    clock.sleep(43200)
    again=run(runner,snapshot)
    assert again['requests']==10 and again['result']['reference_run_id'] is not None
    assert again['result']['committed_pages']==10


def test_tail_parser_failure_preserves_five_page_prefix(apple_database,tmp_path):
    runner,snapshot,http,*_=setup_runner(apple_database,tmp_path,
        lambda app,p,f:Response(b'{}' if p==6 else feed(range(p*50,p*50+50))))
    result=run(runner,snapshot)
    assert result['overall_status']=='partial' and result['requests']==6
    assert window(result,5) is not None and window(result,10) is None
    assert not result['result']['comparison_eligible']
    assert_integrity(apple_database)


def test_twenty_physical_requests_with_fallback(apple_database,tmp_path):
    runner,snapshot,http,*_=setup_runner(apple_database,tmp_path,
        lambda app,p,f:Response(b'{"feed":{}}' if f=='json' else atom([p])))
    result=run(runner,snapshot)
    assert result['overall_status']=='succeeded' and len(http.calls)==20
    assert all(page['requests']==2 for page in result['pages'])
    assert_integrity(apple_database)


@pytest.mark.parametrize('kind',['duplicate','conflict','empty','denial'])
def test_blocking_conditions_stop_without_retry(apple_database,tmp_path,kind):
    def respond(app,p,f):
        if p<6:return Response(feed([p]))
        if kind=='duplicate':return Response(feed([1]))
        if kind=='conflict':return Response(feed([1],body='DIFFERENT_PRIVATE_TEXT'))
        if kind=='empty':return Response(b'{"feed":{}}' if f=='json' else atom([]))
        return Response(b'PRIVATE_DENIAL_BODY',403)
    runner,snapshot,http,_,outputs,_=setup_runner(apple_database,tmp_path,respond)
    result=run(runner,snapshot)
    assert result['overall_status']=='partial'
    assert len(http.calls)==(7 if kind=='empty' else 6)
    if kind=='conflict':
        assert result['pages'][-1]['invalidated_pages']==[1]
        with apple_database.connect() as c:
            assert c.scalar(text('SELECT count(*) FROM review_version'))==5
    else: assert window(result,5) is not None
    assert 'PRIVATE' not in json.dumps(outputs)
    assert_integrity(apple_database)


def test_database_mismatch_never_dispatches_and_unsupported_snapshot_rejected(apple_database,tmp_path):
    runner,snapshot,http,*_=setup_runner(apple_database,tmp_path,lambda *a:Response(feed([1])),database='apple_ingestion')
    result=run(runner,snapshot)
    assert result['overall_status']=='recovery_required' and not http.calls
    with pytest.raises(CoverageError,match='SCOPE'):
        run(runner,replace(snapshot,config=IngestionConfig()))


def test_page_transaction_failure_retains_prefix_then_recovery_is_not_retried(apple_database,tmp_path,monkeypatch):
    original=runner_module.persist_page
    def fail(connection,run_id,attempt_id,records,at):
        if records[0].source_review_id=='6':
            from feasibility.apple_ingestion.reconcile import ReconciliationError
            raise ReconciliationError('PERSISTENCE_ERROR')
        return original(connection,run_id,attempt_id,records,at)
    runner,snapshot,http,clock,outputs,spool=setup_runner(apple_database,tmp_path,
        lambda app,p,f:Response(feed([p])))
    monkeypatch.setattr(runner_module,'persist_page',fail)
    result=run(runner,snapshot)
    assert result['overall_status']=='recovery_required' and len(http.calls)==6
    assert window(result,5) is not None
    assert_integrity(apple_database)
    again=run(runner,snapshot)
    assert again['overall_status']=='recovery_required' and len(http.calls)==6
    with apple_database.connect() as c:
        assert c.scalar(text('SELECT count(*) FROM review'))==5
        assert c.scalar(text("SELECT count(*) FROM collection_run WHERE execution_status='interrupted'"))==1
    assert_integrity(apple_database)


def test_after_commit_acknowledgement_loss_is_resolved_on_same_session(apple_database,tmp_path,monkeypatch):
    original=runner_module.persist_page
    def ack(connection,*args,**kwargs):
        result=original(connection,*args,**kwargs)
        from feasibility.apple_ingestion.reconcile import ReconciliationError
        raise ReconciliationError('PERSISTENCE_ERROR')
    monkeypatch.setattr(runner_module,'persist_page',ack)
    runner,snapshot,http,*_=setup_runner(apple_database,tmp_path,lambda app,p,f:Response(feed([p])))
    result=run(runner,snapshot)
    assert result['overall_status']=='succeeded' and len(http.calls)==10
    assert_integrity(apple_database)


def test_real_operator_verification_is_zero_http_and_disabled_observe_does_not_create_session(tmp_path,monkeypatch):
    from feasibility.apple_ingestion import coverage_experiment as operator
    store=store_at(tmp_path)
    monkeypatch.setattr(operator,'load_config',lambda _:object())
    monkeypatch.setattr(operator,'environments',lambda *a:({},{}))
    monkeypatch.setattr(operator,'verify',lambda *a,**kw:{'real_http_performed':False})
    result=operator.operate(store,'verify',session_factory=lambda:pytest.fail('HTTP session created'))
    assert result['real_http_performed'] is False
    assert (store.directory/'entry-verification.json').exists()
    # Scope gate is evaluated before runtime connections/target updates/session creation.
    from contextlib import nullcontext
    monkeypatch.setattr(operator,'existing_operator_lock',lambda:nullcontext())
    monkeypatch.setattr(operator,'deployment_engine',lambda *a,**kw:pytest.fail('engine before gate'))
    with pytest.raises(CoverageError,match='DISABLED'):
        operator.operate(store,'observe',session_factory=lambda:pytest.fail('session created'))


def test_nonblocking_state_lock_and_malformed_manifest_do_not_allow_dispatch(tmp_path):
    store=store_at(tmp_path)
    with store.locked():
        with pytest.raises(CoverageError,match='BUSY'):
            with StudyStore(store.directory).locked():pass
    plan=store.load();plan['slots'][3]['planned_utc']=plan['slots'][2]['planned_utc'];store.save(plan)
    with pytest.raises(CoverageError,match='MANIFEST'):
        store.load()


def test_last_missed_slot_consolidates_without_fabricated_observations(tmp_path):
    from feasibility.apple_ingestion.coverage_experiment import consolidate
    store=store_at(tmp_path);enable(store)
    store.maintenance(at=START+timedelta(days=4))
    result=consolidate(store)
    assert len(result['acquisition_failures'])==7
    assert result['strategies']['D']['evaluable']==0
    assert result['requests_reserved']==0
    assert 'PRIVATE' not in (store.directory/'technical-report.md').read_text()
    store.retire()
    assert not store.load()['enabled']


def test_operator_hold_is_not_cleared_by_successful_finalization(tmp_path):
    store=store_at(tmp_path);enable(store)
    store.reserve_slot(at=START)
    plan=store.load();plan['hold']=True;store.save(plan)
    store.finish(0,{'overall_status':'succeeded'})
    assert store.load()['hold']


def test_request_reservation_failure_never_dispatches_unbudgeted_http(apple_database,tmp_path):
    count=0
    def reserve(page,fmt):
        nonlocal count
        count+=1
        if count==2:raise CoverageError('EXPERIMENT_REQUEST_BUDGET')
    runner,snapshot,http,*_=setup_runner(apple_database,tmp_path,lambda app,p,f:Response(feed([p])),reserve=reserve)
    result=run(runner,snapshot)
    assert result['overall_status']=='partial' and len(http.calls)==1
    assert result['requests']==1
    assert_integrity(apple_database)


def test_missing_or_failed_post_run_verification_prevents_prefix_promotion(tmp_path):
    from feasibility.apple_ingestion.coverage_experiment import consolidate
    store=store_at(tmp_path)
    for index in range(7):
        save_json(store.directory/f'observation-{index}.json',observation(index,fail=6))
    result=consolidate(store)
    assert result['verification_failures']==list(range(7))
    assert result['strategies']['A']['evaluable']==0
    # An independently verified prefix may still survive deep acquisition failure.
    for index in range(7):
        save_json(store.directory/f'verification-{index}.json',
                  {'integrity':{'ok':True},'original_pilot_unchanged':True})
    result=consolidate(store)
    assert result['verification_failures']==[]
    assert result['strategies']['A']['evaluable']==3
    assert result['strategies']['B']['evaluable']==0


def test_unknown_send_still_consumes_offline_request_cost(apple_database,tmp_path,monkeypatch):
    from feasibility.apple_ingestion.coverage_comparison import request_cost
    runner,snapshot,http,_,outputs,_=setup_runner(apple_database,tmp_path,
        lambda app,p,f:Response(feed([p])))
    def fail_metadata(*args,**kwargs):
        raise RuntimeError('PRIVATE_UNSAFE_EXCEPTION')
    monkeypatch.setattr(runner.helper,'_complete_attempt',fail_metadata)
    result=run(runner,snapshot)
    assert result['overall_status']=='recovery_required' and len(http.calls)==1
    assert result['attempt_timings']==[{'request_number':1,'page':1,'format':'json','status':'reserved'}]
    assert request_cost(result,5)==1
    assert outputs[1]['attempt_timings'][0]['status']=='reserved'
    assert 'PRIVATE_UNSAFE_EXCEPTION' not in json.dumps(outputs)
    report=compare([result,None,None,None,None,None,None])
    assert report['strategies']['A']['reserved_request_outcomes_unconfirmed']==1

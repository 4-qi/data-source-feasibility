"""Synthetic rehearsal semantics, local-only DB guard and safe artifact checks."""
from datetime import date,datetime,time,timedelta
import hashlib
import json
from types import SimpleNamespace

import pytest
from sqlalchemy import URL,text

from feasibility.apple_ingestion.parser import parse_feed
from feasibility.apple_ingestion.synthetic import (
    LOCAL_ZONE,ScenarioSession,SimulatedClock,SyntheticError,fresh_output_directory,
    rehearse,scenario_response,validate_disposable_engine,
)


def test_scenario_preserves_A_B_A_metadata_and_full_unicode_text():
    snapshots=[]
    for day in range(3):
        _,payload=scenario_response(0,day,1 if day<2 else 2,'json')
        records=parse_feed(payload,'json').records
        snapshots.append(next(record for record in records if record.source_review_id=='synthetic:0:0000'))
    assert snapshots[0].body==snapshots[2].body!=snapshots[1].body
    _,payload=scenario_response(7,0,1,'json')
    assert len(parse_feed(payload,'json').records[0].body)>20_000
    _,payload=scenario_response(1,3,1,'json')
    assert parse_feed(payload,'json').records[0].application_version=='2.0'


def test_simulated_calendar_clock_crosses_dst_without_real_sleep():
    first=datetime.combine(date(2026,10,31),time(9),LOCAL_ZONE)
    next_day=datetime.combine(date(2026,11,1),time(9),LOCAL_ZONE)
    clock=SimulatedClock(first)
    clock.advance_to(next_day)
    assert clock.monotonic()==25*3600
    with pytest.raises(SyntheticError,match='CANNOT_REWIND'):
        clock.advance_to(first)


@pytest.mark.parametrize('query,host,database',[
    ({'host':'/tmp/socket','hostaddr':'198.51.100.1'},None,'apple_phase_a_fixture'),
    ({'host':'/tmp/socket','service':'shared'},None,'apple_phase_a_fixture'),
    ({'host':'/tmp/socket'},'remote.example','apple_phase_a_fixture'),
    ({'host':'/var/run/postgresql'},None,'apple_phase_a_fixture'),
    ({'host':'/tmp/socket'},None,'production'),
    ({'host':'/tmp/socket,/remote'},None,'apple_phase_a_fixture'),
])
def test_database_guard_rejects_remote_or_shared_before_connect(query,host,database):
    engine=SimpleNamespace(url=URL.create('postgresql+psycopg',host=host,database=database,query=query),
        echo=False,hide_parameters=True,connect=lambda:pytest.fail('guard connected'))
    with pytest.raises(SyntheticError,match='PRIVATE_DISPOSABLE'):
        validate_disposable_engine(engine,disposable=True)


def test_database_guard_requires_explicit_optin_before_inspecting_engine():
    with pytest.raises(SyntheticError,match='OPT_IN'):
        validate_disposable_engine(None)


def test_output_refuses_existing_symlink_repo_or_non_tmp(tmp_path):
    existing=tmp_path/'existing'
    existing.mkdir()
    link=tmp_path/'link'
    link.symlink_to(existing,target_is_directory=True)
    for path in (existing,link,'/home/synthetic-output'):
        with pytest.raises(SyntheticError,match='FRESH_PRIVATE_TMP'):
            fresh_output_directory(path)
    (existing/'.git').mkdir()
    (existing/'.git/HEAD').write_text('ref: refs/heads/main\n')
    with pytest.raises(SyntheticError):
        fresh_output_directory(existing/'inside-git')


def test_real_seven_day_pipeline_artifacts_and_history(apple_database,tmp_path):
    output=tmp_path/'rehearsal'
    result=rehearse(apple_database,output,disposable=True)
    summary=result['summary']
    assert summary['evidence_kind']=='synthetic'
    assert summary['planned_slots']==summary['attempted_slots']==56
    assert summary['missing_slots']==0
    assert len(summary['batches'])==len({row['batch_id'] for row in summary['batches']})==7
    assert summary['execution_counts']['partial']>=1 and summary['execution_counts']['failed']>=1
    assert sum(summary['execution_counts'].values())==56
    assert summary['requests']<=560
    assert summary['committed_pages']<=280
    assert summary['assessment_status']=='pending_human_review'
    assert summary['integrity_ok'] is True
    safe_files=list((output/'safe').glob('*.json'))
    for path in safe_files+[output/'summary.json',output/'checksums.json']:
        payload=json.loads(path.read_text())
        assert payload['evidence_kind']=='synthetic'
        assert not any(secret in path.read_text() for secret in
            ('SYNTHETIC_BODY','SYNTHETIC_TITLE','SYNTHETIC_DISPUTED_ALTERNATE','synthetic:0:0000'))
    hashes=json.loads((output/'checksums.json').read_text())['files']
    for relative,digest in hashes.items():
        assert hashlib.sha256((output/relative).read_bytes()).hexdigest()==digest
    protocol=json.loads((output/'safe/protocol.json').read_text())
    config=protocol['config']
    assert (config['min_pages'],config['max_pages'],config['min_overlap_count'],
            config['min_overlap_ratio'],config['max_http_requests'],config['retry_count'])==(2,5,20,.2,10,0)
    assert protocol['extra_diagnostic_runs']==0
    assert (output/'private-assessment').is_dir()
    for path in (output/'private-assessment').glob('*.json'):
        assert json.loads(path.read_text())['evidence_kind']=='synthetic'
    pending=json.loads((output/'private-assessment/responses.pending.json').read_text())
    assert len(pending['records'])==80
    assert all(row['label'] is None and not row['full_text_read'] for row in pending['records'])
    with apple_database.connect() as c:
        assert c.execute(text('SELECT count(*) FROM collection_run')).scalar_one()==56
        assert c.execute(text('SELECT count(DISTINCT batch_id) FROM collection_run')).scalar_one()==7
        versions=c.execute(text("""SELECT v.body FROM review_version v JOIN review r ON r.id=v.review_id
            WHERE r.source_review_id='synthetic:0:0000' ORDER BY v.version_number""")).scalars().all()
        assert len(versions)==3 and versions[0]==versions[2]!=versions[1]
        # Omitted from later synthetic windows: identity/history stays present.
        absent=c.execute(text("SELECT first_observed_at,last_observed_at FROM review WHERE source_review_id='synthetic:6:0000'")).one()
        assert absent[0]==absent[1]
        assert c.execute(text('SELECT max(length(body)) FROM review_version')).scalar_one()>20_000
        assert c.execute(text("SELECT count(*) FROM fetch_attempt WHERE parsing_status='pending' OR persistence_status IN ('pending','unknown')")).scalar_one()==0
    with pytest.raises(SyntheticError,match='EMPTY_DISPOSABLE'):
        rehearse(apple_database,tmp_path/'second',disposable=True)

"""Offline privacy, parsing and request-boundary checks for the comparison probe."""
import importlib.util
import json
from pathlib import Path
import pytest

spec=importlib.util.spec_from_file_location('mobile_quality_probe',Path(__file__).resolve().parents[1]/'probes/mobile_quality.py')
probe=importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)

@pytest.fixture(autouse=True)
def reset_probe():
    probe.EVENTS=[];probe.PRIVATE={};probe.BLOCKED=set();probe.LAST=None


def test_json_and_atom_preserve_same_review_fields_without_author():
    row={'id':{'label':'source-id'},'content':{'label':'A useful workflow detail'},'im:rating':{'label':'2'},'updated':{'label':'2026-10-27'},'im:version':{'label':'1'},'author':{'name':'PRIVATE_AUTHOR'}}
    js=json.dumps({'feed':{'entry':[row]}}).encode()
    xml=b'<feed xmlns="http://www.w3.org/2005/Atom" xmlns:im="http://itunes.apple.com/rss"><entry><id>source-id</id><content>A useful workflow detail</content><im:rating>2</im:rating><updated>2026-10-27</updated><im:version>1</im:version><author>PRIVATE_AUTHOR</author></entry></feed>'
    assert probe.apple_rows(js,'json')==probe.apple_rows(xml,'xml')
    assert 'PRIVATE_AUTHOR' not in json.dumps(probe.apple_rows(js,'json'))


def test_missing_entries_and_invalid_feed_are_distinct():
    assert probe.apple_rows(b'{"feed":{}}','json')==[]
    with pytest.raises(ValueError,match='feed_schema'):
        probe.apple_rows(b'{"error":"unavailable"}','json')


def test_google_framing_cursor_and_privacy_projection():
    rows=[['REVIEW_PRIVATE_ID',['PRIVATE_AUTHOR'],1,None,'PRIVATE_BODY',[1793145600]]]
    frame=json.dumps([['wrb.fr','oCPfdb',json.dumps([rows,['CURSOR_PRIVATE'],None])]])
    result,cursor=probe.google_rows((")]}'\n\n100\n"+frame+'\n').encode())
    assert cursor=='CURSOR_PRIVATE'
    projected=probe.project(result[0],'google',probe.APPS[0])
    saved=json.dumps(projected)
    assert projected['rating']==1 and projected['date']==1793145600
    for secret in ('REVIEW_PRIVATE_ID','PRIVATE_AUTHOR','PRIVATE_BODY','CURSOR_PRIVATE'):
        assert secret not in saved
    assert probe.PRIVATE[projected['fingerprint']]['inspection_prefix']=='PRIVATE_BODY'


def test_absent_source_id_cannot_be_fabricated():
    with pytest.raises(ValueError,match='missing_identity'):
        probe.project({'id':None,'text':'A review body','rating':3},'apple',probe.APPS[0])


def test_invalid_google_row_fails_closed():
    frame=json.dumps([['wrb.fr','oCPfdb',json.dumps([[['id',[],9,None,'body',[]]],None,None])]])
    with pytest.raises(ValueError,match='google_review_schema'):
        probe.google_rows(frame.encode())


def test_global_request_budget_prevents_network():
    probe.EVENTS=[{}]*32
    with pytest.raises(ValueError,match='request_budget_exhausted'):
        probe.fetch('apple',probe.APPS[0],1,'baseline')


def test_denial_stops_source_without_retry(monkeypatch):
    class Denied:
        status_code=403
        def __enter__(self):return self
        def __exit__(self,*args):return False
    calls=[]
    def denied(*args,**kwargs):calls.append(kwargs);return Denied()
    monkeypatch.setattr(probe.SESSION,'get',denied)
    event,_=probe.fetch('apple',probe.APPS[0],1,'baseline')
    assert event['status']==403 and event['records']==[]
    assert probe.fetch('apple',probe.APPS[1],1,'baseline')==(None,None)
    assert len(calls)==1 and calls[0]['allow_redirects'] is False


def test_inspection_file_inside_repository_is_rejected_before_collection(tmp_path):
    with pytest.raises(ValueError,match='inspection_output_must_be_outside'):
        probe.main(['initial','--output',str(tmp_path),'--inspection-output',str(probe.R/'raw'/'private.json')])
    assert probe.EVENTS==[]


def test_initial_phase_refuses_to_overwrite_prior_evidence(tmp_path):
    (tmp_path/'collection.json').write_text('{"preserved":true}')
    with pytest.raises(FileExistsError):
        probe.main(['initial','--output',str(tmp_path),'--inspection-output',str(tmp_path/'private.json')])
    assert (tmp_path/'collection.json').read_text()=='{"preserved":true}'
    assert probe.EVENTS==[]

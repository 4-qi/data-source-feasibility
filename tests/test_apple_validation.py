"""Offline transport, privacy and failure-boundary checks for the RSS diagnostic."""
import json
import pytest
from feasibility import apple_validation as probe


class Response:
    def __init__(self, status, body):
        self.status_code=status
        self.body=body
        self.headers={'Content-Type':'application/json'}
    def __enter__(self):return self
    def __exit__(self,*args):return False
    def iter_content(self,size):
        yield self.body


class Session:
    def __init__(self,status=200,body=None):
        self.status=status;self.body=body;self.headers={};self.calls=[];self.xml_body=None
        self.cookies=type('Cookies',(),{'clear':lambda self:None})()
    def get(self,url,**kwargs):
        self.calls.append((url,kwargs))
        if self.xml_body is not None and url.endswith('/xml'):return Response(self.status,self.xml_body)
        if self.body is not None:return Response(self.status,self.body)
        app_id=url.split('/id=')[1].split('/')[0]
        page=url.split('/page=')[1].split('/')[0]
        entry={'id':{'label':app_id+':'+page},'content':{'label':'SENSITIVE_REVIEW_BODY_DO_NOT_RETAIN'},
               'author':{'name':{'label':'PRIVATE_AUTHOR'}},'im:rating':{'label':'1'},
               'updated':{'label':'2026-10-27'},'title':{'label':'PRIVATE_TITLE'},'im:version':{'label':'1.0'}}
        return Response(self.status,json.dumps({'feed':{'entry':[entry]}}).encode())


def setup_run(tmp_path,monkeypatch,session,apps=None):
    path=tmp_path/'manifest.json'
    path.write_text(json.dumps({'apps':apps if apps is not None else [
        {'app_store_id':str(i),'name':'Fixture','analysis_stratum':'fixture'} for i in range(1,9)]}))
    monkeypatch.setattr(probe.requests,'Session',lambda:session)
    monkeypatch.setattr(probe.time,'sleep',lambda duration:None)
    return ['--manifest',str(path),'--output',str(tmp_path/'output')]


def load_output(tmp_path):
    paths=list((tmp_path/'output').glob('apple_rss_access_*.json'))
    assert len(paths)==1
    return json.loads(paths[0].read_text())


def test_request_budget_repeat_identity_and_privacy(tmp_path,monkeypatch):
    session=Session();args=setup_run(tmp_path,monkeypatch,session)
    assert probe.main(args)==0
    result=load_output(tmp_path)
    assert len(session.calls)==result['http_requests']==10
    assert result['distinct_parsed_fingerprints']==9
    assert result['repeat_same_sample_ids'] is True
    assert result['page_1_page_2_sample_overlap']==0
    saved=json.dumps(result)
    for secret in ('SENSITIVE_REVIEW_BODY_DO_NOT_RETAIN','PRIVATE_AUTHOR','PRIVATE_TITLE'):
        assert secret not in saved
    assert session.trust_env is False
    for url,kwargs in session.calls:
        assert url.startswith('https://itunes.apple.com/us/rss/customerreviews/')
        assert kwargs['allow_redirects'] is False
        assert kwargs['timeout']==(10,25)
        assert kwargs['stream'] is True
        assert 'auth' not in kwargs


def test_first_denial_stops_all_remaining_requests(tmp_path,monkeypatch):
    session=Session(status=403);args=setup_run(tmp_path,monkeypatch,session)
    assert probe.main(args)==1
    assert len(session.calls)==1
    assert load_output(tmp_path)['stopped_on_error'] is True


def test_invalid_feed_is_failure_not_empty_corpus(tmp_path,monkeypatch):
    session=Session(body=b'{"error":"PRIVATE_DIAGNOSTIC"}');args=setup_run(tmp_path,monkeypatch,session)
    assert probe.main(args)==1
    result=load_output(tmp_path)
    assert result['runs'][0]['entries_returned'] is None
    assert 'PRIVATE_DIAGNOSTIC' not in json.dumps(result)
    assert len(session.calls)==1


def test_oversized_response_stops_without_saving_body(tmp_path,monkeypatch):
    session=Session(body=b'X'*2000001);args=setup_run(tmp_path,monkeypatch,session)
    assert probe.main(args)==1
    assert load_output(tmp_path)['runs'][0]['entries_returned'] is None
    assert len(session.calls)==1


def test_invalid_manifest_cannot_make_requests(tmp_path,monkeypatch):
    session=Session();args=setup_run(tmp_path,monkeypatch,session,apps=[
        {'app_store_id':'1/../../private','name':'Fixture','analysis_stratum':'fixture'} for _ in range(8)])
    with pytest.raises(ValueError,match='manifest_requires'):
        probe.main(args)
    assert session.calls==[]


def test_valid_feed_without_entries_does_not_claim_reviews(tmp_path,monkeypatch):
    session=Session(body=b'{"feed":{"updated":{"label":"2026-10-27"}}}')
    session.xml_body=b'<feed xmlns="http://www.w3.org/2005/Atom"/>'
    args=setup_run(tmp_path,monkeypatch,session)
    assert probe.main(args)==1
    result=load_output(tmp_path)
    assert result['http_200']==13
    assert result['request_budget_exhausted'] is True
    assert result['distinct_parsed_fingerprints']==0
    assert result['ongoing_update_detection']=='NOT_TESTED'
    assert result['production_use_rights']=='NOT_ESTABLISHED'


def test_xml_parser_uses_atom_namespace_and_preserves_only_needed_fields():
    payload=b'<feed xmlns="http://www.w3.org/2005/Atom" xmlns:im="http://itunes.apple.com/rss"><entry><id>123</id><content>Experience text</content><im:rating>2</im:rating><im:version>1.0</im:version><author><name>PRIVATE_AUTHOR</name></author></entry></feed>'
    feed=probe.decode_feed(payload,xml=True)
    assert feed['entry'][0]['im:rating']=={'label':'2'}
    assert feed['entry'][0]['content']=={'label':'Experience text'}
    assert 'PRIVATE_AUTHOR' not in json.dumps(feed)

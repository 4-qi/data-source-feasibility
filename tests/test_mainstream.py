"""Offline checks for a bounded access gate, not a new validated review collector."""
import json

import pytest
from feasibility.http import StopCollection
from feasibility import mainstream_validation as probe


class FakeClient:
    def __init__(self, response=None, error=None):
        self.response = response
        self.error = error
        self.calls = []
        self.events = []

    def get(self, url, params=None):
        self.calls.append((url, params))
        status = 403 if self.error == 'access_or_rate_denial' else None if self.error else 200
        self.events.append({'status': status, 'error': self.error})
        if self.error:
            raise StopCollection(self.error)
        return self.response


def test_one_documented_request_and_no_raw_content():
    client = FakeClient({'hits': {'hits': [{'private': 'SOURCE_TEXT_DO_NOT_SAVE'}]},
                         '_meta': {'last_updated': 'not-retained'}})
    result = probe.probe(client)
    assert client.calls == [(probe.ENDPOINT, {'size': 2, 'frm': 0, 'sort': 'created_date_desc',
                                            'no_aggs': 'true', 'no_highlight': 'true'})]
    assert result['http_requests'] == 1
    assert result['response_schema'] == {'hits': 'dict', '_meta': 'dict'}
    assert 'SOURCE_TEXT_DO_NOT_SAVE' not in json.dumps(result)
    assert 'not-retained' not in json.dumps(result)
    assert result['narrative_availability'] == 'NOT_ASSESSED'


@pytest.mark.parametrize('error', ['access_or_rate_denial', 'transport_error', 'malformed_json'])
def test_denial_or_failure_is_saved_without_retry(error):
    client = FakeClient(error=error)
    result = probe.probe(client)
    assert len(client.calls) == 1
    assert result['error'] == error
    assert result['response_schema'] is None
    assert result['narrative_availability'] == 'NOT_ASSESSED'


def test_empty_response_is_not_evidence_of_empty_review_corpus():
    result = probe.probe(FakeClient({}))
    assert result['response_schema'] == {}
    assert result['narrative_availability'] == 'NOT_ASSESSED'


def test_unexpected_response_stops_without_storing_payload():
    result = probe.probe(FakeClient(['PRIVATE_PAYLOAD']))
    assert result['error'] == 'unexpected_cfpb_schema'
    assert 'PRIVATE_PAYLOAD' not in json.dumps(result)


def test_default_client_has_one_request_budget(monkeypatch):
    seen = {}
    def factory(host, max_requests, delay):
        seen.update(host=host, max_requests=max_requests, delay=delay)
        return FakeClient({})
    monkeypatch.setattr(probe, 'Client', factory)
    probe.probe()
    assert seen == {'host': 'www.consumerfinance.gov', 'max_requests': 1, 'delay': 2.0}


def test_cli_keeps_existing_evidence_and_reports_failure(tmp_path, monkeypatch):
    old = tmp_path / 'prior.json'
    old.write_text('{"preserved": true}\n')
    result = {'error': 'access_or_rate_denial', 'response_status_summary': {'403': 1},
              'narrative_availability': 'NOT_ASSESSED'}
    monkeypatch.setattr(probe, 'probe', lambda: result)
    assert probe.main(['--output', str(tmp_path)]) == 1
    assert old.read_text() == '{"preserved": true}\n'
    outputs = list(tmp_path.glob('cfpb_access_*.json'))
    assert len(outputs) == 1 and json.loads(outputs[0].read_text()) == result

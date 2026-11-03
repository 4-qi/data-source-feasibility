"""Transport proof with injected synthetic sessions only; no network escapes."""
from dataclasses import replace

import pytest
from requests.exceptions import Timeout

from feasibility.apple_ingestion.contracts import IngestionConfig
from feasibility.apple_ingestion.transport import BoundedTransport, PILOT_APPLICATION_IDS

APP = '572688855'


class Clock:
    def __init__(self):
        self.now = 0.0
        self.sleeps = []
    def __call__(self):
        return self.now
    def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.now += seconds


class Response:
    def __init__(self, status=200, chunks=(b'synthetic body',), clock=None):
        self.status_code, self.chunks, self.clock = status, chunks, clock
        self.closed, self.iterated = False, False
    def __enter__(self):
        return self
    def __exit__(self, *args):
        self.closed = True
    def iter_content(self, chunk_size):
        assert chunk_size == 16384
        self.iterated = True
        for chunk in self.chunks:
            if self.clock:
                self.clock.now += 1
            if isinstance(chunk, Exception):
                raise chunk
            yield chunk


class Session:
    def __init__(self, responses, clock=None):
        self.responses, self.clock, self.calls = list(responses), clock, []
        self.trust_env, self.auth, self.cert = True, ('PRIVATE', 'PRIVATE'), 'PRIVATE'
        self.proxies, self.params = {'https': 'PRIVATE'}, {'api_key': 'PRIVATE'}
        self.headers = {'Authorization': 'PRIVATE', 'Cookie': 'PRIVATE', 'user-agent': 'PRIVATE', 'X-Api-Key': 'PRIVATE'}
        self.cookies = {'secret': 'PRIVATE'}
        self.hooks = {'response': ['PRIVATE']}
    def get(self, url, **kwargs):
        assert not self.cookies and self.trust_env is False
        assert self.auth is self.cert is None and self.proxies == self.params == {}
        assert self.hooks == {'response': []} and self.verify is True
        assert 'PRIVATE' not in repr(self.headers)
        self.calls.append((url, kwargs, self.clock() if self.clock else None, dict(self.headers)))
        self.cookies['received'] = 'PRIVATE'
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def transport(responses, clock=None):
    clock = clock or Clock()
    session = Session(responses, clock)
    return BoundedTransport(session, clock=clock, sleep=clock.sleep), session, clock


def test_explicit_session_required_and_construction_is_idle():
    with pytest.raises(TypeError):
        BoundedTransport()
    with pytest.raises(ValueError, match='EXPLICIT_SESSION_REQUIRED'):
        BoundedTransport(None)
    value, session, _ = transport([])
    assert session.calls == []


def test_exact_url_headers_safe_request_options_and_secret_free_repr():
    response = Response(chunks=(b'PRIVATE title body',))
    value, session, _ = transport([response])
    result = value.fetch(APP, 2, 'json', IngestionConfig())
    assert result.status_code == 200 and result.body == b'PRIVATE title body'
    assert result.response_bytes == 18 and result.error_code is None
    assert 'PRIVATE' not in repr(result)
    url, options, _, headers = session.calls[0]
    assert url == 'https://itunes.apple.com/us/rss/customerreviews/page=2/id=572688855/sortby=mostrecent/json'
    assert options == dict(allow_redirects=False, stream=True, timeout=(10.0, 25.0))
    assert headers['User-Agent'].startswith('DataSourceFeasibility/')
    assert headers['Accept'] == 'application/json'
    assert response.closed and session.cookies == {}


def test_spacing_is_global_across_applications_and_formats():
    value, session, clock = transport([Response(), Response(), Response()])
    for app, format in ((APP, 'json'), ('1212616790', 'xml'), ('529379082', 'json')):
        assert value.fetch(app, 1, format, IngestionConfig()).error_code is None
    assert [call[2] for call in session.calls] == [0, 2, 4]
    assert clock.sleeps == [2, 2]
    assert session.calls[1][3]['Accept'] == 'application/atom+xml, application/xml'


@pytest.mark.parametrize('status,code', [(401, 'HTTP_DENIED'), (403, 'HTTP_DENIED'), (429, 'HTTP_RATE_LIMIT'),
                                        (301, 'HTTP_NON_200'), (302, 'HTTP_NON_200'), (500, 'HTTP_NON_200')])
def test_denials_redirects_and_failures_have_no_body_retry_or_fallback(status, code):
    response = Response(status, (b'PRIVATE failure body',))
    value, session, _ = transport([response])
    result = value.fetch(APP, 1, 'json', replace(IngestionConfig(), retry_count=3))
    assert (result.status_code, result.body, result.response_bytes, result.error_code) == (status, b'', 0, code)
    assert len(session.calls) == 1 and not response.iterated and response.closed


def test_streaming_limit_counts_bytes_and_discards_the_partial_body():
    value, _, _ = transport([Response(chunks=(b'A' * 2_000_000, b'Z'))])
    result = value.fetch(APP, 1, 'json', IngestionConfig())
    assert (result.body, result.response_bytes, result.error_code) == (b'', 2_000_001, 'BODY_LIMIT')
    value, _, _ = transport([Response(chunks=(b'A' * 2_000_000,))])
    assert len(value.fetch(APP, 1, 'json', IngestionConfig()).body) == 2_000_000


@pytest.mark.parametrize('failure,code', [(Timeout('PRIVATE'), 'TRANSPORT_TIMEOUT'),
                                       (RuntimeError('PRIVATE'), 'TRANSPORT_ERROR')])
def test_safe_exception_codes_without_raw_exception_or_partial_body(failure, code):
    for response in (failure, Response(chunks=(b'PRIVATE', failure))):
        value, session, _ = transport([response])
        result = value.fetch(APP, 1, 'json', IngestionConfig())
        assert result.error_code == code and result.body == b''
        assert 'PRIVATE' not in repr(result) and len(session.calls) == 1


def test_deadline_before_request_during_spacing_and_during_stream():
    value, session, clock = transport([Response(), Response()])
    assert value.fetch(APP, 1, 'json', IngestionConfig(), deadline=0).error_code == 'TARGET_DEADLINE'
    assert not session.calls
    assert value.fetch(APP, 1, 'json', IngestionConfig(), deadline=10).error_code is None
    assert value.fetch(APP, 2, 'json', IngestionConfig(), deadline=1).error_code == 'TARGET_DEADLINE'
    assert len(session.calls) == 1
    response = Response(chunks=(b'PRIVATE', b'tail'), clock=clock)
    value, session, _ = transport([response], clock)
    result = value.fetch(APP, 1, 'json', IngestionConfig(), deadline=2)
    assert result.error_code == 'TARGET_DEADLINE' and result.body == b''
    assert response.closed


@pytest.mark.parametrize('app,page,format', [('../../PRIVATE', 1, 'json'), ('572688855?x=y', 1, 'json'),
                                           ('１２３', 1, 'json'), ('123', 1, 'json'), (572688855, 1, 'json'),
                                           (APP, True, 'json'), (APP, 0, 'json'), (APP, 6, 'json'), (APP, 1, 'yaml')])
def test_unsafe_urls_pages_formats_and_out_of_frame_apps_never_reach_session(app, page, format):
    value, session, _ = transport([])
    result = value.fetch(app, page, format, IngestionConfig())
    assert result.error_code == 'INVALID_REQUEST' and not session.calls


def test_real_requests_adapter_retry_is_disabled_without_any_request(monkeypatch):
    import requests
    session = requests.Session()  # Explicit injection; get is replaced before use.
    session.mount('https://', requests.adapters.HTTPAdapter(max_retries=7))
    calls = []
    monkeypatch.setattr(session, 'get', lambda *a, **kw: calls.append((a, kw)) or Response())
    try:
        result = BoundedTransport(session).fetch(APP, 1, 'json', IngestionConfig())
        assert result.error_code is None and len(calls) == 1
        assert session.get_adapter('https://itunes.apple.com').max_retries.total == 0
    finally:
        session.close()


def test_transport_frame_equals_existing_manifest():
    from pathlib import Path
    from feasibility.apple_ingestion.seed import load_seed_manifest
    frame = load_seed_manifest(Path(__file__).resolve().parents[1] / 'results/mainstream/app_sample_manifest.json')
    assert {record.source_application_id for record in frame} == PILOT_APPLICATION_IDS

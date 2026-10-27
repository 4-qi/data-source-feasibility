import json
import pytest
import requests
from feasibility.http import Client, StopCollection


class Response:
    def __init__(self, status=200, data=None, headers=None, content=None):
        self.status_code = status
        self.headers = headers or {}
        self.body = content if content is not None else json.dumps(data).encode()
    def __enter__(self): return self
    def __exit__(self, *args): pass
    def iter_content(self, size): yield self.body


class Session:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.headers = {}
        self.cookies = requests.cookies.RequestsCookieJar()
        self.calls = []
    def get(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        r = next(self.responses)
        if isinstance(r, Exception): raise r
        return r


@pytest.mark.parametrize('status', [401, 403, 429])
def test_denial_stops_no_retry(status):
    s = Session([Response(status=status, headers={'Retry-After': '30'})])
    c = Client('api.github.com', session=s, delay=0)
    with pytest.raises(StopCollection, match='access_or_rate_denial'):c.get('https://api.github.com/test')
    with pytest.raises(StopCollection, match='source_stopped'):c.get('https://api.github.com/test')
    assert len(s.calls) == 1 and c.events[0]['headers']['retry-after'] == '30'


def test_zero_remaining_stops_after_retaining_response():
    c = Client('api.github.com', session=Session([Response(data=[], headers={'X-RateLimit-Remaining': '0'})]), delay=0)
    assert c.get('https://api.github.com/test') == []
    with pytest.raises(StopCollection, match='source_stopped'):c.get('https://api.github.com/test')


@pytest.mark.parametrize('response,code', [(Response(content=b'not json'),'malformed_json'),
    (Response(status=302),'http_error'), (Response(content=b'x'*2_000_001),'response_size_limit'),
    (requests.exceptions.Timeout(),'transport_error')])
def test_safe_errors(response,code):
    c = Client('api.github.com', session=Session([response]), delay=0)
    with pytest.raises(StopCollection, match=code):c.get('https://api.github.com/test')
    assert c.events[0]['error'] == code


def test_host_and_budget():
    c = Client('api.github.com', max_requests=1, session=Session([Response(data=[])]), delay=0)
    with pytest.raises(StopCollection, match='disallowed_url'):c.get('https://evil.example/')
    assert not c.events
    c.get('https://api.github.com/test')
    with pytest.raises(StopCollection, match='request_budget'):c.get('https://api.github.com/test')


def test_cursor_redacted_and_no_auth_redirects():
    s = Session([Response(data={})]);c = Client('api.github.com', session=s)
    c.get('https://api.github.com/test', params={'input_json': json.dumps({'cursor':'opaque+/='})})
    assert c.events[0]['params']['input_json']['cursor'].startswith('sha256:')
    assert not s.calls[0][1]['allow_redirects']
    assert s.trust_env is False

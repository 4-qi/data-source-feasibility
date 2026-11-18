"""Synthetic probe proof; no Apple requests or persistent deployment writes."""
import json

import pytest
from sqlalchemy import text

from feasibility.apple_ingestion import pagination_probe as probe
from feasibility.apple_ingestion.pagination_probe import ProbeError, prefix_validity, run_probe
from test_apple_ingestion_transport import Clock, Response, Session


def feed(ids):
    return json.dumps({"feed": {"entry": [
        {"id": {"label": str(i)}, "content": {"label": "PRIVATE_SYNTHETIC_FULL_TEXT"},
         "title": {"label": "PRIVATE_TITLE"}, "im:rating": {"label": "4"},
         "updated": {"label": "2026-11-12T00:00:00Z"}} for i in ids
    ]}}).encode()


def atom(ids):
    return ('<feed xmlns="http://www.w3.org/2005/Atom" xmlns:im="http://itunes.apple.com/rss">'
            + ''.join(f'<entry><id>{i}</id><content>PRIVATE_BODY</content><im:rating>4</im:rating></entry>'
                      for i in ids) + '</feed>').encode()


def execute(tmp_path, bodies, *, budget=14, preflight=None):
    directory = tmp_path / 'evidence'
    directory.mkdir(mode=0o700)
    clock = Clock()
    responses = [Response(chunks=(body,)) if isinstance(body, bytes) else body for body in bodies]
    session = Session(responses, clock)
    result = run_probe(session, directory, max_requests=budget, clock=clock,
                       sleep=clock.sleep, preflight=preflight)
    return result, session, directory, clock


def test_deep_pages_new_ids_spacing_and_single_use(tmp_path):
    result, session, directory, clock = execute(tmp_path, [feed([i]) for i in probe.PAGES])
    assert result['status'] == 'completed' and result['requests'] == 7
    assert result['valid_pages'] == list(probe.PAGES)
    assert [row['novel_ids'] for row in result['pages']] == [1] * 7
    assert [call[2] for call in session.calls] == list(range(0, 14, 2))
    assert all(f'/page={page}/id=570060128/sortby=mostrecent/json' in call[0]
               for call, page in zip(session.calls, probe.PAGES))
    assert all('PRIVATE' not in p.read_text() for p in directory.iterdir() if p.is_file())
    with pytest.raises(ProbeError, match='PROBE_ALREADY_RESERVED'):
        run_probe(session, directory, clock=clock, sleep=clock.sleep)
    assert len(session.calls) == 7


def test_repeated_deep_page_stops(tmp_path):
    result, session, *_ = execute(tmp_path, [feed([1]), feed([5]), feed([5]), feed([7])])
    assert result['requests'] == 3 and result['stop_reason'] == 'duplicate_only_deep_page'
    assert result['pages'][-1]['repeated_page_ids']
    assert result['pages'][-1]['novel_ids'] == 0


def test_duplicate_within_page_and_conflicting_previous_id(tmp_path):
    result, *_ = execute(tmp_path, [feed([1, 1]), feed([5]), feed([6]), feed([7]), feed([8]), feed([9]), feed([10])])
    assert result['pages'][0]['same_page_duplicate_occurrences'] == 1
    changed = feed([1]).replace(b'PRIVATE_SYNTHETIC_FULL_TEXT', b'OTHER_PRIVATE')
    other = tmp_path / 'other'
    other.mkdir()
    result, *_ = execute(other, [feed([1]), feed([5]), changed])
    assert result['stop_reason'] == 'conflicting_occurrence'
    assert result['pages'][-1]['invalidated_pages'] == [1]


@pytest.mark.parametrize(('body', 'expected'), [(b'{}', 'parse_error'), (b'not JSON', 'parse_error')])
def test_malformed_has_no_fallback(tmp_path, body, expected):
    result, session, *_ = execute(tmp_path, [body, feed([2])])
    assert result['requests'] == 1 and result['stop_reason'] == expected


def test_empty_selected_atom_stops(tmp_path):
    result, *_ = execute(tmp_path, [b'{"feed":{}}', atom([])])
    assert result['requests'] == 2 and result['stop_reason'] == 'empty_page'


def test_all_json_empty_then_atom_uses_exactly_fourteen_requests(tmp_path):
    bodies = [body for p in probe.PAGES for body in (b'{"feed":{}}', atom([p]))]
    result, session, *_ = execute(tmp_path, bodies)
    assert result['status'] == 'completed' and len(session.calls) == 14
    assert [row['format'] for row in result['pages']] == ['xml'] * 7


def test_budget_exhausted_before_fallback(tmp_path):
    result, session, *_ = execute(tmp_path, [feed([1]), b'{"feed":{}}', atom([5])], budget=2)
    assert result['stop_reason'] == 'request_budget' and result['requests'] == 2
    assert result['valid_pages'] == [1] and len(session.calls) == 2


def test_nested_atom_diagnostics_safe(tmp_path):
    xml = (b'<feed xmlns="http://www.w3.org/2005/Atom"><entry><content type="xhtml">'
           b'<div xmlns="http://www.w3.org/1999/xhtml">PRIVATE</div></content></entry></feed>')
    result, *_ = execute(tmp_path, [b'{"feed":{}}', xml])
    assert result['stop_reason'] == 'parse_error'
    assert result['attempts'][-1]['diagnostic'] == {
        'category': 'unsupported_xhtml', 'field': 'content', 'entry_index': 1}
    assert 'PRIVATE' not in json.dumps(result)


@pytest.mark.parametrize('status', [403, 429, 302, 500])
def test_http_failure_stops_without_fallback(tmp_path, status):
    result, session, *_ = execute(tmp_path, [Response(status=status), feed([2])])
    assert result['requests'] == len(session.calls) == 1
    assert result['status'] == 'stopped'


def test_persistence_failure_retains_intent_no_replay(tmp_path, monkeypatch):
    original = probe.Evidence.save

    def fail_completion(self, value, **kwargs):
        if value['attempts'] and value['attempts'][-1]['status'] != 'intent':
            raise ProbeError('EVIDENCE_UNAVAILABLE')
        return original(self, value, **kwargs)

    monkeypatch.setattr(probe.Evidence, 'save', fail_completion)
    directory = tmp_path / 'evidence'
    directory.mkdir(mode=0o700)
    clock = Clock()
    session = Session([Response(chunks=(feed([1]),))], clock)
    with pytest.raises(ProbeError, match='EVIDENCE_UNAVAILABLE'):
        run_probe(session, directory, clock=clock, sleep=clock.sleep)
    assert len(session.calls) == 1
    saved = json.loads((directory / 'probe.json').read_text())
    assert saved['attempts'][-1]['status'] == 'intent'
    monkeypatch.setattr(probe.Evidence, 'save', original)
    with pytest.raises(ProbeError, match='PROBE_ALREADY_RESERVED'):
        run_probe(session, directory, clock=clock, sleep=clock.sleep)
    assert len(session.calls) == 1


def test_five_page_prefix_survives_tail_parse_failure():
    pages = [{'page': p, 'status': 'valid'} for p in range(1, 6)]
    pages.append({'page': 6, 'status': 'incomplete'})
    assert prefix_validity(pages, 5)
    assert not prefix_validity(pages, 10)
    pages[-1]['invalidated_pages'] = [2]
    assert not prefix_validity(pages, 5)


def test_probe_is_database_read_only_and_preflight_failure_sends_nothing(tmp_path, apple_database):
    before = {}
    with apple_database.connect() as c:
        before = {t: c.scalar(text('SELECT count(*) FROM ' + t)) for t in ('collection_run','fetch_attempt','review')}
    def preflight():
        with apple_database.connect() as c:
            c.exec_driver_sql('SET TRANSACTION READ ONLY')
            assert c.scalar(text('SELECT current_database()')).startswith('apple_phase_a_fixture_')
    result, *_ = execute(tmp_path, [feed([p]) for p in probe.PAGES], preflight=preflight)
    assert result['status'] == 'completed'
    with apple_database.connect() as c:
        assert before == {t: c.scalar(text('SELECT count(*) FROM ' + t)) for t in before}
    other = tmp_path / 'other'
    other.mkdir(mode=0o700)
    session = Session([], Clock())
    def broken():
        raise ProbeError('DATABASE_ISOLATION_FAILED')
    with pytest.raises(ProbeError, match='DATABASE_ISOLATION_FAILED'):
        run_probe(session, other, preflight=broken)
    assert not session.calls and not (other / 'probe.json').exists()

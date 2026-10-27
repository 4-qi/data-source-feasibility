"""All fixtures are synthetic; these tests perform zero network calls."""
import pytest
from feasibility.collectors import steam, github_issues as gh, hackernews as hn
from feasibility.http import StopCollection
from feasibility.model import Collected, Record
from feasibility.reporting import summarize, compare
from feasibility.quality import clean_text, screen, language_flag


class FakeClient:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.calls = []
    def get(self, url, params=None, headers=None):
        self.calls.append((url, params))
        item = next(self.responses)
        if isinstance(item, Exception):
            raise item
        return item


def review(i, text='I enjoyed the story and the controls.'):
    return {'recommendationid': i, 'review': text, 'timestamp_created': 1, 'timestamp_updated': 2,
            'voted_up': False, 'language': 'english', 'author': {'steamid': 'DO_NOT_RETAIN', 'playtime_at_review': 60}}


def test_steam_cursor_order_and_normalization():
    c = FakeClient([{'reviews': [review(1)], 'cursor': 'a+/='}, {'reviews': [review(2)], 'cursor': 'b'},
                    {'reviews': [review(1)], 'cursor': 'c'}])
    out = steam.collect(c, max_records=4, appids=(620,), page_size=1)
    import json
    assert json.loads(c.calls[1][1]['input_json'])['cursor'] == 'a+/='
    assert json.loads(c.calls[2][1]['input_json'])['filter'] == 2
    assert out.records[0].metadata['voted_up'] is False
    assert 'DO_NOT_RETAIN' not in repr(out.records)
    assert out.observations[-1]['created_before_updated_count'] == 1


def test_steam_empty_terminates_each_order():
    c = FakeClient([{'reviews': [], 'cursor': 'x'}, {'reviews': []}])
    assert not steam.collect(c, appids=(620,)).records
    assert len(c.calls) == 2


def test_steam_missing_optional_and_repeated_cursor():
    c = FakeClient([{'reviews': [{'recommendationid': '1'}], 'cursor': '*'}, {'reviews': []}])
    out = steam.collect(c, appids=(620,))
    assert out.records[0].text is None
    assert len(c.calls) == 2


def test_steam_malformed_schema():
    with pytest.raises(StopCollection, match='unexpected_steam_schema'):
        steam.collect(FakeClient([{'reviews': {}}]))


def test_steam_rejects_oversized_page():
    with pytest.raises(StopCollection, match='exceeded_requested'):
        steam.collect(FakeClient([{'reviews': [review(1), review(2)]}]), page_size=1)


def test_github_filters_pr_and_preserves_comment_parent():
    issue = {'id': 2, 'number': 42, 'title': 'Problem', 'body': 'My editor crashes after opening a file.',
             'comments': 2, 'user': {'login': 'DO_NOT_RETAIN', 'type': 'User'}}
    c = FakeClient([[{'id': 1, 'pull_request': {}}, issue],
                    [{'id': 3, 'body': 'Please complete this issue template.', 'user': {'type': 'Bot'}}]])
    out = gh.collect(c, page_size=10)
    assert out.excluded['pull_requests'] == 1
    assert len(out.records) == 2
    assert out.records[1].parent == out.records[0].key
    assert out.records[1].author_type == 'Bot'
    assert 'DO_NOT_RETAIN' not in repr(out)


def test_github_does_not_follow_arbitrary_comments_url():
    c = FakeClient([[{'id': 2, 'number': 42, 'comments': 1, 'comments_url': 'https://evil.example/'}], []])
    gh.collect(c)
    assert c.calls[1][0].startswith('https://api.github.com/repos/')


def test_github_empty_and_missing_fields():
    assert gh.collect(FakeClient([[]])).records == []
    r = gh.normalize({'id': 1}, 'owner/repo')
    assert r.created is None and not r.text


def test_github_rejects_bad_repo():
    with pytest.raises(ValueError):
        gh.collect(FakeClient([]), repo='owner/repo/../../../')


def test_github_partial_preserved_on_deny():
    c = FakeClient([[{'id': 2, 'number': 42, 'comments': 1}], StopCollection('access_or_rate_denial')])
    with pytest.raises(StopCollection):
        gh.collect(c)
    assert len(c.collected.records) == 1


def test_hn_deleted_and_direct_parent():
    c = FakeClient([[1], {'id': 1, 'type': 'story', 'text': '<p>Which editor do you use?</p>', 'kids': [2, 3, 4]},
                    {'id': 2, 'type': 'comment', 'parent': 1, 'text': 'My editor works very well.'}, {'deleted': True}])
    out = hn.collect(c)
    assert len(out.records) == 2 and out.records[1].parent == '1'
    assert out.excluded['deleted_or_dead_or_null'] == 1
    assert out.repeat_config == {'story_ids': [1]}
    assert len(c.calls) == 4  # No recursive traversal / no third child.


def test_hn_invalid_parent():
    c = FakeClient([{'id': 1, 'type': 'story', 'kids': [2]}, {'id': 2, 'type': 'comment', 'parent': 9}])
    with pytest.raises(StopCollection, match='unexpected_hn_comment_schema'):
        hn.collect(c, story_ids=[1])


def test_quality_is_eligibility_not_sentiment():
    assert clean_text('<p>Hello &amp; goodbye</p>') == 'Hello & goodbye'
    assert screen(None)['screen'] == 'missing_or_empty'
    assert screen('good')['screen'] == 'short_or_low_information'
    assert screen('I enjoyed the story and the controls.')['screen'] == 'eligible_for_manual_review'
    assert screen('This issue was automatically closed.', 'Bot')['screen'] == 'automated_message'
    assert language_flag('Esse jogo é muito bom', 'english')


def test_summary_dedup_missing_ids_and_privacy():
    from types import SimpleNamespace
    r = Record('steam', 'review', '1', 'I enjoyed the story and the controls.', created=1)
    client = SimpleNamespace(host='example', events=[], blocked=False)
    out = Collected(records=[r, r, Record('steam', 'review', None, None)])
    s = summarize('steam', {'max_records': 3}, out, client, '2026-10-20T00:00:00+00:00')
    assert s['duplicate_records'] == 1
    assert s['unique_records_with_id'] == 1
    assert s['records_without_id'] == 1
    assert s['usable_text_count'] == 1
    assert s['human_validated_opinion_count'] is None
    assert r.text not in str(s)


def test_repeatability_compares_only_present_ids():
    base = {'source': 'steam', 'run_id': 'a', 'started_at_utc': '2026-10-20T00:00:00+00:00',
            'record_metrics': [{'record_fingerprint': 'a'}, {'record_fingerprint': None}],
            'available_fields': {'review': 1}, 'response_status_summary': {'200': 1}}
    other = {**base, 'run_id': 'b', 'started_at_utc': '2026-10-20T00:00:16+00:00',
             'record_metrics': [{'record_fingerprint': 'a'}, {'record_fingerprint': 'b'}]}
    result = compare(base, other)
    assert result['overlapping_unique_ids'] == 1 and result['second_only'] == 1
    assert result['seconds_between_starts'] == 16

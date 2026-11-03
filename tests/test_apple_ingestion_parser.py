"""Synthetic full-page parsing: no network, source evidence, authors or logs."""
from dataclasses import FrozenInstanceError
from datetime import datetime, timezone
import json
import traceback
from xml.sax.saxutils import escape

import pytest

from feasibility.apple_ingestion.contracts import FeedFormat, ReasonCode
from feasibility.apple_ingestion.normalizer import canonical_fields, fingerprint
from feasibility.apple_ingestion.parser import FeedParseError, PARSER_VERSION, parse_feed

ATOM = 'http://www.w3.org/2005/Atom'
IM = 'http://itunes.apple.com/rss'


def entry(**changes):
    values = dict(id=" opaque:0001 /id ", title="标题 &amp; 😀", content="Full e\u0301\r\nbody  &amp; <b>literal</b>",
                  updated="2026-11-03T12:30:00-08:00", **{"im:rating": "4", "im:version": "1.2"})
    values.update(changes)
    return {key: {"label": value} for key, value in values.items()}


def json_body(entries):
    return json.dumps({"feed": {"entry": entries}}, ensure_ascii=False).encode()


def xml_body(entries):
    result = f'<feed xmlns="{ATOM}" xmlns:im="{IM}">'
    for values in entries:
        result += '<entry>'
        for key, value in values.items():
            result += f'<{key}>' + escape(value['label']) + f'</{key}>'
        result += '</entry>'
    return (result + '</feed>').encode()


def failed(body, format='json', code=ReasonCode.ENTRY_SCHEMA):
    with pytest.raises(FeedParseError) as caught:
        parse_feed(body, format)
    assert caught.value.code is code
    assert str(caught.value) == code.value
    assert 'PRIVATE' not in ''.join(traceback.format_exception(caught.value))


def test_complete_json_atom_equivalence_and_decode_exactly_once():
    item = entry()
    js = parse_feed(json_body([item]), FeedFormat.JSON)
    xml = parse_feed(xml_body([item]), 'xml')
    assert js.entry_count == xml.entry_count == 1
    left, right = js.records[0], xml.records[0]
    assert left.source_review_id == right.source_review_id == " opaque:0001 /id "
    assert left.title == right.title == "标题 &amp; 😀"
    assert left.body == "Full e\u0301\r\nbody  &amp; <b>literal</b>"
    assert right.body == left.body.replace('\r\n', '\n')  # XML-standard line-ending decoding
    assert canonical_fields(left) == canonical_fields(right)
    assert fingerprint(left) == fingerprint(right)
    assert left.source_updated_at.astimezone(timezone.utc) == datetime(2026, 11, 3, 20, 30, tzinfo=timezone.utc)
    assert js.codes == xml.codes == ()
    assert PARSER_VERSION == 'apple-feed-v1'
    with pytest.raises(FrozenInstanceError):
        js.entry_count = 2


def test_single_json_entry_and_duplicates_preserve_order_and_full_tail():
    first = entry(content='正文😀\n' * 30_000 + 'END')
    assert parse_feed(json_body(first), 'json').records[0].body.endswith('END')
    entries = [first, entry(id='different'), entry(content='changed same ID')]
    for body, format in ((json_body(entries), 'json'), (xml_body(entries), 'xml')):
        page = parse_feed(body, format)
        assert page.entry_count == 3
        assert [record.source_review_id for record in page.records] == [first['id']['label'], 'different', first['id']['label']]
        assert page.records[0].body == first['content']['label']
        assert page.records[2].body == 'changed same ID'


def test_null_and_empty_optional_values_stay_distinct():
    item = entry(title='')
    for key in ('updated', 'im:version'):
        del item[key]
    for body, format in ((json_body(item), 'json'), (xml_body([item]), 'xml')):
        record = parse_feed(body, format).records[0]
        assert record.title == ''
        assert record.application_version is record.source_updated_at is None
    del item['title']
    assert parse_feed(json_body(item), 'json').records[0].title is None


@pytest.mark.parametrize('body,format,absent,codes', [
    (b'{"feed":{}}', 'json', True, (ReasonCode.JSON_ENTRY_ABSENT, ReasonCode.EMPTY_PAGE)),
    (b'{"feed":{"entry":[]}}', 'json', False, (ReasonCode.EMPTY_PAGE,)),
    (f'<feed xmlns="{ATOM}"/>'.encode(), 'xml', False, (ReasonCode.EMPTY_PAGE,)),
])
def test_missing_and_empty_are_successful_distinct_safe_states(body, format, absent, codes):
    page = parse_feed(body, format)
    assert page.records == () and page.entry_count == 0
    assert page.entry_absent is absent and page.codes == codes


def test_only_recognizable_application_catalog_is_ignored():
    catalog = {'im:name': {'label': 'Synthetic App'},
               'im:contentType': {'attributes': {'term': 'Application'}}}
    assert parse_feed(json_body([catalog, entry()]), 'json').entry_count == 1
    assert parse_feed(json_body([catalog]), 'json').codes == (ReasonCode.EMPTY_PAGE,)
    xml = (f'<feed xmlns="{ATOM}" xmlns:im="{IM}"><entry><im:name>Synthetic App</im:name>'
           '<im:contentType term="Application"/></entry></feed>').encode()
    assert parse_feed(xml, 'xml').entry_count == 0
    # A review-shaped record cannot bypass missing-rating validation with catalog markers.
    review = entry()
    del review['im:rating']
    failed(json_body([catalog, review | catalog]))
    failed(json_body([{'im:name': {'label': 'not enough to identify a catalog'}}]))
    failed(json_body([{}]))


@pytest.mark.parametrize('key', ['id', 'content', 'im:rating'])
def test_missing_required_candidate_fields_fail_entire_page(key):
    invalid = entry(content='PRIVATE invalid record')
    del invalid[key]
    failed(json_body([entry(), invalid]))
    failed(xml_body([entry(), invalid]), 'xml')


@pytest.mark.parametrize('key,value', [
    ('id', ''), ('id', ' \t\n'), ('id', 12345), ('id', 'PRIVATE\x00id'),
    ('content', None), ('content', 5), ('content', 'PRIVATE\ud800'),
    ('title', []), ('im:version', 1), ('im:rating', '0'), ('im:rating', '6'),
    ('im:rating', '3.0'), ('im:rating', ' 3'), ('im:rating', '٣'),
    ('im:rating', 3), ('im:rating', True),
])
def test_invalid_values_and_types_reject_the_page_without_raw_errors(key, value):
    # ASCII escaping permits surrogate test bytes without a Python encode failure.
    invalid = entry(**{key: value})
    payload = json.dumps({'feed': {'entry': [entry(), invalid]}}).encode()
    failed(payload)


@pytest.mark.parametrize('timestamp', ['', '2026-11-03', 'PRIVATE invalid timestamp',
                                      '2026-11-03T12:30:00', '2026-02-30T12:30:00Z',
                                      '2026-11-03T12:30:00+24:00', '2026-11-03T12:30:00+01:60',
                                      '2026-11-03T12:30:00.1234567Z', '2026-11-03 12:30:00Z'])
def test_malformed_optional_timestamp_fails_whole_page(timestamp):
    item = entry(updated=timestamp)
    failed(json_body([entry(), item]), code=ReasonCode.INVALID_TIMESTAMP)
    failed(xml_body([entry(), item]), 'xml', ReasonCode.INVALID_TIMESTAMP)


@pytest.mark.parametrize('payload', [b'PRIVATE invalid json', b'[]', b'{"feed":null}', b'{}',
                                     b'{"feed":{"entry":null}}', b'{"feed":{"entry":"PRIVATE"}}',
                                     b'{"feed":{},"feed":{"entry":[]}}', b'{"feed":{"bad":NaN}}',
                                     b'{"feed":{"bad":Infinity}}', b'\xff'])
def test_invalid_json_envelopes_cannot_masquerade_as_empty(payload):
    failed(payload, code=ReasonCode.FEED_SCHEMA)


@pytest.mark.parametrize('entry_value', [None, 'PRIVATE', 3, [], {'id': 'PRIVATE'}])
def test_bad_entry_objects_and_wrappers_fail(entry_value):
    failed(json_body([entry_value]))


@pytest.mark.parametrize('xml', [
    '<feed/>', f'<rss xmlns="{ATOM}"/>', f'<feed xmlns="{ATOM}"><entry xmlns=""/></feed>',
    f'<!DOCTYPE feed><feed xmlns="{ATOM}"/>',
    f'<!DOCTYPE feed [<!ENTITY x "PRIVATE">]><feed xmlns="{ATOM}">&x;</feed>',
    f'<!DOCTYPE feed SYSTEM "file:///PRIVATE"><feed xmlns="{ATOM}"/>',
    f'<feed xmlns="{ATOM}"><entry>',
])
def test_invalid_xml_namespaces_malformed_and_dtds_are_safe_failures(xml):
    failed(xml.encode(), 'xml', ReasonCode.FEED_SCHEMA)
    failed(xml.encode('utf-16'), 'xml', ReasonCode.FEED_SCHEMA)


@pytest.mark.parametrize('content', [
    '<content>start<b xmlns="http://www.w3.org/1999/xhtml">PRIVATE tail</b></content>',
    '<content type="xhtml"><div xmlns="http://www.w3.org/1999/xhtml">PRIVATE</div></content>',
    '<content type="xhtml"/>', '<content src="https://PRIVATE/"/>',
    '<content type="application/octet-stream">PRIVATE</content>',
])
def test_nested_or_external_xml_content_is_rejected_never_truncated(content):
    xml = (f'<feed xmlns="{ATOM}" xmlns:im="{IM}"><entry><id>opaque</id>'
           f'<im:rating>3</im:rating>{content}</entry></feed>')
    failed(xml.encode(), 'xml')


def test_duplicate_xml_fields_and_duplicate_json_members_are_rejected():
    xml = (f'<feed xmlns="{ATOM}" xmlns:im="{IM}"><entry><id>first</id><id>second</id>'
           '<im:rating>3</im:rating><content>PRIVATE</content></entry></feed>')
    failed(xml.encode(), 'xml')
    failed(b'{"feed":{"entry":{"id":{"label":"one","label":"PRIVATE"}}}}', code=ReasonCode.FEED_SCHEMA)


def test_html_text_and_literal_escaped_entities_are_not_repeatedly_unescaped():
    xml = (f'<feed xmlns="{ATOM}" xmlns:im="{IM}"><entry><id>opaque</id><im:rating>3</im:rating>'
           '<title type="html">&lt;b&gt;title&lt;/b&gt;</title>'
           '<content type="html">&amp;lt;b&amp;gt; &amp;amp; PRIVATE</content></entry></feed>')
    record = parse_feed(xml.encode(), 'xml').records[0]
    assert record.title == '<b>title</b>'
    assert record.body == '&lt;b&gt; &amp; PRIVATE'


@pytest.mark.parametrize('body,format', [('PRIVATE', 'json'), (bytearray(b'{}'), 'json'), (b'{}', 'yaml'), (b'{}', {})])
def test_input_contract_errors_are_safe(body, format):
    failed(body, format, ReasonCode.FEED_SCHEMA)

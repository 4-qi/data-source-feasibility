"""Synthetic compatibility fixtures, never a replay of raw historical Apple text.

Historical sanitized evidence is used only to verify its classification. Pure
legacy decode_feed replays field mappings, not old lossy normalization or live
requests. Do not import probes/mobile_quality.py: it initializes a Session.
"""
from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import traceback
from xml.sax.saxutils import escape

import pytest

from feasibility.apple_validation import decode_feed as historical_field_adapter
from feasibility.apple_ingestion.contracts import FeedFormat, ReasonCode
from feasibility.apple_ingestion.normalizer import canonical_fields, fingerprint
from feasibility.apple_ingestion.parser import FeedParseError, parse_feed

ROOT = Path(__file__).resolve().parents[1]
ATOM = 'http://www.w3.org/2005/Atom'
IM = 'http://itunes.apple.com/rss'
XHTML = 'http://www.w3.org/1999/xhtml'


@dataclass(frozen=True)
class SyntheticFixture:
    body: bytes
    format: FeedFormat
    evidence_kind: str = 'synthetic'
    provenance: str = 'invented content; mapping from historical adapter code, not saved feed bytes'


def json_fixture(**changes):
    values = dict(id=' opaque:0000001 /keep-spaces ', title='Synthetic title 😀 &amp;',
        content='Synthetic full e\u0301\r\nbody  &amp; <b>literal</b>\n' + '完整正文 ' * 5000 + 'FULL_TAIL',
        updated='2026-11-03T04:30:00.123456-08:00', **{'im:rating': '3', 'im:version': ' 1.0 '})
    values.update(changes)
    fields = {key: {'label': value} for key, value in values.items()}
    fields['id']['attributes'] = {'im:id': 'untrusted-alternate-id'}
    fields['author'] = {'name': {'label': 'SYNTHETIC_AUTHOR_NOT_A_RECORD_FIELD'}}
    return SyntheticFixture(json.dumps({'feed': {'entry': fields}}, ensure_ascii=True).encode(), FeedFormat.JSON)


def atom_fixture(fields, *, type='text', prefix=False):
    entry = ''.join(f'<{key}{(" type=" + chr(34) + type + chr(34)) if key in {"content", "title"} else ""}>'
                    + escape(value['label']) + f'</{key}>' for key, value in fields.items()
                    if key != 'author')
    if prefix:
        for key in ('id', 'title', 'content', 'updated'):
            entry = entry.replace(f'<{key}', f'<a:{key}').replace(f'</{key}', f'</a:{key}')
        xml = f'<a:feed xmlns:a="{ATOM}" xmlns:im="{IM}"><a:entry>{entry}</a:entry></a:feed>'
    else:
        xml = f'<feed xmlns="{ATOM}" xmlns:im="{IM}"><entry>{entry}</entry></feed>'
    return SyntheticFixture(xml.encode(), FeedFormat.XML)


@pytest.mark.parametrize('text_type', ['text', 'html'])
@pytest.mark.parametrize('prefix', [False, True])
def test_synthetic_historical_json_atom_field_mapping_fulltext_and_comparison(text_type, prefix):
    js = json_fixture()
    raw_fields = json.loads(js.body)['feed']['entry']
    xml = atom_fixture(raw_fields, type=text_type, prefix=prefix)
    assert js.evidence_kind == xml.evidence_kind == 'synthetic'
    old_json = historical_field_adapter(js.body)['entry']
    old_xml = historical_field_adapter(xml.body, xml=True)['entry'][0]
    parsed_json = parse_feed(js.body, js.format).records[0]
    parsed_xml = parse_feed(xml.body, xml.format).records[0]
    for old, current in ((old_json, parsed_json), (old_xml, parsed_xml)):
        assert current.source_review_id == old['id']['label'] == ' opaque:0000001 /keep-spaces '
        assert current.title == old['title']['label']
        assert current.body == old['content']['label']
        assert current.rating == int(old['im:rating']['label']) == 3
        assert current.application_version == old['im:version']['label'] == ' 1.0 '
        assert current.body.endswith('FULL_TAIL') and len(current.body) > 20_000
        assert not hasattr(current, 'author')
    assert parsed_json.body.startswith('Synthetic full e\u0301\r\nbody  &amp; <b>literal</b>')
    assert parsed_xml.body == parsed_json.body.replace('\r\n', '\n')  # XML parser line-ending decoding
    assert canonical_fields(parsed_json) == canonical_fields(parsed_xml)
    assert canonical_fields(parsed_json)[-1] == '2026-11-03T12:30:00.123456Z'
    assert fingerprint(parsed_json) == fingerprint(parsed_xml)


@pytest.mark.parametrize('include_title,title', [(False, None), (True, '')])
def test_nullable_contract_is_missing_optional_field_not_permissive_null_wrapper(include_title, title):
    raw = json.loads(json_fixture().body)
    fields = raw['feed']['entry']
    fields.pop('updated')
    fields.pop('im:version')
    if include_title:
        fields['title']['label'] = title
    else:
        fields.pop('title')
    js = SyntheticFixture(json.dumps(raw).encode(), FeedFormat.JSON)
    xml = atom_fixture(fields)
    for fixture in (js, xml):
        record = parse_feed(fixture.body, fixture.format).records[0]
        assert record.title == title
        assert record.source_updated_at is record.application_version is None
    fields['title'] = {'label': None}
    with pytest.raises(FeedParseError) as caught:
        parse_feed(json.dumps(raw).encode(), FeedFormat.JSON)
    assert caught.value.code is ReasonCode.ENTRY_SCHEMA


@pytest.mark.parametrize('field', ['id', 'content', 'title', 'im:rating', 'im:version', 'updated'])
@pytest.mark.parametrize('invalid', [None, 3, False])
def test_present_json_labels_require_scalar_strings_without_coercion(field, invalid):
    raw = json.loads(json_fixture().body)
    raw['feed']['entry'][field] = {'label': invalid}
    with pytest.raises(FeedParseError) as caught:
        parse_feed(json.dumps(raw).encode(), 'json')
    assert caught.value.code is ReasonCode.ENTRY_SCHEMA


def test_atom_cdata_html_literal_is_decoded_once_without_becoming_nested_markup():
    xml = (f'<feed xmlns="{ATOM}" xmlns:im="{IM}"><entry><id>synthetic-id</id>'
        '<title type="html">&lt;b&gt;Synthetic title&lt;/b&gt;</title><im:rating>2</im:rating>'
        '<content type="html"><![CDATA[<p>synthetic &amp; literal</p>]]></content></entry></feed>')
    parsed = parse_feed(xml.encode(), 'xml').records[0]
    assert parsed.title == '<b>Synthetic title</b>'
    assert parsed.body == '<p>synthetic &amp; literal</p>'
    assert canonical_fields(parsed)[1] == parsed.body


@pytest.mark.parametrize('text', [
    '<content type="xhtml"><div xmlns="http://www.w3.org/1999/xhtml"><p>FIRST<br/>NEXT</p>TAIL<p>LAST</p></div></content>',
    '<title type="xhtml"><div xmlns="http://www.w3.org/1999/xhtml">TITLE<b>SUFFIX</b>TAIL</div></title>',
    '<content type="text">PREFIX<b xmlns="http://www.w3.org/1999/xhtml">SUFFIX</b>TAIL</content>',
    '<content type="html"><p>FIRST</p><p>LAST</p></content>',
])
def test_nested_candidate_is_rejected_whole_page_not_silently_truncated(text):
    xml = (f'<feed xmlns="{ATOM}" xmlns:im="{IM}">'
        '<entry><id>synthetic-valid</id><im:rating>3</im:rating><content>valid first record</content></entry>'
        f'<entry><id>synthetic-unsupported</id><im:rating>3</im:rating>{text}</entry></feed>')
    with pytest.raises(FeedParseError) as caught:
        parse_feed(xml.encode(), 'xml')
    assert caught.value.code is ReasonCode.ENTRY_SCHEMA
    formatted = ''.join(traceback.format_exception(caught.value))
    assert all(value not in formatted for value in ('PREFIX', 'SUFFIX', 'FIRST', 'LAST', 'synthetic-unsupported'))


def test_candidate_text_projection_requires_an_explicit_boundary_policy_not_itertext_join():
    # This is an illustration of the pending design choice, not an enabled parser.
    import xml.etree.ElementTree as ET
    root = ET.fromstring(f'<div xmlns="{XHTML}">START<p>FIRST<br/>NEXT</p>TAIL<p>LAST</p>END</div>')
    assert ''.join(root.itertext()) == 'STARTFIRSTNEXTTAILLASTEND'
    # Dropped br/paragraph boundaries would join separate words and manufacture
    # equivalence. No such projection or hash-contract change is enabled.


@pytest.mark.parametrize('filename', [
    'mainstream/apple_rss_access.json', 'mainstream/apple_xml_review_sample.json',
    'mainstream/apple_empty_feed_diagnostic.json', 'mainstream/apple_online_readiness.json',
    'mobile_quality/collection.json',
])
def test_saved_diagnostic_json_is_not_a_raw_feed_replay_fixture(filename):
    payload = (ROOT / 'results' / filename).read_bytes()
    metadata = json.loads(payload)
    assert 'feed' not in metadata  # report envelope, not Apple response envelope
    if 'raw_review_text_saved' in metadata:
        assert metadata['raw_review_text_saved'] is False
    if 'raw_content_saved' in metadata:
        assert metadata['raw_content_saved'] is False
    assert all(request.get('raw_body_saved', False) is False for request in metadata.get('requests', []))
    with pytest.raises(FeedParseError) as caught:
        parse_feed(payload, 'json')
    assert caught.value.code is ReasonCode.FEED_SCHEMA


def test_more_than_microsecond_precision_remains_explicitly_unsupported_not_truncated():
    fixture = json_fixture(updated='2026-11-03T12:30:00.123456789Z')
    with pytest.raises(FeedParseError) as caught:
        parse_feed(fixture.body, fixture.format)
    assert caught.value.code is ReasonCode.INVALID_TIMESTAMP

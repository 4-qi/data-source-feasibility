"""Fixed apple-observed-v1 vectors and full-value comparison invariants."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest

from feasibility.apple_ingestion.contracts import ContractError, ReviewRecord
from feasibility.apple_ingestion.normalizer import HASH_CONTRACT_VERSION, canonical_fields, fingerprint


def record(**changes):
    values = dict(source_review_id=" opaque /001 ", title=None, body="Hello\r\n世界😀", rating=3,
                  application_version="1.0", source_updated_at=datetime(2026, 11, 3, 12, 30,
                                                                         tzinfo=timezone(timedelta(hours=-8))))
    return ReviewRecord(**(values | changes))


def test_fixed_utf8_json_sha256_vectors_and_public_tuple_api():
    value = record()
    fields = canonical_fields(value)
    assert type(fields) is tuple
    assert fields == (None, "Hello\n世界😀", 3, "1.0", "2026-11-03T20:30:00.000000Z")
    hashes = fingerprint(value)
    assert type(hashes) is tuple and all(type(item) is bytes and len(item) == 32 for item in hashes)
    assert tuple(item.hex() for item in hashes) == (
        "db0364374d18b81ef27a74dc2456b54b324e8921e6f04d880f1f511a322bd1ee",
        "142b6d5ff58dbfea33418233828314ea58fb8969f96e9ab9904075c49d37b0c4")
    assert HASH_CONTRACT_VERSION == "apple-observed-v1"
    assert value.body == "Hello\r\n世界😀"  # comparison never mutates storage fields


def test_fixed_null_metadata_and_empty_body_vectors():
    value = ReviewRecord("id", None, "", 1)
    assert tuple(item.hex() for item in fingerprint(value)) == (
        "5b5566edf47bd4fd3877699da1f2d0318a4bb4a27c138b4cbe27120580b46dd8",
        "2b330296c14615d8703687dcbd2935878204607a50f383828394efcbd16b7c91")


def test_composed_unicode_and_all_line_endings_compare_equally():
    left = record(title="Cafe\u0301\rline\r\n", body="e\u0301\r\n\r", application_version="ve\u0301\r\n")
    right = record(title="Café\nline\n", body="é\n\n", application_version="vé\n")
    assert canonical_fields(left) == canonical_fields(right)
    assert fingerprint(left) == fingerprint(right)
    assert left.title == "Cafe\u0301\rline\r\n"


@pytest.mark.parametrize("field,value", [("title", ""), ("title", "New title"),
                                         ("body", "Hello\n世界😀 "), ("body", "hello\n世界😀"),
                                         ("body", "Hello  世界😀"), ("body", "Hello &amp; 世界😀")])
def test_content_changes_preserve_whitespace_case_entities_and_null_distinction(field, value):
    original = record()
    changed = replace(original, **{field: value})
    assert canonical_fields(changed) != canonical_fields(original)
    assert fingerprint(changed)[0] != fingerprint(original)[0]
    assert fingerprint(changed)[1] == fingerprint(original)[1]


@pytest.mark.parametrize("field,value", [("rating", 4), ("application_version", ""),
                                         ("application_version", None),
                                         ("source_updated_at", None),
                                         ("source_updated_at", datetime(2026, 11, 3, 20, 30, 0, 1, tzinfo=timezone.utc))])
def test_metadata_changes_are_versions_even_when_content_stays_equal(field, value):
    original = record()
    changed = replace(original, **{field: value})
    assert canonical_fields(changed) != canonical_fields(original)
    assert fingerprint(changed)[0] == fingerprint(original)[0]
    assert fingerprint(changed)[1] != fingerprint(original)[1]


def test_equivalent_offset_timestamps_and_opaque_ids_do_not_change_hashes():
    left = record()
    right = replace(left, source_review_id="completely different opaque ID",
                    source_updated_at=left.source_updated_at.astimezone(timezone.utc))
    assert canonical_fields(left) == canonical_fields(right)
    assert fingerprint(left) == fingerprint(right)


def test_full_text_tail_participates_in_hash_and_full_field_comparison():
    left = record(body="正文😀\n" * 30_000 + "A")
    right = replace(left, body=left.body[:-1] + "B")
    assert len(canonical_fields(left)[1]) == len(left.body)
    assert canonical_fields(left) != canonical_fields(right)
    assert fingerprint(left)[0] != fingerprint(right)[0]


def test_lone_surrogates_and_utc_overflow_raise_safe_errors():
    for value in (record(body="private\ud800text"),
                  record(source_updated_at=datetime(1, 1, 1, tzinfo=timezone(timedelta(hours=1))))):
        with pytest.raises(ContractError) as caught:
            fingerprint(value)
        assert "private" not in str(caught.value)

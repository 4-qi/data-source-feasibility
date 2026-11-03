"""Strict in-memory Apple JSON/Atom adapters, with no partial-page success.

Only recognizably marked Application catalog entries may be ignored: im:name
and im:contentType term=Application, with no content/rating/version review fields.
All other entries are review candidates. Nested XML text/XHTML and external-src
content are explicitly unsupported and fail the page instead of losing text.
Neither adapter HTML-unescapes strings after its one transport-level decode.
"""
from dataclasses import dataclass
from datetime import datetime
import json
import re
import xml.etree.ElementTree as ET
from xml.parsers import expat

from .contracts import ContractError, FeedFormat, ReasonCode, ReviewRecord

PARSER_VERSION = "apple-feed-v1"
ATOM = "{http://www.w3.org/2005/Atom}"
IM = "{http://itunes.apple.com/rss}"
_TIMESTAMP = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}"
                        r"(?:\.[0-9]{1,6})?(?:Z|[+-][0-9]{2}:[0-9]{2})\Z")


class FeedParseError(ContractError):
    """Safe enumerated error only: no raw text, source IDs or parser exceptions."""
    def __init__(self, code: ReasonCode):
        self.code = code
        super().__init__(code.value)


@dataclass(frozen=True)
class ParsedPage:
    records: tuple[ReviewRecord, ...]
    entry_absent: bool
    entry_count: int
    codes: tuple[ReasonCode, ...] = ()


def _text(value: object) -> str:
    if type(value) is not str or "\x00" in value:
        raise FeedParseError(ReasonCode.ENTRY_SCHEMA)
    try:
        value.encode("utf-8")
    except UnicodeError:
        raise FeedParseError(ReasonCode.ENTRY_SCHEMA) from None
    return value


def _timestamp(value: str | None) -> datetime | None:
    if value is None:
        return None
    if not _TIMESTAMP.fullmatch(value):
        raise FeedParseError(ReasonCode.INVALID_TIMESTAMP)
    # RFC 3339 offsets use hours 00..23 and minutes 00..59. datetime accepts
    # minute overflow, so validate this before its conversion.
    if value[-1] != "Z" and (int(value[-5:-3]) > 23 or int(value[-2:]) > 59):
        raise FeedParseError(ReasonCode.INVALID_TIMESTAMP)
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise FeedParseError(ReasonCode.INVALID_TIMESTAMP) from None


def _record(values: dict) -> ReviewRecord:
    try:
        rating = values["im:rating"]
        if type(rating) is not str or not re.fullmatch("[1-5]", rating):
            raise FeedParseError(ReasonCode.ENTRY_SCHEMA)
        return ReviewRecord(source_review_id=values["id"], title=values.get("title"),
                            body=values["content"], rating=int(rating),
                            application_version=values.get("im:version"),
                            source_updated_at=_timestamp(values.get("updated")))
    except (KeyError, ContractError) as exc:
        if isinstance(exc, FeedParseError):
            raise
        raise FeedParseError(ReasonCode.ENTRY_SCHEMA) from None


def _json_label(entry: dict, key: str) -> str:
    value = entry[key]
    if type(value) is not dict or "label" not in value:
        raise FeedParseError(ReasonCode.ENTRY_SCHEMA)
    return _text(value["label"])


def _json_catalog(entry: dict) -> bool:
    if any(key in entry for key in ("im:rating", "im:version", "content")):
        return False
    content_type = entry.get("im:contentType")
    if type(content_type) is not dict or type(content_type.get("attributes")) is not dict:
        return False
    if content_type["attributes"].get("term") != "Application":
        return False
    if "im:name" not in entry:
        return False
    return bool(_json_label(entry, "im:name").strip())


def _json_page(body: bytes) -> tuple[list[dict], bool]:
    def unique_object(pairs):
        value = {}
        for key, item in pairs:
            if key in value:
                raise FeedParseError(ReasonCode.FEED_SCHEMA)
            value[key] = item
        return value

    def invalid_constant(_):
        raise FeedParseError(ReasonCode.FEED_SCHEMA)

    try:
        payload = json.loads(body, object_pairs_hook=unique_object, parse_constant=invalid_constant)
    except (ValueError, UnicodeError, RecursionError):
        raise FeedParseError(ReasonCode.FEED_SCHEMA) from None
    if type(payload) is not dict or type(payload.get("feed")) is not dict:
        raise FeedParseError(ReasonCode.FEED_SCHEMA)
    feed = payload["feed"]
    if "entry" not in feed:
        return [], True
    entries = feed["entry"]
    if type(entries) is dict:
        entries = [entries]
    if type(entries) is not list:
        raise FeedParseError(ReasonCode.FEED_SCHEMA)
    result = []
    for entry in entries:
        if type(entry) is not dict:
            raise FeedParseError(ReasonCode.ENTRY_SCHEMA)
        if _json_catalog(entry):
            continue
        values = {key: _json_label(entry, key) for key in
                  ("id", "content", "im:rating", "title", "im:version", "updated") if key in entry}
        result.append(values)
    return result, False


def _xml_text(element: ET.Element) -> str:
    if len(element) or element.get("src") is not None or element.get("type") not in (None, "text", "html"):
        raise FeedParseError(ReasonCode.ENTRY_SCHEMA)
    return _text(element.text if element.text is not None else "")


def _xml_page(body: bytes) -> tuple[list[dict], bool]:
    def forbidden(*_):
        raise FeedParseError(ReasonCode.FEED_SCHEMA)

    # Expat checks declarations in the actual declared encoding (also UTF-16),
    # avoiding byte-pattern filters that can miss NUL-interleaved DTDs.
    guard = expat.ParserCreate()
    guard.StartDoctypeDeclHandler = forbidden
    guard.EntityDeclHandler = forbidden
    guard.ExternalEntityRefHandler = forbidden
    try:
        guard.Parse(body, True)
        root = ET.fromstring(body)
    except (expat.ExpatError, ET.ParseError, ValueError, RecursionError):
        raise FeedParseError(ReasonCode.FEED_SCHEMA) from None
    if root.tag != ATOM + "feed":
        raise FeedParseError(ReasonCode.FEED_SCHEMA)
    if any(child.tag.rsplit("}", 1)[-1] == "entry" and child.tag != ATOM + "entry" for child in root):
        raise FeedParseError(ReasonCode.FEED_SCHEMA)
    result = []
    tags = {ATOM + key: key for key in ("id", "content", "title", "updated")}
    tags.update({IM + key: "im:" + key for key in ("rating", "version")})
    for entry in root.findall(ATOM + "entry"):
        by_tag = {}
        for child in entry:
            if child.tag in tags or child.tag in (IM + "name", IM + "contentType"):
                if child.tag in by_tag:
                    raise FeedParseError(ReasonCode.ENTRY_SCHEMA)
                by_tag[child.tag] = child
        if not any(tag in by_tag for tag in (IM + "rating", IM + "version", ATOM + "content")):
            name, kind = by_tag.get(IM + "name"), by_tag.get(IM + "contentType")
            if name is not None and kind is not None and kind.get("term") == "Application" and _xml_text(name).strip():
                continue
        result.append({tags[tag]: _xml_text(child) for tag, child in by_tag.items() if tag in tags})
    return result, False


def parse_feed(body: bytes, format: FeedFormat | str) -> ParsedPage:
    """Parse an entire page or raise FeedParseError with a safe ReasonCode.

    entry_absent distinguishes a missing JSON entry member from a valid empty
    member/feed. entry_count counts review candidates, excluding known catalogs.
    Duplicate IDs are returned in source order for later reconciliation.
    """
    if type(body) is not bytes:
        raise FeedParseError(ReasonCode.FEED_SCHEMA)
    try:
        selected = FeedFormat(format)
    except (ValueError, TypeError):
        raise FeedParseError(ReasonCode.FEED_SCHEMA) from None
    entries, absent = _json_page(body) if selected is FeedFormat.JSON else _xml_page(body)
    records = tuple(_record(values) for values in entries)
    codes = ((ReasonCode.JSON_ENTRY_ABSENT,) if absent else ())
    if not records:
        codes += (ReasonCode.EMPTY_PAGE,)
    return ParsedPage(records, absent, len(records), codes)

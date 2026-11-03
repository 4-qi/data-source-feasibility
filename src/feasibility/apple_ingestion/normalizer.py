"""Pure comparison contract apple-observed-v1; stored records stay untouched.

All compared strings normalize CRLF/CR to LF and Unicode to NFC. Canonical JSON
uses UTF-8, ensure_ascii=False, separators=(',', ':'), allow_nan=False. UTC source
timestamps use exactly six fractional digits and a trailing Z; null stays null.
Review identity is not part of either hash and is never normalized here.
"""
from datetime import timezone
import hashlib
import json
import unicodedata

from .contracts import ContractError, ReviewRecord

HASH_CONTRACT_VERSION = "apple-observed-v1"


CanonicalFields = tuple[str | None, str, int, str | None, str | None]


def _normalize(value: str | None) -> str | None:
    if value is None:
        return None
    result = unicodedata.normalize("NFC", value.replace("\r\n", "\n").replace("\r", "\n"))
    # Python strings can contain lone surrogates, but canonical UTF-8 cannot.
    try:
        result.encode("utf-8")
    except UnicodeError:
        raise ContractError("comparison text must contain valid Unicode scalars") from None
    return result


def canonical_fields(record: ReviewRecord) -> CanonicalFields:
    """Return (title, body, rating, application_version, UTC_timestamp_or_none).

    Compare this complete tuple for equality as well as the two hash values.
    """
    if type(record) is not ReviewRecord:
        raise ContractError("record must be a ReviewRecord")
    try:
        timestamp = (record.source_updated_at.astimezone(timezone.utc).isoformat(
            timespec="microseconds").replace("+00:00", "Z")
            if record.source_updated_at is not None else None)
    except (ValueError, OverflowError):
        raise ContractError("source_updated_at cannot be represented in UTC") from None
    return (_normalize(record.title), _normalize(record.body), record.rating,
            _normalize(record.application_version), timestamp)


def fingerprint(record: ReviewRecord) -> tuple[bytes, bytes]:
    """Hash complete canonical fields. Hash equality alone does not prove equality."""
    values = canonical_fields(record)

    def digest(fields: tuple) -> bytes:
        payload = json.dumps(fields, ensure_ascii=False, separators=(",", ":"),
                             allow_nan=False).encode("utf-8")
        return hashlib.sha256(payload).digest()

    return digest(values[:2]), digest(values[2:])

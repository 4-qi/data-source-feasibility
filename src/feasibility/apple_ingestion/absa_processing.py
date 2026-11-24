"""Prepare a private current-review CSV for aspect-based sentiment analysis."""

import argparse
import csv
from dataclasses import dataclass
from datetime import datetime
from hashlib import sha256
from io import StringIO
import json
from pathlib import Path
import re
import stat
from threading import Lock
import unicodedata
from uuid import UUID

from .retrieval import normalize_filters
from .retrieval_export import (
    CONTRACT_VERSION as RETRIEVAL_CONTRACT,
    CSV_COLUMNS as RETRIEVAL_COLUMNS,
    _private_file,
    decode_csv_cell,
    encode_csv_cell,
)


CONTRACT_VERSION = "apple-absa-processing/v1"
DERIVED_COLUMNS = (
    "analysis_text", "has_text", "text_length", "is_analysis_eligible",
    "exclusion_reason", "language_status", "source_dataset_label",
    "processing_contract_version", "processing_config_id",
)
CSV_COLUMNS = RETRIEVAL_COLUMNS + DERIVED_COLUMNS
# Unicode White_Space, explicitly fixed for this contract.
_EDGE_WHITESPACE = (
    "\t\n\v\f\r \x85\xa0\u1680\u2000\u2001\u2002\u2003\u2004\u2005"
    "\u2006\u2007\u2008\u2009\u200a\u2028\u2029\u202f\u205f\u3000"
)
_NULLABLE = {"title", "application_version", "source_updated_at"}
_TIME_FIELDS = (
    "source_updated_at", "first_observed_at", "last_observed_at", "version_first_observed_at",
)
_ID_FIELDS = ("source", "source_application_id", "source_review_id")
_CSV_READ_LOCK = Lock()


class ProcessingError(ValueError):
    """A validation failure with no source text or identifiers in its message."""


@dataclass(frozen=True)
class ProcessingConfig:
    unicode_version: str = unicodedata.unidata_version

    def __post_init__(self):
        if self.unicode_version != unicodedata.unidata_version:
            raise ProcessingError("Requested Unicode database version is unavailable")

    @property
    def identifier(self):
        return f"{CONTRACT_VERSION}/nfc-ucd-{self.unicode_version}"


def _valid_label(label):
    return isinstance(label, str) and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}", label)


def _utc_timestamp(value):
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ProcessingError("Expected a UTC timestamp")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
        if parsed.tzinfo is None or encode_csv_cell(parsed) != value:
            raise ValueError
        return parsed
    except ValueError:
        raise ProcessingError("Invalid UTC timestamp") from None


def _validate_record(record):
    if not isinstance(record, dict) or record.keys() != set(RETRIEVAL_COLUMNS):
        raise ProcessingError("Expected the current-review CSV schema")
    for name, value in record.items():
        if value is None and name in _NULLABLE:
            continue
        if not isinstance(value, str) or "\0" in value:
            raise ProcessingError(f"Invalid value in {name}")
    for name in (*_ID_FIELDS, "detecting_run_status", "storefront", "sort_by"):
        if not record[name].strip(_EDGE_WHITESPACE):
            raise ProcessingError(f"Missing value in {name}")
    if record["source"] != "apple_app_store":
        raise ProcessingError("Unsupported review source")
    for name in ("review_id", "version_id", "version_number", "observation_count",
                 "conflict_occurrence_count", "rating"):
        minimum = 0 if name.endswith("_count") else 1
        value = record[name]
        if (not re.fullmatch(r"0|[1-9][0-9]{0,18}", value)
                or not minimum <= int(value) <= (5 if name == "rating" else 2**63 - 1)):
            raise ProcessingError(f"Invalid integer in {name}")
    for name in _TIME_FIELDS:
        if record[name] is not None:
            _utc_timestamp(record[name])
    for name in ("detecting_run_id", "detecting_batch_id"):
        try:
            if str(UUID(record[name])) != record[name]:
                raise ValueError
        except ValueError:
            raise ProcessingError(f"Invalid UUID in {name}") from None


def _prepare_text(value):
    text = (value or "").replace("\r\n", "\n").replace("\r", "\n")
    return unicodedata.normalize("NFC", text).strip(_EDGE_WHITESPACE)


def process_review(record, config, *, dataset_label):
    """Return a new flat dict from one decoded retrieval CSV row (strings or None)."""
    if not isinstance(config, ProcessingConfig) or not _valid_label(dataset_label):
        raise ProcessingError("Expected a processing configuration and valid dataset label")
    _validate_record(record)
    title, body = record["title"], record["body"]
    analysis_text = "\n\n".join(filter(None, (_prepare_text(title), _prepare_text(body))))
    has_text = bool(analysis_text)
    reason = None if has_text else ("whitespace_only" if title or body else "missing_text")
    return {
        **record,
        "analysis_text": analysis_text,
        "has_text": has_text,
        "text_length": len(analysis_text),
        "is_analysis_eligible": has_text,
        "exclusion_reason": reason,
        "language_status": "unknown",
        "source_dataset_label": dataset_label,
        "processing_contract_version": CONTRACT_VERSION,
        "processing_config_id": config.identifier,
    }


def _validate_context(config, dataset_label, source_application_id):
    if not isinstance(config, ProcessingConfig) or not _valid_label(dataset_label):
        raise ProcessingError("Expected a processing configuration and valid dataset label")
    if not isinstance(source_application_id, str) or not source_application_id.strip(_EDGE_WHITESPACE):
        raise ProcessingError("Expected a source application ID")


def process_reviews(records, config, *, dataset_label, source_application_id):
    """Prepare a single-app, single-snapshot batch, ordered by internal review ID."""
    _validate_context(config, dataset_label, source_application_id)
    processed = []
    source_ids, review_ids, version_ids = set(), set(), set()
    for record in records:
        row = process_review(record, config, dataset_label=dataset_label)
        if row["source_application_id"] != source_application_id:
            raise ProcessingError("Review application differs from the input manifest")
        source_id, review_id, version_id = (row[name] for name in (
            "source_review_id", "review_id", "version_id",
        ))
        if source_id in source_ids or review_id in review_ids or version_id in version_ids:
            raise ProcessingError("Duplicate review or version identity in the current-review input")
        source_ids.add(source_id)
        review_ids.add(review_id)
        version_ids.add(version_id)
        processed.append(row)
    return sorted(processed, key=lambda row: int(row["review_id"]))


def _read_manifest(path):
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if (not isinstance(manifest, dict) or manifest.get("contract_version") != RETRIEVAL_CONTRACT
            or not _valid_label(manifest.get("dataset_label"))
            or type(manifest.get("row_count")) is not int or manifest["row_count"] < 0):
        raise ProcessingError("Invalid retrieval manifest")
    _utc_timestamp(manifest.get("exported_at"))
    filters = manifest.get("filters")
    if not isinstance(filters, dict) or filters.keys() != {
        "source_application_id", "time_field", "start", "end", "ratings",
    }:
        raise ProcessingError("Invalid retrieval filters")
    bounds = {name: _utc_timestamp(filters[name]) if filters[name] is not None else None
              for name in ("start", "end")}
    normalize_filters(filters["source_application_id"], filters["time_field"],
                      bounds["start"], bounds["end"], filters["ratings"], batch_size=1)
    return manifest


def _read_rows(raw):
    reader = csv.reader(StringIO(raw.decode("utf-8"), newline=""), strict=True)
    if tuple(next(reader, ())) != RETRIEVAL_COLUMNS:
        raise ProcessingError("Unexpected retrieval CSV header")
    for cells in reader:
        if len(cells) != len(RETRIEVAL_COLUMNS):
            raise ProcessingError("Unexpected retrieval CSV row width")
        values = [decode_csv_cell(cell) for cell in cells]
        if any(encode_csv_cell(value) != cell for value, cell in zip(values, cells)):
            raise ProcessingError("Invalid retrieval CSV escaping")
        yield dict(zip(RETRIEVAL_COLUMNS, values))


def _process_csv(raw, config, manifest):
    # The stdlib CSV limit is process-wide. Bound it by the input already in
    # memory, allow long stored fields, and restore it before returning.
    with _CSV_READ_LOCK:
        original_limit = csv.field_size_limit()
        csv.field_size_limit(max(original_limit, len(raw)))
        try:
            return process_reviews(
                _read_rows(raw), config, dataset_label=manifest["dataset_label"],
                source_application_id=manifest["filters"]["source_application_id"],
            )
        finally:
            csv.field_size_limit(original_limit)


def _private_destination(output_dir):
    path = Path(output_dir)
    if not path.is_absolute() or path.name in ("", ".", ".."):
        raise ProcessingError("Expected an absolute new output directory")
    destination = path.parent.resolve(strict=True) / path.name
    if any((parent / ".git").is_file() or (parent / ".git" / "HEAD").is_file()
           for parent in destination.parents):
        raise ProcessingError("Expected a private directory outside a Git checkout")
    return destination


def export_processed_reviews(input_dir, output_dir, config=ProcessingConfig()):
    """Process one completed retrieval export and publish the completion manifest last."""
    input_path = Path(input_dir)
    manifest = _read_manifest(input_path / "manifest.json")
    raw = (input_path / "reviews.csv").read_bytes()
    rows = _process_csv(raw, config, manifest)
    if len(rows) != manifest["row_count"]:
        raise ProcessingError("Retrieval CSV row count differs from the input manifest")
    destination = _private_destination(output_dir)
    destination.mkdir(mode=0o700)
    csv_path = destination / "reviews.csv"
    manifest_path = destination / "manifest.json"
    try:
        if stat.S_IMODE(destination.stat().st_mode) != 0o700:
            raise ProcessingError("Output directory must support private permissions")
        with _private_file(csv_path, newline="") as output:
            writer = csv.writer(output, lineterminator="\r\n")
            writer.writerow(CSV_COLUMNS)
            for row in rows:
                writer.writerow(encode_csv_cell(row[name]) for name in CSV_COLUMNS)
        eligible = sum(row["is_analysis_eligible"] for row in rows)
        result = {
            "contract_version": CONTRACT_VERSION,
            "configuration_id": config.identifier,
            "unicode_version": config.unicode_version,
            "source_dataset_label": manifest["dataset_label"],
            "input_contract_version": RETRIEVAL_CONTRACT,
            "input_filters": manifest["filters"],
            "input_row_count": len(rows),
            "output_row_count": len(rows),
            "eligible_count": eligible,
            "excluded_count": len(rows) - eligible,
            "exclusion_counts": {reason: sum(row["exclusion_reason"] == reason for row in rows)
                                 for reason in ("missing_text", "whitespace_only")},
            "language_status_counts": {"unknown": len(rows)},
            "input_csv_sha256": sha256(raw).hexdigest(),
            "output_csv_sha256": sha256(csv_path.read_bytes()).hexdigest(),
        }
        # Rename a complete sidecar into place so its presence marks completion.
        pending_manifest = destination / ".manifest.tmp"
        with _private_file(pending_manifest) as output:
            json.dump(result, output, indent=2, sort_keys=True)
            output.write("\n")
        pending_manifest.rename(manifest_path)
        return result
    except BaseException:
        (destination / ".manifest.tmp").unlink(missing_ok=True)
        manifest_path.unlink(missing_ok=True)
        csv_path.unlink(missing_ok=True)
        destination.rmdir()
        raise


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", required=True, help="completed private retrieval export")
    parser.add_argument("--output-dir", required=True, help="new absolute private output directory")
    parser.add_argument("--unicode-version", default=unicodedata.unidata_version,
                        help="require the recorded Unicode database version")
    args = parser.parse_args(argv)
    try:
        result = export_processed_reviews(
            args.input_dir, args.output_dir, ProcessingConfig(args.unicode_version),
        )
    except (OSError, ValueError, csv.Error):
        parser.exit(1, "ABSA preparation failed. Check the retrieval export, configuration and output path.\n")
    print(f"Prepared {result['output_row_count']} rows ({result['eligible_count']} eligible).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

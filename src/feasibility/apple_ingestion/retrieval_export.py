"""Export a private CSV and manifest from one read-only PostgreSQL snapshot."""

import argparse
import csv
from dataclasses import fields
from datetime import datetime, timezone
import json
import os
import stat
from pathlib import Path
import re
from uuid import UUID

from sqlalchemy import text

from .deployment import deployment_engine, load_config
from .retrieval import CurrentReview, RetrievalError, iter_current_reviews, normalize_filters


CONTRACT_VERSION = "apple-review-retrieval/v1"
CSV_COLUMNS = tuple(field.name for field in fields(CurrentReview))
NULL = r"\N"


def _scalar(value):
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    if isinstance(value, UUID):
        return str(value)
    return value


def encode_csv_cell(value):
    value = _scalar(value)
    if value is None:
        return NULL
    if isinstance(value, str) and value.startswith("\\"):
        return "\\" + value
    return value


def decode_csv_cell(value):
    if value == NULL:
        return None
    if value.startswith("\\\\"):
        return value[1:]
    return value


def _private_file(path, *, newline=None):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    return os.fdopen(fd, "w", encoding="utf-8", newline=newline)


def export_current_reviews(engine, output_dir, *, dataset_label, expected_database,
                           source_application_id, time_field="first_observed_at",
                           start=None, end=None, ratings=None, batch_size=1000):
    """Create a fresh mode-0700 directory. The manifest marks completed output."""
    if not isinstance(dataset_label, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}", dataset_label):
        raise RetrievalError("Invalid dataset label")
    if not isinstance(expected_database, str) or not expected_database:
        raise RetrievalError("Expected database is required")
    filters = normalize_filters(source_application_id, time_field, start, end, ratings, batch_size)
    destination = Path(output_dir)
    if not destination.is_absolute():
        raise RetrievalError("Expected an absolute output directory")
    destination = destination.parent.resolve(strict=True) / destination.name
    if any((parent / ".git").is_file() or (parent / ".git" / "HEAD").is_file()
           for parent in destination.parents):
        raise RetrievalError("Expected a private directory outside a Git checkout")
    destination.mkdir(mode=0o700)
    csv_path = destination / "reviews.csv"
    manifest_path = destination / "manifest.json"
    try:
        if stat.S_IMODE(destination.stat().st_mode) != 0o700:
            raise RetrievalError("Output directory must support private permissions")
        with engine.connect() as connection, connection.begin():
            connection.exec_driver_sql("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
            if connection.scalar(text("SELECT current_database()")) != expected_database:
                raise RetrievalError("Connected database does not match expected database")
            count = 0
            with _private_file(csv_path, newline="") as output:
                writer = csv.writer(output)
                writer.writerow(CSV_COLUMNS)
                for row in iter_current_reviews(connection, **filters, batch_size=batch_size):
                    writer.writerow(encode_csv_cell(getattr(row, name)) for name in CSV_COLUMNS)
                    count += 1
        manifest = {
            "contract_version": CONTRACT_VERSION,
            "dataset_label": dataset_label,
            "filters": {name: _scalar(value) for name, value in filters.items()},
            "exported_at": _scalar(datetime.now(timezone.utc)),
            "row_count": count,
        }
        with _private_file(manifest_path) as output:
            json.dump(manifest, output, indent=2)
            output.write("\n")
        return manifest
    except BaseException:
        manifest_path.unlink(missing_ok=True)
        csv_path.unlink(missing_ok=True)
        destination.rmdir()
        raise


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--deployment", required=True)
    parser.add_argument("--expected-database", required=True)
    parser.add_argument("--dataset-label", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--app-id", required=True)
    parser.add_argument("--time-field", choices=("first_observed_at", "source_updated_at"),
                        default="first_observed_at")
    parser.add_argument("--start")
    parser.add_argument("--end")
    parser.add_argument("--rating", type=int, action="append")
    parser.add_argument("--batch-size", type=int, default=1000)
    args = parser.parse_args(argv)
    try:
        engine = deployment_engine(load_config(args.deployment), "report")
        try:
            result = export_current_reviews(
                engine, args.output_dir, dataset_label=args.dataset_label,
                expected_database=args.expected_database, source_application_id=args.app_id,
                time_field=args.time_field, ratings=args.rating, batch_size=args.batch_size,
                start=datetime.fromisoformat(args.start.replace("Z", "+00:00")) if args.start else None,
                end=datetime.fromisoformat(args.end.replace("Z", "+00:00")) if args.end else None,
            )
        finally:
            engine.dispose()
    except Exception:
        parser.exit(1, "Review export failed. Check database selection, filters and private output directory.\n")
    print(f"Exported {result['row_count']} review rows.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

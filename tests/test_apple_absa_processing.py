"""Deterministic ABSA preparation checks using synthetic retrieval exports."""

import csv
from hashlib import sha256
import json
from pathlib import Path
import stat
from unicodedata import unidata_version

import pytest

pytest.importorskip("sqlalchemy")
from feasibility.apple_ingestion import absa_processing as absa
from feasibility.apple_ingestion import retrieval_export as retrieval


LABEL = "synthetic"
APP = "0001"
STAMP = "2026-11-14T05:00:00Z"
RUN = "ac45a690-bc8c-48bb-b3ae-38f93cf0c65a"


def review(**changes):
    return dict(
        source="apple_app_store", source_application_id=APP, source_review_id="00001",
        review_id="2", version_id="31", version_number="2", title=None, body="No ads!",
        rating="5", application_version=None, source_updated_at=None,
        first_observed_at=STAMP, last_observed_at=STAMP, version_first_observed_at=STAMP,
        detecting_run_id=RUN, detecting_batch_id=RUN, detecting_run_status="partial",
        storefront="us", sort_by="mostrecent", observation_count="7",
        conflict_occurrence_count="1",
    ) | changes


def retrieval_input(path, rows, **manifest_changes):
    path.mkdir(mode=0o700)
    with (path / "reviews.csv").open("w", encoding="utf-8", newline="") as output:
        writer = csv.writer(output)
        writer.writerow(retrieval.CSV_COLUMNS)
        writer.writerows(
            [retrieval.encode_csv_cell(row[name]) for name in retrieval.CSV_COLUMNS]
            for row in rows
        )
    manifest = {
        "contract_version": retrieval.CONTRACT_VERSION,
        "dataset_label": LABEL,
        "filters": dict(source_application_id=APP, time_field="first_observed_at",
                        start=None, end=None, ratings=None),
        "exported_at": STAMP,
        "row_count": len(rows),
    } | manifest_changes
    (path / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return path


def decoded_csv(path):
    with path.open(encoding="utf-8", newline="") as handle:
        return [{key: retrieval.decode_csv_cell(value) for key, value in row.items()}
                for row in csv.DictReader(handle)]


def test_normalizes_only_analysis_text():
    row = review(title="  Re\u0301glages\r\n  BETA!  ",
                 body="\u3000I do NOT pay  $5. 😕\r不行。\nSí, \u200d funciona.\t")
    original = row.copy()
    out = absa.process_review(row, absa.ProcessingConfig(), dataset_label=LABEL)
    assert row == original
    assert {key: out[key] for key in row} == original
    assert out["analysis_text"] == "Réglages\n  BETA!\n\nI do NOT pay  $5. 😕\n不行。\nSí, \u200d funciona."
    assert out["language_status"] == "unknown"
    assert out["text_length"] == len(out["analysis_text"])
    assert out["processing_config_id"] == f"{absa.CONTRACT_VERSION}/nfc-ucd-{unidata_version}"


@pytest.mark.parametrize("title,body,analysis_text,reason", [
    (None, "", "", "missing_text"),
    ("", "", "", "missing_text"),
    ("", "\u00a0\r\n\t", "", "whitespace_only"),
    (" \t", "", "", "whitespace_only"),
    (None, " No. ", "No.", None),
    ("好", "", "好", None),
    (None, "👍", "👍", None),
    (" ", " a \n\n  b ", "a \n\n  b", None),
])
def test_text_eligibility_retains_short_and_empty_records(title, body, analysis_text, reason):
    row = absa.process_review(review(title=title, body=body), absa.ProcessingConfig(),
                              dataset_label=LABEL)
    assert (row["title"], row["body"]) == (title, body)
    assert row["analysis_text"] == analysis_text
    assert row["has_text"] is row["is_analysis_eligible"] is bool(analysis_text)
    assert row["text_length"] == len(analysis_text)
    assert row["exclusion_reason"] == reason


def test_batch_orders_by_numeric_id_and_keeps_distinct_reviews_with_same_text():
    left = review()
    right = review(source_review_id="00002", review_id="10", version_id="42")
    rows = absa.process_reviews([right, left], absa.ProcessingConfig(),
                                dataset_label=LABEL, source_application_id=APP)
    assert [row["review_id"] for row in rows] == ["2", "10"]
    assert [row["source_review_id"] for row in rows] == ["00001", "00002"]
    assert [row["observation_count"] for row in rows] == ["7", "7"]
    assert [row["version_id"] for row in rows] == ["31", "42"]
    assert rows[0]["analysis_text"] == rows[1]["analysis_text"] == "No ads!"


@pytest.mark.parametrize("changes,reason", [
    ({}, "Duplicate"),
    ({"version_id": "30", "version_number": "1", "rating": "4"}, "Duplicate"),
    ({"source_review_id": "00002", "version_id": "32"}, "Duplicate"),
    ({"source_review_id": "00002", "review_id": "3"}, "Duplicate"),
    ({"source_application_id": "0002"}, "application"),
])
def test_batch_rejects_repeated_rows_history_and_mixed_apps(changes, reason):
    with pytest.raises(absa.ProcessingError, match=reason):
        absa.process_reviews([review(), review(**changes)], absa.ProcessingConfig(),
                             dataset_label=LABEL, source_application_id=APP)


@pytest.mark.parametrize("changes", [
    {"body": None}, {"rating": "0"}, {"review_id": "02"}, {"version_id": None},
    {"source_review_id": ""}, {"observation_count": "-1"},
    {"source_updated_at": "2026-11-14Z"}, {"detecting_run_id": "invalid"},
    {"is_current": "false"}, {"title": "x\0y"},
])
def test_malformed_records_are_rejected(changes):
    with pytest.raises(absa.ProcessingError):
        absa.process_review(review(**changes), absa.ProcessingConfig(), dataset_label=LABEL)


def test_invalid_configuration_is_rejected():
    with pytest.raises(absa.ProcessingError, match="Unicode database version"):
        absa.ProcessingConfig("0.0.0")
    with pytest.raises(absa.ProcessingError, match="configuration"):
        absa.process_review(review(), None, dataset_label=LABEL)


def test_export_is_private_faithful_and_reproducible(tmp_path):
    expected = [
        review(title=None, body=r"\N"),
        review(review_id="3", version_id="32", source_review_id="00002", version_number="1",
               title="", body='Line 1\r\n雪 😕, "why?"\rLine 3', source_updated_at=STAMP),
        review(review_id="10", version_id="42", source_review_id="00003", body=" "),
        review(review_id="11", version_id="43", source_review_id="00004", body=""),
    ]
    source = retrieval_input(tmp_path / "retrieval", expected[::-1])
    input_files = {name: (source / name).read_bytes() for name in ("reviews.csv", "manifest.json")}
    first, second = tmp_path / "first", tmp_path / "second"
    result = absa.export_processed_reviews(source, first)
    # Export clocks are independent of snapshot identity.
    manifest = json.loads(input_files["manifest.json"])
    manifest["exported_at"] = "2026-11-15T05:00:00Z"
    (source / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    assert absa.export_processed_reviews(source, second) == result
    for name in ("reviews.csv", "manifest.json"):
        assert (first / name).read_bytes() == (second / name).read_bytes()
        assert stat.S_IMODE((first / name).stat().st_mode) == 0o600
    assert stat.S_IMODE(first.stat().st_mode) == 0o700
    assert (source / "reviews.csv").read_bytes() == input_files["reviews.csv"]
    assert json.loads((source / "manifest.json").read_text()) == manifest
    rows = decoded_csv(first / "reviews.csv")
    assert tuple(rows[0]) == absa.CSV_COLUMNS
    assert [{key: row[key] for key in retrieval.CSV_COLUMNS} for row in rows] == expected
    assert [row["analysis_text"] for row in rows] == [r"\N", 'Line 1\n雪 😕, "why?"\nLine 3', "", ""]
    assert [row["exclusion_reason"] for row in rows] == [None, None, "whitespace_only", "missing_text"]
    assert result["input_row_count"] == result["output_row_count"] == 4
    assert result["eligible_count"] == result["excluded_count"] == 2
    assert result["exclusion_counts"] == {"missing_text": 1, "whitespace_only": 1}
    assert result["language_status_counts"] == {"unknown": 4}
    assert result["input_csv_sha256"] == sha256(input_files["reviews.csv"]).hexdigest()
    assert result["output_csv_sha256"] == sha256((first / "reviews.csv").read_bytes()).hexdigest()
    with pytest.raises(FileExistsError):
        absa.export_processed_reviews(source, first)
    assert result["output_csv_sha256"] == sha256((first / "reviews.csv").read_bytes()).hexdigest()


def test_empty_and_long_exports(tmp_path):
    empty = retrieval_input(tmp_path / "empty", [])
    assert absa.export_processed_reviews(empty, tmp_path / "empty-out")["output_row_count"] == 0
    previous_limit = csv.field_size_limit()
    long = retrieval_input(tmp_path / "long", [review(body="x" * (previous_limit + 1))])
    assert absa.export_processed_reviews(long, tmp_path / "long-out")["output_row_count"] == 1
    assert csv.field_size_limit() == previous_limit


@pytest.mark.parametrize("case", ["header", "width", "quoting", "escape", "count", "contract", "missing"])
def test_malformed_exports_leave_no_output(tmp_path, case):
    source = retrieval_input(tmp_path / "retrieval", [review()])
    path = source / "reviews.csv"
    manifest_path = source / "manifest.json"
    raw = path.read_bytes()
    manifest = json.loads(manifest_path.read_bytes())
    if case == "header":
        path.write_bytes(raw.replace(b"source,", b"wrong_field,", 1))
    elif case == "width":
        path.write_bytes(raw.rstrip(b"\r\n") + b",extra\r\n")
    elif case == "quoting":
        path.write_bytes(raw + b'"unclosed')
    elif case == "escape":
        path.write_bytes(raw.replace(b"No ads!", br"\bad"))
    elif case == "count":
        manifest["row_count"] = 0
    elif case == "contract":
        manifest["contract_version"] = "future"
    if case == "missing":
        manifest_path.unlink()
    else:
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises((absa.ProcessingError, csv.Error, FileNotFoundError)):
        absa.export_processed_reviews(source, tmp_path / "output")
    assert not (tmp_path / "output").exists()


def test_cli_keeps_review_text_out_of_errors_and_checks_destination(tmp_path, capsys):
    source = retrieval_input(tmp_path / "retrieval", [review(body="private-synthetic-marker")])
    checkout = tmp_path / "checkout"
    checkout.mkdir()
    (checkout / ".git").write_text("placeholder", encoding="utf-8")
    with pytest.raises(SystemExit, match="1"):
        absa.main(["--input-dir", str(source), "--output-dir", str(checkout / "output")])
    assert "private-synthetic-marker" not in capsys.readouterr().err
    assert not (checkout / "output").exists()
    output = tmp_path / "output"
    assert absa.main(["--input-dir", str(source), "--output-dir", str(output)]) == 0
    assert capsys.readouterr().out == "Prepared 1 rows (1 eligible).\n"
    assert Path(output, "manifest.json").is_file()

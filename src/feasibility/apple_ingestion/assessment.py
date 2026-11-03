"""Private human-only quality sampling; no labels, sentiment or network inferred.

A primary sample uses one latest version with an undisputed completed-run
observation at cutoff per logical review. A conflicted observation is excluded;
independent clean observations can confirm that same accepted version. Terminal
partial/failed/interrupted runs may contribute individually committed clean
observations: quality eligibility is independent of coverage/reference eligibility.

Sample dicts contain private full text. Only summarize_assessment's aggregate
result belongs in routine reports. Human provenance is a required declaration,
not identity verification; synthetic fixture labels are counted separately.
"""
from collections import Counter
from datetime import datetime, timezone
import hashlib
import html
import json
import os
from pathlib import Path
import stat

from sqlalchemy import select
from sqlalchemy.engine import Connection

from .contracts import ConfigSnapshot, RunMode
from .models import Application, CollectionRun, FetchAttempt, Review, ReviewObservation, ReviewVersion
from .seed import load_seed_manifest

SAMPLE_SCHEMA = "apple-assessment-sample/1"
LABEL_SCHEMA = "apple-human-labels/1"
QUERY_VERSION = "apple-quality-sample/1"
RUBRIC_VERSION = "apple-usefulness/1"
RUBRIC = {
    "U3": "Detailed concrete experience, context, action and consequence",
    "U2": "Concrete but limited feedback",
    "U1": "Generic reaction with little detail",
    "U0": "Unusable or unclear content for experience assessment",
}
_REPOSITORY = Path(__file__).resolve().parents[3]
_MANIFEST = _REPOSITORY / "results/mainstream/app_sample_manifest.json"
A, R, F, I, O, V = (model.__table__ for model in (
    Application, CollectionRun, FetchAttempt, Review, ReviewObservation, ReviewVersion))
_LABEL_KEYS = frozenset({"schema_version", "manifest_id", "rubric_version", "review_id", "version_id",
    "reviewer_id", "assessed_at", "language", "full_text_read", "label", "reason",
    "assessment_type", "provenance", "ai_assistance", "unassessed_reason"})
_UNASSESSED = frozenset({"PENDING_HUMAN", "LANGUAGE_UNAVAILABLE", "FULL_TEXT_NOT_READ", "REVIEWER_UNAVAILABLE"})


class AssessmentError(ValueError):
    """Safe fixed codes only; never include private text or input exceptions."""
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def _aware(value):
    try:
        if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
            raise ValueError
        return value.astimezone(timezone.utc)
    except Exception:
        raise AssessmentError("AWARE_TIMESTAMP_REQUIRED") from None


def _iso(value):
    return _aware(value).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _json(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True, allow_nan=False)


def _manifest_id(sample):
    payload = {key: value for key, value in sample.items() if key != "manifest_id"}
    return hashlib.sha256(_json(payload).encode("utf-8")).hexdigest()


def _text(value):
    if type(value) is not str or not value.strip() or "\x00" in value:
        return False
    try:
        value.encode("utf-8")
        return True
    except UnicodeError:
        return False


def _validate_sample(sample):
    try:
        if type(sample) is not dict or sample["schema_version"] != SAMPLE_SCHEMA or sample["query_version"] != QUERY_VERSION:
            raise ValueError
        if sample["rubric_version"] != RUBRIC_VERSION or sample["manifest_id"] != _manifest_id(sample):
            raise ValueError
        mode = RunMode(sample["run_mode"])
        if sample["evidence_kind"] != mode.value:
            raise ValueError
        records = sample["records"]
        if type(records) is not list or len({row["review_id"] for row in records}) != len(records):
            raise ValueError
        return sample
    except Exception:
        raise AssessmentError("INVALID_ASSESSMENT_MANIFEST") from None


def build_sample(connection: Connection, *, cutoff: datetime, seed: str, per_app=10,
                 run_mode=RunMode.SYNTHETIC) -> dict:
    """Read-only sample; caller owns the read transaction. No source-date cutoff.

    Uses all terminal runs finished <= cutoff; per-observation committed markers
    and conflicts control admission. In-progress runs, mixed-mode versions,
    malformed snapshots and observations after cutoff are excluded explicitly.
    """
    instant = _aware(cutoff)
    if not isinstance(connection, Connection) or connection.closed or connection.invalidated:
        raise AssessmentError("READ_CONNECTION_REQUIRED")
    if not _text(seed) or type(per_app) is not int or not 1 <= per_app <= 1000:
        raise AssessmentError("INVALID_SAMPLING_PARAMETERS")
    try:
        mode = RunMode(run_mode)
    except (TypeError, ValueError):
        raise AssessmentError("INVALID_RUN_MODE") from None
    frame = load_seed_manifest(_MANIFEST)
    source_ids = [item.source_application_id for item in frame]
    apps = {row["source_application_id"]: row for row in connection.execute(select(A).where(
        A.c.source == "apple_app_store", A.c.source_application_id.in_(source_ids))).mappings()}
    if len(apps) != 8 or any(apps[item.source_application_id]["analytical_category"] != item.analytical_category for item in frame):
        raise AssessmentError("EIGHT_APP_FRAME_REQUIRED")
    app_ids = [apps[source_id]["id"] for source_id in source_ids]
    runs = {row["id"]: row for row in connection.execute(select(R).where(R.c.application_id.in_(app_ids))).mappings()}
    snapshots, run_reasons = {}, {}
    for run_id, run in runs.items():
        if run["finished_at"] is None or run["execution_status"] == "running" or run["finished_at"] > instant:
            run_reasons[run_id] = "RUN_NOT_FINISHED_BY_CUTOFF"
            continue
        try:
            snapshot = ConfigSnapshot.from_dict(run["config_snapshot"])
            app = apps.get(snapshot.source_application_id)
            if (app is None or snapshot.application_id != run["application_id"] or app["id"] != run["application_id"]
                    or snapshot.target_id != run["target_id"] or run["coverage_status"] == "pending"):
                raise ValueError
            if snapshot.run_mode is not mode:
                run_reasons[run_id] = "RUN_MODE_MISMATCH"
                continue
            snapshots[run_id] = snapshot
        except (KeyError, TypeError, ValueError):
            run_reasons[run_id] = "INVALID_RUN_SNAPSHOT"
    rows = connection.execute(select(
        O.c.run_id, O.c.application_id, O.c.review_id, O.c.observed_version_id,
        O.c.first_observed_at.label("observation_at"), O.c.conflict_count,
        V.c.version_number, V.c.title, V.c.body, V.c.first_observed_at.label("version_at"),
        V.c.detecting_run_id, F.c.persistence_status,
    ).select_from(O.join(V, O.c.observed_version_id == V.c.id).join(I, O.c.review_id == I.c.id)
      .outerjoin(F, (F.c.run_id == O.c.run_id) & (F.c.page_number == O.c.first_observed_page)
                 & (F.c.persistence_status == "committed")))
      .where(O.c.application_id.in_(app_ids), O.c.first_observed_at <= instant,
             V.c.first_observed_at <= instant)).mappings().all()
    exclusions = {app_id: Counter() for app_id in app_ids}
    latest = {app_id: {} for app_id in app_ids}
    for row in rows:
        reason = run_reasons.get(row["run_id"], None if row["run_id"] in snapshots else "RUN_NOT_FINISHED_BY_CUTOFF")
        if reason is None and (row["observation_at"] > instant or row["version_at"] > instant):
            reason = "OBSERVATION_AFTER_CUTOFF"
        if reason is None and row["detecting_run_id"] not in snapshots:
            reason = "VERSION_ORIGIN_NOT_ELIGIBLE"
        if reason is None and row["persistence_status"] != "committed":
            reason = "COMMITTED_PAGE_REQUIRED"
        if reason is None and row["conflict_count"]:
            reason = "CONFLICTED_OBSERVATION"
        if reason:
            exclusions[row["application_id"]][reason] += 1
            continue
        rank = (row["version_number"], runs[row["run_id"]]["finished_at"], str(row["run_id"]))
        prior = latest[row["application_id"]].get(row["review_id"])
        if prior is None or rank > prior[0]:
            latest[row["application_id"]][row["review_id"]] = rank, row
    summaries, selected, double_ids = [], [], []
    for item in frame:
        app = apps[item.source_application_id]
        candidates = latest[app["id"]]
        # Unambiguous seed+internal identity serialization; version, text, length
        # and rating never influence within-app selection or tie-breaking.
        order = sorted(candidates, key=lambda review_id: (
            hashlib.sha256(_json([seed, app["id"], review_id]).encode("utf-8")).digest(), review_id))
        chosen = order[:per_app]
        summaries.append(dict(application_id=app["id"], source_application_id=item.source_application_id,
            name=item.name, analytical_category=item.analytical_category, eligible=len(order),
            selected=len(chosen), assessed=0, unassessed=len(chosen), usefulness_rate=None,
            shortfall=max(0, per_app - len(chosen)), exclusion_counts=dict(exclusions[app["id"]])))
        for review_id in chosen:
            row = candidates[review_id][1]
            selected.append(dict(application_id=app["id"], source_application_id=item.source_application_id,
                analytical_category=item.analytical_category, review_id=review_id,
                version_id=row["observed_version_id"], version_number=row["version_number"],
                observed_run_id=str(row["run_id"]), title=row["title"], body=row["body"]))
        double_ids.extend(chosen[:2])
    sample = dict(schema_version=SAMPLE_SCHEMA, query_version=QUERY_VERSION, rubric_version=RUBRIC_VERSION,
        assessment_type="pending_human", run_mode=mode.value, evidence_kind=mode.value, cutoff=_iso(instant), sampling_seed=seed,
        per_app=per_app, apps=summaries, records=selected,
        totals=dict(eligible=sum(app["eligible"] for app in summaries), selected=len(selected), assessed=0,
            unassessed=len(selected), usefulness_rate=None, shortfall=sum(app["shortfall"] for app in summaries)),
        double_review=dict(status="optional_pending_human", requested_per_app=2, target=16,
            selected_review_ids=double_ids, selected=len(double_ids), shortfall=16 - len(double_ids), agreement_rate=None))
    sample["manifest_id"] = _manifest_id(sample)
    return sample


def pending_labels(sample):
    """Create empty responses; never claim an actual human read or assessment."""
    _validate_sample(sample)
    records = [dict(schema_version=LABEL_SCHEMA, manifest_id=sample["manifest_id"], rubric_version=RUBRIC_VERSION,
        review_id=row["review_id"], version_id=row["version_id"], reviewer_id=None, assessed_at=None,
        language=None, full_text_read=False, label=None, reason=None, assessment_type="pending_human",
        provenance="pending_human", ai_assistance=None, unassessed_reason="PENDING_HUMAN") for row in sample["records"]]
    return dict(schema_version=LABEL_SCHEMA, manifest_id=sample["manifest_id"], rubric_version=RUBRIC_VERSION,
                run_mode=sample["run_mode"], evidence_kind=sample["run_mode"], assessment_type="pending_human", records=records)


def _validate_labels(sample, labels):
    _validate_sample(sample)
    if type(labels) is not dict or set(labels) != {"schema_version", "manifest_id", "rubric_version", "run_mode", "evidence_kind", "assessment_type", "records"}:
        raise AssessmentError("INVALID_LABEL_ENVELOPE")
    if (labels["schema_version"] != LABEL_SCHEMA or labels["manifest_id"] != sample["manifest_id"]
            or labels["rubric_version"] != RUBRIC_VERSION or labels["run_mode"] != sample["run_mode"]
            or labels["evidence_kind"] != sample["evidence_kind"]
            or type(labels["records"]) is not list):
        raise AssessmentError("LABEL_MANIFEST_MISMATCH")
    membership = {row["review_id"]: row for row in sample["records"]}
    seen, kinds = set(), set()
    for row in labels["records"]:
        if type(row) is not dict or set(row) != _LABEL_KEYS:
            raise AssessmentError("INVALID_LABEL_FIELDS")
        review_id = row["review_id"]
        if type(review_id) is not int or review_id not in membership or type(row["version_id"]) is not int or row["version_id"] != membership[review_id]["version_id"]:
            raise AssessmentError("LABEL_MEMBERSHIP_MISMATCH")
        if review_id in seen:
            raise AssessmentError("DUPLICATE_REVIEW_LABEL")
        seen.add(review_id)
        if row["schema_version"] != LABEL_SCHEMA or row["manifest_id"] != sample["manifest_id"] or row["rubric_version"] != RUBRIC_VERSION:
            raise AssessmentError("LABEL_MANIFEST_MISMATCH")
        if type(row["full_text_read"]) is not bool:
            raise AssessmentError("FULL_TEXT_CONFIRMATION_REQUIRED")
        for key in ("reviewer_id", "language", "reason"):
            if row[key] is not None and not _text(row[key]):
                raise AssessmentError("INVALID_LABEL_METADATA")
        if row["assessed_at"] is not None:
            try:
                if type(row["assessed_at"]) is not str:
                    raise ValueError
                _aware(datetime.fromisoformat(row["assessed_at"].replace("Z", "+00:00")))
            except (TypeError, ValueError):
                raise AssessmentError("AWARE_ASSESSMENT_TIME_REQUIRED") from None
        if row["label"] is None:
            if (row["assessment_type"] != "pending_human" or row["provenance"] != "pending_human"
                    or type(row["unassessed_reason"]) is not str
                    or row["unassessed_reason"] not in _UNASSESSED or row["ai_assistance"] is not None):
                raise AssessmentError("INVALID_PENDING_ASSESSMENT")
            continue
        kind = row["assessment_type"]
        if (type(row["label"]) is not str or row["label"] not in RUBRIC or type(kind) is not str or kind not in {"human", "synthetic_test"}
                or row["provenance"] != kind or row["ai_assistance"] is not False):
            raise AssessmentError("HUMAN_PROVENANCE_REQUIRED")
        if kind == "synthetic_test" and sample["run_mode"] != "synthetic":
            raise AssessmentError("SYNTHETIC_LABELS_CANNOT_ASSESS_LIVE")
        if not row["full_text_read"] or any(row[key] is None for key in ("reviewer_id", "assessed_at", "language", "reason")) or row["unassessed_reason"] is not None:
            raise AssessmentError("COMPLETE_HUMAN_ASSESSMENT_REQUIRED")
        kinds.add(kind)
    if len(kinds) > 1:
        raise AssessmentError("MIXED_ASSESSMENT_PROVENANCE")
    kind = next(iter(kinds), "pending_human")
    if labels["assessment_type"] != kind:
        raise AssessmentError("ASSESSMENT_PROVENANCE_MISMATCH")
    return labels["records"], kind


def summarize_assessment(sample, labels):
    """Validate declarations/membership, aggregate usefulness without private text.

    Missing records and language/full-read limitations remain unassessed. The
    denominator is assessed unique reviews; an initial pending rate is null.
    Synthetic-test rates validate mechanics and are not human study results.
    """
    rows, kind = _validate_labels(sample, labels)
    by_review = {row["review_id"]: row for row in rows if row["label"] is not None}
    membership = {row["review_id"]: row for row in sample["records"]}

    def aggregate(apps):
        app_ids = {app["application_id"] for app in apps}
        assessed = [row for review_id, row in by_review.items() if membership[review_id]["application_id"] in app_ids]
        counts = {label: sum(row["label"] == label for row in assessed) for label in RUBRIC}
        selected = sum(app["selected"] for app in apps)
        return dict(eligible=sum(app["eligible"] for app in apps), selected=selected, assessed=len(assessed),
            unassessed=selected-len(assessed), shortfall=sum(app["shortfall"] for app in apps), label_counts=counts,
            useful=counts["U2"] + counts["U3"],
            usefulness_rate=(counts["U2"] + counts["U3"]) / len(assessed) if assessed else None,
            human_assessed=len(assessed) if kind == "human" else 0,
            synthetic_test_assessed=len(assessed) if kind == "synthetic_test" else 0)
    apps = [dict(application_id=app["application_id"], source_application_id=app["source_application_id"],
        analytical_category=app["analytical_category"], exclusion_counts=app["exclusion_counts"], **aggregate([app])) for app in sample["apps"]]
    categories = {category: aggregate([app for app in sample["apps"] if app["analytical_category"] == category])
                  for category in sorted({app["analytical_category"] for app in sample["apps"]})}
    unassessed = Counter(row["unassessed_reason"] for row in rows if row["label"] is None)
    absent = sample["totals"]["selected"] - len(rows)
    if absent:
        unassessed["MISSING_RESPONSE"] += absent
    return dict(schema_version="apple-assessment-summary/1", manifest_id=sample["manifest_id"],
        rubric_version=RUBRIC_VERSION, run_mode=sample["run_mode"], evidence_kind=sample["run_mode"], assessment_type=kind,
        overall=aggregate(sample["apps"]), apps=apps, categories=categories,
        unassessed_reasons=dict(unassessed), sentiment_assessment="NOT_PERFORMED",
        double_review=dict(selected=sample["double_review"]["selected"], human_pairs_assessed=0,
                           agreement_rate=None, status="second_reviewer_not_supplied"))


def compare_double_review(sample, primary_labels, secondary_labels):
    """Optional independently supplied second responses on the fixed subset.

    This checks declarations only. No actual-human agreement is reported for
    fixture labels; no agreement is manufactured from pending/one-reviewer data.
    """
    primary, first_kind = _validate_labels(sample, primary_labels)
    secondary, second_kind = _validate_labels(sample, secondary_labels)
    selected = set(sample["double_review"]["selected_review_ids"])
    first = {row["review_id"]: row for row in primary if row["label"] is not None and row["review_id"] in selected}
    second = {row["review_id"]: row for row in secondary if row["label"] is not None and row["review_id"] in selected}
    pairs = sorted(first.keys() & second.keys())
    if any(first[key]["reviewer_id"] == second[key]["reviewer_id"] for key in pairs):
        raise AssessmentError("INDEPENDENT_SECOND_REVIEWER_REQUIRED")
    actual = first_kind == second_kind == "human"
    agreed = sum(first[key]["label"] == second[key]["label"] for key in pairs)
    return dict(selected=len(selected), assessed_pairs=len(pairs), human_pairs_assessed=len(pairs) if actual else 0,
        assessment_type="human" if actual and pairs else "synthetic_test" if pairs else "pending_human",
        agreement_rate=agreed / len(pairs) if actual and pairs else None,
        disagreements=[key for key in pairs if first[key]["label"] != second[key]["label"]],
        adjudication="pending" if agreed < len(pairs) else "not_required" if pairs else "pending_human")


def _reading_html(sample):
    sections = []
    for row in sample["records"]:
        title = "(no title)" if row["title"] is None else row["title"]
        sections.append(f'<article><h2>Review {row["review_id"]} / version {row["version_id"]}</h2>'
            f'<h3>{html.escape(title)}</h3><pre>{html.escape(row["body"])}</pre></article>')
    return ('<!doctype html><html><head><meta charset="utf-8">'
        '<meta http-equiv="Content-Security-Policy" content="default-src &#39;none&#39;; style-src &#39;unsafe-inline&#39;">'
        '<title>Private human assessment — pending</title><style>body{max-width:70em;margin:2em auto;'
        'font-family:sans-serif}pre{white-space:pre-wrap;overflow-wrap:anywhere}article{border-top:1px solid #888}</style>'
        '</head><body><h1>Private human assessment — pending</h1><p>Run mode: '
        + html.escape(sample["run_mode"]) + '. Read each complete title/body. Language or reading limitations '
        'remain unassessed. U2/U3 indicate usefulness; no sentiment assessment is requested.</p><dl>'
        + ''.join(f'<dt>{key}</dt><dd>{html.escape(value)}</dd>' for key, value in RUBRIC.items())
        + '</dl>' + ''.join(sections) + '</body></html>')


def export_assessment(sample, output_dir):
    """Create a new private 0700 directory outside Git; 0600/no-overwrite files.

    Returns absolute paths for manifest, reading_material, responses, rubric.
    No network, database writes or actual human labels are produced.
    """
    _validate_sample(sample)
    target = Path(output_dir)
    payloads = {
        "manifest": ("sample-manifest.json", _json(sample) + "\n"),
        "reading_material": ("reading-material.html", _reading_html(sample)),
        "responses": ("responses.pending.json", _json(pending_labels(sample)) + "\n"),
        "rubric": ("rubric.json", _json(dict(rubric_version=RUBRIC_VERSION, evidence_kind=sample["run_mode"],
            run_mode=sample["run_mode"], criteria=RUBRIC,
            useful_labels=["U2", "U3"], sentiment_assessment="NOT_PERFORMED")) + "\n"),
    }
    parent_fd, directory_fd, created = None, None, False
    written = []
    try:
        if not target.is_absolute() or ".." in target.parts or target == _REPOSITORY or _REPOSITORY in target.parents:
            raise ValueError
        if any((parent / ".git").is_file() or (parent / ".git" / "HEAD").is_file() for parent in target.parents):
            raise ValueError
        parent_fd = os.open("/", os.O_RDONLY | os.O_DIRECTORY)
        for part in target.parent.parts[1:]:
            next_fd = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent_fd)
            os.close(parent_fd)
            parent_fd = next_fd
        os.mkdir(target.name, 0o700, dir_fd=parent_fd)
        created = True
        directory_fd = os.open(target.name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent_fd)
        info = os.fstat(directory_fd)
        if info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o700:
            raise ValueError
        for filename, content in payloads.values():
            fd = os.open(filename, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=directory_fd)
            written.append(filename)
            try:
                pending = memoryview(content.encode("utf-8"))
                while pending:
                    count = os.write(fd, pending)
                    if count <= 0:
                        raise OSError
                    pending = pending[count:]
                os.fsync(fd)
            finally:
                os.close(fd)
        os.fsync(directory_fd)
        os.fsync(parent_fd)
        return {key: str(target / filename) for key, (filename, _) in payloads.items()}
    except Exception:
        if created:
            try:
                for filename in written:
                    os.unlink(filename, dir_fd=directory_fd)
                os.rmdir(target.name, dir_fd=parent_fd)
            except OSError:
                pass
        raise AssessmentError("PRIVATE_EXPORT_FAILED") from None
    finally:
        if directory_fd is not None:
            os.close(directory_fd)
        if parent_fd is not None:
            os.close(parent_fd)

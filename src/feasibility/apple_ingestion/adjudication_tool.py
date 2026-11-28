"""Focused human adjudication of the nineteen flagged first-round reviews."""

import argparse
from collections import Counter, defaultdict
from copy import copy, deepcopy
from datetime import datetime, timezone
from hashlib import sha256
from http.server import HTTPServer
import json
import os
from pathlib import Path
import secrets
import shutil
import tempfile

from .annotation_tool import (
    AnnotationError, AnnotationStore, Conflict, atomic_json, make_handler, private_path,
)


GROUPS = {
    "evidence_context": (1, "证据的情感上下文"),
    "target_evidence_coverage": (1, "证据的情感上下文"),
    "transport_quality_boundary": (2, "车辆与服务环境的分类边界"),
    "mixed_target_granularity": (3, "Mixed 目标范围"),
    "zero_aspect_threshold": (4, "零方面判断"),
    "rationale_overreach": (5, "理由或目标的原文依据"),
    "software_service_boundary": (6, "软件与交易归因"),
    "aspect_coverage": (7, "方面覆盖"),
}
CHOICES = ("confirm", "modify", "requires_guideline_change")


def digest(value):
    return sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                             separators=(",", ":")).encode()).hexdigest()


def source_form(record):
    return dict(language=record["language"], annotation_status=record["annotation_status"],
                no_aspect_reason=record["no_aspect_reason"] or "",
                aspects=deepcopy(record["aspects"]), language_verified=False,
                outside_competence=False, evidence_confirmed=False, notes="")


def label_content(record):
    return {name: record[name] for name in
            ("language", "annotation_status", "no_aspect_reason", "aspects")}


def aggregate(records, rows):
    """Recompute descriptive results while retaining review-level grouping."""
    matrix = defaultdict(Counter)
    applications = {}
    categories = {}
    for record, row in zip(records, rows):
        for aspect in record["aspects"]:
            matrix[aspect["aspect"]][aspect["sentiment"]] += 1
        for groups, key in ((applications, row["app_name"]), (categories, row["category"])):
            group = groups.setdefault(key, dict(reviews=0, entries=0, aspects=Counter(),
                                                sentiments=Counter(), statuses=Counter()))
            group["reviews"] += 1
            group["entries"] += len(record["aspects"])
            group["aspects"].update(a["aspect"] for a in record["aspects"])
            group["sentiments"].update(a["sentiment"] for a in record["aspects"])
            group["statuses"].update([record["annotation_status"]])
    return dict(review_count=len(records), aspect_entries=sum(len(r["aspects"]) for r in records),
                aspect_bearing_reviews=sum(bool(r["aspects"]) for r in records),
                multi_entry_reviews=sum(len(r["aspects"]) > 1 for r in records),
                statuses=Counter(r["annotation_status"] for r in records),
                languages=Counter(r["language"] for r in records),
                sentiments=Counter(a["sentiment"] for r in records for a in r["aspects"]),
                aspect_sentiment=matrix, by_application=applications, by_category=categories)


class AdjudicationStore(AnnotationStore):
    def __init__(self, sample_dir, schema_path, guidelines_path):
        if not (Path(sample_dir) / "annotation-progress.json").is_file():
            raise AnnotationError("Existing completed round-one progress is required.")
        # The original tool's lock prevents simultaneous edits to round-one progress.
        super().__init__(sample_dir, schema_path)
        try:
            self.guidelines_path = Path(guidelines_path)
            self.original_state = deepcopy(self.state)
            self.all_rows = self.rows
            self.original_bytes = (self.root / "annotations-export-3.json").read_bytes()
            self.original = json.loads(self.original_bytes)
            self.audit_bytes = (self.root / "annotation-analysis-private.json").read_bytes()
            self.audit = json.loads(self.audit_bytes)
            if self.original != self.original_state["records"]:
                raise AnnotationError("Round-one export differs from its saved progress.")
            if not all(r["workflow_status"] == "complete" for r in self.original):
                raise AnnotationError("Round one must contain eighty completed records.")
            self.source_paths = {
                **{name: self.root / name for name in self.audit["input_sha256"]},
                "annotation-analysis-private.json": self.root / "annotation-analysis-private.json",
            }
            for name, expected in self.audit["input_sha256"].items():
                if sha256(self.source_paths[name].read_bytes()).hexdigest() != expected:
                    raise AnnotationError("An audited source file has changed.")
            self.source_hashes = {name: sha256(path.read_bytes()).hexdigest()
                                  for name, path in self.source_paths.items()}
            self.binding.update(original_export_sha256=sha256(self.original_bytes).hexdigest(),
                                audit_sha256=sha256(self.audit_bytes).hexdigest(),
                                guidelines_sha256=sha256(self.guidelines_path.read_bytes()).hexdigest())
            questions = defaultdict(list)
            for issue in self.audit["audit_issues"]:
                if issue["issue"] not in GROUPS:
                    raise AnnotationError("An audit question has no defined review group.")
                for reference in issue["references"]:
                    number = reference["sample_number"]
                    if type(number) is not int or not 1 <= number <= 80:
                        raise AnnotationError("Invalid audit sample reference.")
                    row = self.all_rows[number - 1]
                    if any(reference[name] != row[name] for name in
                           ("source_application_id", "review_id", "version_id")):
                        raise AnnotationError("Audit reference differs from the frozen sample.")
                    entry = reference["aspect_entry_number"]
                    if entry is not None and (type(entry) is not int
                            or not 1 <= entry <= len(self.original[number - 1]["aspects"])):
                        raise AnnotationError("Audit aspect reference is invalid.")
                    questions[number].append(dict(issue=issue["issue"], note=issue["note"],
                                                  aspect_entry_number=entry))
            if len(questions) != 19:
                raise AnnotationError("This round requires exactly nineteen flagged reviews.")
            self.numbers = sorted(questions, key=lambda n:
                                  (min(GROUPS[q["issue"]][0] for q in questions[n]), n))
            self.rows = [self.all_rows[n - 1] for n in self.numbers]
            self.queue = [
                dict(sample_number=n, parent_sha256=digest(self.original[n - 1]),
                     original_annotation=deepcopy(self.original[n - 1]),
                     title=self.all_rows[n - 1]["title"], body=self.all_rows[n - 1]["body"],
                     questions=questions[n],
                     groups=sorted({GROUPS[q["issue"]][0] for q in questions[n]}))
                for n in self.numbers
            ]
            self.work = self.root / "adjudication-v1"
            self.work.mkdir(mode=0o700, exist_ok=True)
            private_path(self.work)
            self.preserve_original()
            queue_path = self.work / "queue-private.json"
            queue_document = dict(binding=self.binding, reviews=self.queue)
            if queue_path.exists():
                private_path(queue_path)
                if json.loads(queue_path.read_bytes()) != queue_document:
                    raise AnnotationError("Saved adjudication queue differs from its bound inputs.")
            else:
                atomic_json(queue_path, queue_document)
                queue_path.chmod(0o400)
            self.path = self.work / "adjudication-progress.json"
            if self.path.exists():
                private_path(self.path)
                self.state = json.loads(self.path.read_bytes())
            else:
                self.state = dict(binding=self.binding, revision=0, cursor=0, drafts={},
                                  records=[self.pending(r) for r in self.rows], decisions={})
                atomic_json(self.path, self.state)
            self.validate_state()
            self.validate_decisions()
        except BaseException:
            self.close()
            raise

    def preserve_original(self):
        destination = self.work / "round1-original.json"
        if destination.exists():
            private_path(destination)
            if destination.read_bytes() != self.original_bytes:
                raise AnnotationError("Historical round-one snapshot differs from its source.")
            return
        fd, temporary = tempfile.mkstemp(prefix=".history-", dir=self.work)
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(self.original_bytes)
                handle.flush()
                os.fsync(handle.fileno())
                os.fchmod(handle.fileno(), 0o400)
            os.replace(temporary, destination)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)

    def verify_inputs(self):
        super().verify_inputs()
        if any(sha256(path.read_bytes()).hexdigest() != self.source_hashes[name]
               for name, path in self.source_paths.items()):
            raise AnnotationError("Original annotation or audit input changed.")
        if sha256(self.guidelines_path.read_bytes()).hexdigest() != self.binding["guidelines_sha256"]:
            raise AnnotationError("Frozen guidelines changed. A new version requires review.")
        if (self.work / "round1-original.json").read_bytes() != self.original_bytes:
            raise AnnotationError("Historical snapshot changed.")
        if json.loads((self.work / "queue-private.json").read_bytes()) != dict(binding=self.binding, reviews=self.queue):
            raise AnnotationError("Frozen review queue changed.")

    def snapshot(self):
        result = super().snapshot()
        result["drafts"] = {str(i): source_form(q["original_annotation"])
                            for i, q in enumerate(self.queue)}
        result["drafts"].update(self.state["drafts"])
        result["adjudication"] = dict(
            reviews=self.queue, decisions=self.state["decisions"],
            groups={str(number): title for number, title in GROUPS.values()},
            frozen=(self.work / "gold-v1").exists(), original_review_count=80,
        )
        return result

    def validate_decisions(self):
        for key, decision in self.state["decisions"].items():
            if key not in {str(i) for i in range(19)}:
                raise AnnotationError("Invalid adjudication reference.")
            index = int(key)
            if (decision["choice"] not in (*CHOICES, "")
                    or not isinstance(decision["reason"], str)
                    or decision["parent_sha256"] != self.queue[index]["parent_sha256"]):
                raise AnnotationError("Invalid adjudication decision.")
            if decision["status"] == "draft":
                if decision["reviewer_id"] is not None or decision["completed_at"] is not None:
                    raise AnnotationError("Draft decision has final reviewer metadata.")
                if self.state["records"][index]["workflow_status"] != "pending":
                    raise AnnotationError("Draft decision has a completed annotation.")
                continue
            if not decision["reviewer_id"] or not decision["reason"].strip():
                raise AnnotationError("Submitted adjudication requires reviewer and reason.")
            try:
                datetime.fromisoformat(decision["completed_at"].replace("Z", "+00:00"))
            except (TypeError, ValueError):
                raise AnnotationError("Invalid adjudication timestamp.") from None
            if not decision["completed_at"].endswith("Z"):
                raise AnnotationError("Adjudication requires a UTC timestamp.")
            record = self.state["records"][index]
            if decision["choice"] == "requires_guideline_change":
                if decision["status"] != "guideline_change_required" or record["workflow_status"] != "pending":
                    raise AnnotationError("A guideline proposal cannot apply labels.")
                continue
            if decision["status"] != "resolved" or record["workflow_status"] != "complete":
                raise AnnotationError("Unresolved adjudication.")
            original = self.queue[index]["original_annotation"]
            same = label_content(record) == label_content(original)
            if same != (decision["choice"] == "confirm"):
                raise AnnotationError("Keep and modify decisions must match the actual label differences.")
            if (record["reviewer_id"], record["annotated_at"]) != (decision["reviewer_id"], decision["completed_at"]):
                raise AnnotationError("Adjudication metadata differs from its reviewed record.")
        for i, record in enumerate(self.state["records"]):
            if record["workflow_status"] == "complete" and str(i) not in self.state["decisions"]:
                raise AnnotationError("Completed adjudication has no decision.")

    def save(self, payload):
        self.verify_inputs()
        if (self.work / "gold-v1").exists():
            raise AnnotationError("Gold v1 is frozen. Further changes require a new dataset version.")
        if payload.get("revision") != self.state["revision"]:
            raise Conflict("Newer progress exists. Reload before reviewing.")
        index = payload.get("index")
        if type(index) is not int or not 0 <= index < 19:
            raise AnnotationError("Only the nineteen flagged reviews can be adjudicated.")
        form = payload.get("form")
        self.validate_form(form)
        decision = payload.get("decision")
        if (not isinstance(decision, dict) or set(decision) != {"choice", "reason"}
                or decision["choice"] not in (*CHOICES, "")
                or not isinstance(decision["reason"], str)):
            raise AnnotationError("Select an adjudication action and enter its reason.")
        if payload.get("action") not in ("draft", "submit"):
            raise AnnotationError("Invalid adjudication action.")
        record = self.pending(self.rows[index])
        decision = dict(decision, status="draft", parent_sha256=self.queue[index]["parent_sha256"],
                        reviewer_id=None, completed_at=None)
        if payload["action"] == "submit":
            if any(d["status"] == "guideline_change_required" for k, d in self.state["decisions"].items()
                   if k != str(index)):
                raise AnnotationError("A guideline-change proposal is awaiting review. Adjudication is paused.")
            reviewer = payload.get("reviewer")
            if not isinstance(reviewer, str) or not reviewer.strip() or not decision["reason"].strip():
                raise AnnotationError("Actual reviewer identity and adjudication reason are required.")
            reviewers = {d["reviewer_id"] for d in self.state["decisions"].values()
                         if d["reviewer_id"] is not None}
            if reviewers and reviewers != {reviewer.strip()}:
                raise AnnotationError("Use the same adjudicator identity for this review round.")
            if decision["choice"] not in CHOICES:
                raise AnnotationError("Choose keep, modify or guideline change explicitly.")
            decision.update(reviewer_id=reviewer.strip(),
                            completed_at=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"))
            if decision["choice"] == "requires_guideline_change":
                decision["status"] = "guideline_change_required"
            else:
                record.update(workflow_status="complete", language=form["language"],
                              annotation_status=form["annotation_status"], aspects=form["aspects"],
                              no_aspect_reason=form["no_aspect_reason"] or None,
                              reviewer_id=decision["reviewer_id"], annotated_at=decision["completed_at"])
                self.validate_record(record, index)
                self.validate_confirmations(record, form)
                same = label_content(record) == label_content(self.queue[index]["original_annotation"])
                if same != (decision["choice"] == "confirm"):
                    raise AnnotationError("Keep requires unchanged labels; modify requires an actual correction.")
                decision["status"] = "resolved"
        updated = deepcopy(self.state)
        updated["drafts"][str(index)] = form
        updated["decisions"][str(index)] = decision
        updated["records"][index] = record
        updated["cursor"] = index
        updated["revision"] += 1
        previous = self.state
        self.state = updated
        try:
            self.validate_state()
            self.validate_decisions()
            atomic_json(self.path, updated)
        except BaseException:
            self.state = previous
            raise
        return dict(revision=updated["revision"], record=record, decision=decision)

    def export(self, revision):
        """Freeze one complete eighty-record Gold dataset after human review."""
        self.verify_inputs()
        if revision != self.state["revision"]:
            raise Conflict("Newer decisions exist. Reload before freezing.")
        self.validate_state()
        self.validate_decisions()
        if len(self.state["decisions"]) != 19 or any(
                d["status"] != "resolved" for d in self.state["decisions"].values()):
            raise AnnotationError("All nineteen decisions must be resolved under frozen v1 before Gold can freeze.")
        records = deepcopy(self.original)
        decisions = []
        for i, number in enumerate(self.numbers):
            decision = dict(self.state["decisions"][str(i)], sample_number=number,
                            source_application_id=self.rows[i]["source_application_id"],
                            source_review_id=self.rows[i]["source_review_id"],
                            review_id=self.rows[i]["review_id"], version_id=self.rows[i]["version_id"])
            if decision["choice"] == "modify":
                records[number - 1] = deepcopy(self.state["records"][i])
            decision["result_sha256"] = digest(records[number - 1])
            decisions.append(decision)
        checker = copy(self)
        checker.rows = self.all_rows
        for i, record in enumerate(records):
            checker.validate_record(record, i)
            if i + 1 not in self.numbers and record != self.original[i]:
                raise AnnotationError("An unflagged review changed.")
        if len(records) != 80:
            raise AnnotationError("Gold dataset must retain eighty reviews.")
        contents = {
            "annotations.json": records,
            "adjudication-decisions.json": decisions,
            "aggregate-results.json": aggregate(records, self.all_rows),
        }
        destination = self.work / "gold-v1"
        if destination.exists():
            manifest = json.loads((destination / "manifest.json").read_bytes())
            if manifest["binding"] != self.binding or manifest["progress_revision"] != revision:
                raise AnnotationError("Existing Gold freeze differs from this review revision.")
            for name, expected in contents.items():
                if (json.loads((destination / name).read_bytes()) != expected
                        or sha256((destination / name).read_bytes()).hexdigest() != manifest["files_sha256"][name]):
                    raise AnnotationError("Frozen Gold content changed.")
            return dict(filename="adjudication-v1/gold-v1/annotations.json", records=records)
        temporary = Path(tempfile.mkdtemp(prefix=".gold-", dir=self.work))
        try:
            for name, value in contents.items():
                atomic_json(temporary / name, value)
                (temporary / name).chmod(0o400)
            manifest = dict(dataset_version="apple-absa-gold/v1", binding=self.binding,
                            source_files_sha256=self.source_hashes,
                            guideline_version="apple-absa-guidelines/v1",
                            annotation_schema_version="apple-absa-annotation/v1",
                            progress_revision=revision, review_count=80,
                            adjudicated_review_count=19, unflagged_review_count=61,
                            frozen_at=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                            validation=dict(schema=True, parent_versions=True, original_slices=True,
                                            completed_decisions=True, unflagged_records_preserved=True,
                                            semantic_human_confirmation=True),
                            files_sha256={name: sha256((temporary / name).read_bytes()).hexdigest()
                                          for name in contents})
            atomic_json(temporary / "manifest.json", manifest)
            (temporary / "manifest.json").chmod(0o400)
            temporary.rename(destination)
        finally:
            if temporary.exists():
                shutil.rmtree(temporary)
        return dict(filename="adjudication-v1/gold-v1/annotations.json", records=records)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sample-dir", required=True, type=Path)
    parser.add_argument("--port", type=int, default=8766)
    parser.add_argument("--prepare-only", action="store_true")
    args = parser.parse_args(argv)
    repo = Path(__file__).resolve().parents[3]
    store = AdjudicationStore(args.sample_dir, repo / "docs/APPLE_ABSA_ANNOTATION_SCHEMA.md",
                              repo / "docs/APPLE_ABSA_ANNOTATION_GUIDELINES.md")
    try:
        if args.prepare_only:
            print("Prepared 19 private review items within the frozen 80-review sample.")
            return
        page = Path(__file__).with_name("annotation_tool.html").read_bytes()
        token = secrets.token_urlsafe(32)
        with HTTPServer(("127.0.0.1", args.port), make_handler(store, token, page)) as server:
            print(f"Open http://127.0.0.1:{server.server_port}/#{token}", flush=True)
            try:
                server.serve_forever()
            except KeyboardInterrupt:
                pass
    finally:
        store.close()


if __name__ == "__main__":
    main()

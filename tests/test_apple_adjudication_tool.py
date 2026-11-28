"""Synthetic human-review decisions; the real sample is never changed."""

from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import unittest

from feasibility.apple_ingestion.adjudication_tool import AdjudicationStore
from feasibility.apple_ingestion.annotation_tool import AnnotationError, atomic_json
import test_apple_annotation_tool as annotation_tests


SCHEMA = annotation_tests.SCHEMA
GUIDELINES = SCHEMA.with_name("APPLE_ABSA_ANNOTATION_GUIDELINES.md")


class AdjudicationTests(unittest.TestCase):
    def setUp(self):
        self.fixture = annotation_tests.AnnotationTests()
        self.fixture.setUp()
        self.root = self.fixture.root
        form = self.fixture.valid_form()
        for index in range(80):
            self.fixture.save(deepcopy(form), "submit", index=index, reviewer="synthetic-original")
        original = deepcopy(self.fixture.store.state["records"])
        self.fixture.store.close()
        atomic_json(self.root / "annotations-export-3.json", original)
        names = ("sample-private.json", "manifest-private.json",
                 "annotation-progress.json", "annotations-export-3.json")
        refs = [dict(sample_number=i + 1, source_application_id=r["source_application_id"],
                     review_id=r["review_id"], version_id=r["version_id"], aspect_entry_number=1)
                for i, r in enumerate(original[:19])]
        atomic_json(self.root / "annotation-analysis-private.json",
                    dict(input_sha256={name: sha256((self.root / name).read_bytes()).hexdigest()
                                       for name in names},
                         audit_issues=[dict(issue="evidence_context",
                                            note="Synthetic review question.", references=refs)]))
        self.source = {p.name: p.read_bytes() for p in self.root.iterdir() if p.is_file()}
        self.store = AdjudicationStore(self.root, SCHEMA, GUIDELINES)

    def tearDown(self):
        self.store.close()
        self.fixture.tearDown()

    def submit(self, index=0, choice="confirm", form=None, action="submit", reason="Human checked the source."):
        if form is None:
            form = self.store.snapshot()["drafts"][str(index)]
            form.update(language_verified=True, evidence_confirmed=True)
        return self.store.save(dict(index=index, revision=self.store.state["revision"],
                                    action=action, form=form, reviewer="synthetic-adjudicator",
                                    decision=dict(choice=choice, reason=reason)))

    def test_queue_is_exact_and_pending(self):
        snapshot = self.store.snapshot()
        self.assertEqual(len(snapshot["rows"]), 19)
        self.assertEqual(snapshot["adjudication"]["original_review_count"], 80)
        self.assertTrue(all(r["workflow_status"] == "pending" for r in snapshot["records"]))
        self.assertEqual(snapshot["adjudication"]["decisions"], {})
        self.assertTrue(all(not f["language_verified"] for f in snapshot["drafts"].values()))
        self.assertEqual((self.store.work / "round1-original.json").read_bytes(),
                         self.source["annotations-export-3.json"])
        self.assertEqual((self.store.work / "round1-original.json").stat().st_mode & 0o777, 0o400)
        with self.assertRaises(AnnotationError):
            self.store.export(0)
        self.assertFalse((self.store.work / "gold-v1").exists())

    def test_keep_all_freezes_eighty_with_history(self):
        for index in range(19):
            self.submit(index)
        revision = self.store.state["revision"]
        result = self.store.export(revision)
        self.assertEqual(result["records"], json.loads(self.source["annotations-export-3.json"]))
        decisions = json.loads((self.store.work / "gold-v1/adjudication-decisions.json").read_bytes())
        self.assertEqual(len(decisions), 19)
        self.assertTrue(all(d["reviewer_id"] == "synthetic-adjudicator" and d["completed_at"].endswith("Z")
                            for d in decisions))
        manifest = json.loads((self.store.work / "gold-v1/manifest.json").read_bytes())
        self.assertEqual(manifest["review_count"], 80)
        self.assertEqual(manifest["unflagged_review_count"], 61)
        self.assertEqual(self.store.export(revision), result)
        with self.assertRaises(AnnotationError):
            self.submit()
        for name, original_bytes in self.source.items():
            self.assertEqual((self.root / name).read_bytes(), original_bytes)
        aggregate = json.loads((self.store.work / "gold-v1/aggregate-results.json").read_bytes())
        self.assertEqual(aggregate["aspect_entries"], 80)

    def test_changes_require_modify_and_valid_evidence(self):
        form = self.store.snapshot()["drafts"]["0"]
        form.update(language_verified=True, evidence_confirmed=True)
        form["aspects"][0]["reason"] = "Human clarified the rationale."
        with self.assertRaises(AnnotationError):
            self.submit(form=form)
        record = self.submit(form=form, choice="modify")["record"]
        self.assertEqual(record["aspects"][0]["reason"], "Human clarified the rationale.")
        form["aspects"][0]["evidence"][0]["start"] += 1
        previous = self.store.path.read_bytes()
        with self.assertRaises(AnnotationError):
            self.submit(form=form, choice="modify")
        self.assertEqual(self.store.path.read_bytes(), previous)

    def test_modified_gold_preserves_unflagged_and_confirmed(self):
        for index in range(19):
            self.submit(index)
        form = self.store.snapshot()["drafts"]["0"]
        form["aspects"][0]["reason"] = "More precise human rationale."
        self.submit(choice="modify", form=form)
        records = self.store.export(self.store.state["revision"])["records"]
        old = json.loads(self.source["annotations-export-3.json"])
        self.assertEqual(records[1:], old[1:])
        self.assertEqual(records[0]["review_id"], old[0]["review_id"])
        self.assertEqual(records[0]["version_id"], old[0]["version_id"])
        self.assertNotEqual(records[0], old[0])

    def test_guideline_change_records_proposal_and_pauses(self):
        result = self.submit(choice="requires_guideline_change", reason="A category definition needs review.")
        self.assertEqual(result["record"]["workflow_status"], "pending")
        self.assertEqual(result["decision"]["status"], "guideline_change_required")
        with self.assertRaises(AnnotationError):
            self.submit(index=1)
        with self.assertRaises(AnnotationError):
            self.store.export(self.store.state["revision"])
        self.assertFalse((self.store.work / "gold-v1").exists())

    def test_resume_and_reason_requirement(self):
        with self.assertRaises(AnnotationError):
            self.submit(reason="")
        self.submit(action="draft", reason="Draft review note.")
        self.store.close()
        self.store = AdjudicationStore(self.root, SCHEMA, GUIDELINES)
        self.assertEqual(self.store.state["decisions"]["0"]["status"], "draft")
        self.assertIsNone(self.store.state["decisions"]["0"]["reviewer_id"])
        self.assertEqual(self.store.state["records"][0]["workflow_status"], "pending")
        self.submit()
        self.assertEqual(self.store.state["records"][0]["workflow_status"], "complete")

    def test_source_changes_block_decisions(self):
        (self.root / "annotations-export-3.json").write_text("[]")
        with self.assertRaises(AnnotationError):
            self.submit()


if __name__ == "__main__":
    unittest.main()

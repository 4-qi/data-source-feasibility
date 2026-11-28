"""Synthetic-only checks for the private annotation interface."""

from copy import deepcopy
import hashlib
from http.client import HTTPConnection
import json
from pathlib import Path
import socket
from socketserver import UnixStreamServer
import tempfile
from threading import Thread
import unittest

from feasibility.apple_ingestion.annotation_tool import (
    AnnotationError, AnnotationStore, Conflict, make_handler,
)

SCHEMA = Path(__file__).resolve().parents[1] / "docs/APPLE_ABSA_ANNOTATION_SCHEMA.md"


class AnnotationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        rows = [dict(source="apple_app_store", source_application_id="001",
                     source_review_id=f"0{i}", review_id=str(i + 1),
                     version_id=str(i + 101), version_number="2",
                     language_status="unknown", title=None, body="😀 Cafe\u0301\r\nNo ads!",
                     app_name="Synthetic app", category="productivity",
                     sample_rank=i + 1, stage=1 if i < 20 else 2,
                     rating=5, previous_label="U3") for i in range(80)]
        raw = json.dumps(rows, ensure_ascii=False).encode()
        (self.root / "sample-private.json").write_bytes(raw)
        manifest = dict(sample_id="synthetic", dataset_id="synthetic",
                        sample_count=80, sample_sha256=hashlib.sha256(raw).hexdigest(),
                        review_version_keys=[[r["source_application_id"], r["review_id"], r["version_id"]]
                                             for r in rows])
        (self.root / "manifest-private.json").write_text(json.dumps(manifest))
        for path in self.root.iterdir():
            path.chmod(0o600)
        self.store = AnnotationStore(self.root, SCHEMA)

    def tearDown(self):
        self.store.close()
        self.temporary.cleanup()

    def form(self):
        return dict(language="", annotation_status=None, no_aspect_reason="", aspects=[],
                    language_verified=False, outside_competence=False,
                    evidence_confirmed=False, notes="")

    def valid_form(self):
        form = self.form()
        form.update(language="en", language_verified=True, evidence_confirmed=True,
                    annotation_status="annotated",
                    aspects=[dict(aspect="pricing", target_domain="app", target="ads",
                                  sentiment="positive", reason="Explicitly favorable absence.",
                                  evidence=[dict(field="body", start=10, end=17, text="No ads!")])])
        # Offsets follow the exact original Unicode sequence.
        body = self.store.rows[0]["body"]
        start = body.index("No ads!")
        form["aspects"][0]["evidence"][0].update(start=start, end=start + len("No ads!"))
        return form

    def save(self, form, action="draft", index=0, reviewer="human"):
        return self.store.save(dict(index=index, revision=self.store.state["revision"],
                                    form=form, action=action, reviewer=reviewer))

    def test_initial_export_and_rating_blind_api(self):
        snapshot = self.store.snapshot()
        self.assertNotIn("rating", snapshot["rows"][0])
        self.assertNotIn("previous_label", snapshot["rows"][0])
        self.assertEqual(snapshot["rows"][0]["body"], "😀 Cafe\u0301\r\nNo ads!")
        self.assertEqual(len(snapshot["records"]), 80)
        exported = self.store.export(0)
        self.assertTrue(all(r["workflow_status"] == "pending" and r["reviewer_id"] is None
                            and r["annotated_at"] is None for r in exported["records"]))
        for path in self.root.iterdir():
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)

    def test_draft_resume_submission_and_reopen(self):
        form = self.valid_form()
        self.save(form)
        self.assertEqual(self.store.state["records"][0]["aspects"], [])
        self.store.close()
        self.store = AnnotationStore(self.root, SCHEMA)
        self.assertEqual(self.store.state["drafts"]["0"], form)
        result = self.save(form, "submit")
        record = result["record"]
        self.assertEqual(record["version_id"], "101")
        self.assertEqual(record["reviewer_id"], "human")
        self.assertTrue(record["annotated_at"].endswith("Z"))
        self.assertEqual(record["aspects"], form["aspects"])
        self.assertEqual(self.store.export(result["revision"])["records"][0], record)
        form["notes"] = "Revising"
        self.save(form)
        self.assertEqual(self.store.state["records"][0]["workflow_status"], "pending")

    def test_invalid_submissions_do_not_change_progress(self):
        original = self.store.path.read_bytes()
        invalid = []
        form = self.valid_form()
        for key in ("language_verified", "evidence_confirmed"):
            changed = deepcopy(form)
            changed[key] = False
            invalid.append(changed)
        changed = deepcopy(form)
        changed["aspects"][0]["evidence"][0]["start"] += 1
        invalid.append(changed)
        changed = deepcopy(form)
        changed["aspects"][0]["sentiment"] = "invented"
        invalid.append(changed)
        changed = deepcopy(form)
        changed["aspects"][0]["evidence"][0]["field"] = "title"
        invalid.append(changed)
        changed = deepcopy(form)
        changed["language"] = "ru"
        invalid.append(changed)
        for bad in invalid:
            with self.subTest(form=bad), self.assertRaises(AnnotationError):
                self.save(bad, "submit")
            self.assertEqual(self.store.path.read_bytes(), original)

    def test_zero_aspect_and_language_rules(self):
        form = self.form()
        form.update(language="en", language_verified=True,
                    annotation_status="no_identifiable_aspect", no_aspect_reason="Generic response.")
        self.save(form, "submit")
        form.update(language="ru", annotation_status="language_out_of_scope",
                    no_aspect_reason="Verified Russian is outside my competence.")
        with self.assertRaises(AnnotationError):
            self.save(form, "submit")
        form["outside_competence"] = True
        self.save(form, "submit")
        form["language"] = "und"
        with self.assertRaises(AnnotationError):
            self.save(form, "submit")

    def test_stale_tabs_lock_and_input_mutation(self):
        self.save(self.form())
        with self.assertRaises(Conflict):
            self.store.save(dict(index=0, revision=0, form=self.form(), action="draft"))
        with self.assertRaises(BlockingIOError):
            AnnotationStore(self.root, SCHEMA)
        (self.root / "manifest-private.json").write_text("{}")
        with self.assertRaises(AnnotationError):
            self.store.export(self.store.state["revision"])

    def test_provenance_tampering_is_rejected(self):
        self.save(self.valid_form(), "submit")
        self.store.state["records"][0]["version_id"] = "9999"
        with self.assertRaises(AnnotationError):
            self.store.export(self.store.state["revision"])

    def test_http_auth_and_origin(self):
        socket_path = str(self.root / "http-test.socket")
        server = UnixStreamServer(socket_path, make_handler(self.store, "secret", b"<html>Local</html>"))
        server.server_port = 0
        def connect():
            connection = HTTPConnection("127.0.0.1", 0)
            connection.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            connection.sock.connect(socket_path)
            return connection
        thread = Thread(target=server.serve_forever)
        thread.start()
        try:
            connection = connect()
            connection.request("GET", "/api/state")
            self.assertEqual(connection.getresponse().status, 403)
            connection.close()
            connection = connect()
            connection.request("GET", "/api/state", headers={"X-Annotation-Token": "secret",
                                                            "Origin": "https://outside.example"})
            self.assertEqual(connection.getresponse().status, 403)
            connection.close()
            connection = connect()
            connection.request("GET", "/api/state", headers={"X-Annotation-Token": "secret"})
            response = connection.getresponse()
            self.assertEqual(response.status, 200)
            self.assertEqual(len(json.loads(response.read())["records"]), 80)
            connection.close()
        finally:
            server.shutdown()
            thread.join()
            server.server_close()


if __name__ == "__main__":
    unittest.main()

"""Private, loopback-only human annotation for a frozen ABSA sample."""

import argparse
from copy import deepcopy
from datetime import datetime, timezone
import fcntl
from hashlib import sha256
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import os
from pathlib import Path
import re
import secrets
import stat
import tempfile
from urllib.parse import urlsplit

from jsonschema import Draft202012Validator, FormatChecker


IDENTITY = ("source", "source_application_id", "source_review_id", "review_id",
            "version_id", "version_number", "language_status")
FORM_FIELDS = {"language", "annotation_status", "no_aspect_reason", "aspects",
               "language_verified", "outside_competence", "evidence_confirmed", "notes"}
CONFIRMATIONS = ("language_verified", "outside_competence", "evidence_confirmed")


class AnnotationError(ValueError):
    """Validation error suitable for the local interface."""


class Conflict(AnnotationError):
    """Another view has saved newer progress."""


def read_schema(path):
    blocks = re.findall(r'```json\n(.*?)\n```', path.read_text(encoding="utf-8"), re.S)
    schema = json.loads(blocks[0])
    Draft202012Validator.check_schema(schema)
    return schema


def atomic_json(path, value):
    """Replace a private file only after the complete new image is on disk."""
    fd, temporary = tempfile.mkstemp(prefix=".annotation-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(value, handle, ensure_ascii=False, indent=2, allow_nan=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def private_path(path):
    if path.is_symlink() or stat.S_IMODE(path.stat().st_mode) & 0o077:
        raise AnnotationError("Private files require owner-only permissions.")


class AnnotationStore:
    def __init__(self, sample_dir, schema_path):
        self.root = Path(sample_dir).resolve(strict=True)
        private_path(self.root)
        if any((parent / ".git").is_file() or (parent / ".git" / "HEAD").is_file()
               for parent in (self.root, *self.root.parents)):
            raise AnnotationError("Sample storage must be outside a Git checkout.")
        self.schema = read_schema(Path(schema_path))
        self.schema_path = Path(schema_path)
        self.validator = Draft202012Validator(self.schema, format_checker=FormatChecker())
        for name in ("manifest-private.json", "sample-private.json"):
            private_path(self.root / name)
        self.manifest_bytes = (self.root / "manifest-private.json").read_bytes()
        self.manifest = json.loads(self.manifest_bytes)
        self.sample_bytes = (self.root / "sample-private.json").read_bytes()
        if sha256(self.sample_bytes).hexdigest() != self.manifest["sample_sha256"]:
            raise AnnotationError("Frozen sample checksum mismatch.")
        self.rows = json.loads(self.sample_bytes)
        keys = [[row["source_application_id"], row["review_id"], row["version_id"]]
                for row in self.rows]
        if (len(self.rows) != 80 or self.manifest["sample_count"] != 80
                or keys != self.manifest["review_version_keys"]
                or len({tuple(key) for key in keys}) != 80):
            raise AnnotationError("Frozen sample identity mismatch.")
        self.binding = {
            "sample_sha256": sha256(self.sample_bytes).hexdigest(),
            "manifest_sha256": sha256(self.manifest_bytes).hexdigest(),
            "schema_sha256": sha256(Path(schema_path).read_bytes()).hexdigest(),
        }
        self.path = self.root / "annotation-progress.json"
        lock_path = self.root / "annotation-progress.lock"
        fd = os.open(lock_path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
        self.lock = os.fdopen(fd, "r+")
        try:
            private_path(lock_path)
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            if self.path.exists():
                private_path(self.path)
                self.state = json.loads(self.path.read_bytes())
                self.validate_state()
            else:
                self.state = dict(binding=self.binding, revision=0, cursor=0, drafts={},
                                  records=[self.pending(row) for row in self.rows])
                atomic_json(self.path, self.state)
        except BaseException:
            self.lock.close()
            raise

    def close(self):
        self.lock.close()

    def verify_inputs(self):
        paths = {"sample_sha256": self.root / "sample-private.json",
                 "manifest_sha256": self.root / "manifest-private.json",
                 "schema_sha256": self.schema_path}
        if any(sha256(path.read_bytes()).hexdigest() != self.binding[name]
               for name, path in paths.items()):
            raise AnnotationError("Frozen sample, manifest or schema changed. Stop and check the input files.")

    def pending(self, row):
        return dict(
            schema_version="apple-absa-annotation/v1",
            guideline_version="apple-absa-guidelines/v1",
            dataset_id=self.manifest["dataset_id"], sample_id=self.manifest["sample_id"],
            **{name: row[name] for name in IDENTITY},
            language=None, workflow_status="pending", annotation_status=None,
            no_aspect_reason=None, aspects=[], reviewer_id=None, annotated_at=None,
        )

    def validate_record(self, record, index):
        if list(self.validator.iter_errors(record)):
            raise AnnotationError("Annotation does not match the frozen JSON Schema.")
        row = self.rows[index]
        parent = self.pending(row)
        for name in (*IDENTITY, "dataset_id", "sample_id", "schema_version", "guideline_version"):
            if record[name] != parent[name]:
                raise AnnotationError("Review/version reference differs from the frozen sample.")
        if record["workflow_status"] == "pending":
            if record != parent:
                raise AnnotationError("Pending export records must contain no final labels.")
            return
        for name in ("language", "reviewer_id"):
            if not record[name] or not record[name].strip():
                raise AnnotationError("Language and reviewer identity are required.")
        if not record["annotated_at"] or not record["annotated_at"].endswith("Z"):
            raise AnnotationError("Completion time must be an actual UTC timestamp.")
        language = record["language"]
        if not re.fullmatch(r"[a-z]{2,3}(?:-[A-Za-z0-9]{2,8})*", language):
            raise AnnotationError("Enter a language tag such as en, en-US, es or ru.")
        english = language == "en" or language.startswith("en-")
        status = record["annotation_status"]
        if status == "language_out_of_scope":
            if english or language in ("und", "mul"):
                raise AnnotationError("Out-of-scope status requires a confirmed non-English language.")
        elif not english:
            raise AnnotationError("Non-English or unresolved language must remain a draft.")
        if status == "annotated":
            if not record["aspects"] or record["no_aspect_reason"] is not None:
                raise AnnotationError("Annotated records require aspects and no exclusion reason.")
        elif status is None or record["aspects"] or not (record["no_aspect_reason"] or "").strip():
            raise AnnotationError("A zero-aspect status requires a reason and no aspect entries.")
        targets = set()
        for aspect in record["aspects"]:
            if not aspect["target"].strip() or not aspect["reason"].strip():
                raise AnnotationError("Each aspect requires a target and rationale.")
            target = (aspect["aspect"], aspect["target_domain"], aspect["target"])
            if target in targets:
                raise AnnotationError("Merge repeated aspect/target entries or describe distinct targets.")
            targets.add(target)
            for span in aspect["evidence"]:
                original = row[span["field"]]
                if (not isinstance(original, str)
                        or not 0 <= span["start"] < span["end"] <= len(original)
                        or original[span["start"]:span["end"]] != span["text"]):
                    raise AnnotationError("Evidence must match exact original Unicode code-point offsets.")

    def validate_form(self, form):
        if not isinstance(form, dict) or form.keys() != FORM_FIELDS:
            raise AnnotationError("Unexpected draft fields.")
        if (not all(type(form[name]) is bool for name in CONFIRMATIONS)
                or not all(isinstance(form[name], str) for name in
                           ("language", "no_aspect_reason", "notes"))
                or not isinstance(form["aspects"], list)):
            raise AnnotationError("Invalid draft values.")
        statuses = self.schema["properties"]["annotation_status"]["enum"]
        if form["annotation_status"] not in statuses:
            raise AnnotationError("Invalid review status.")

    def validate_confirmations(self, record, form):
        self.validate_form(form)
        if not form["language_verified"]:
            raise AnnotationError("Confirm human language verification before submission.")
        if record["annotation_status"] == "language_out_of_scope" and not form["outside_competence"]:
            raise AnnotationError("Confirm the language is outside your competence.")
        if record["aspects"] and not form["evidence_confirmed"]:
            raise AnnotationError("Confirm evidence and sentiment, including both directions of mixed entries.")
        for name in ("language", "annotation_status", "aspects"):
            if record[name] != form[name]:
                raise AnnotationError("Completed record differs from its submitted form.")
        if record["no_aspect_reason"] != (form["no_aspect_reason"] or None):
            raise AnnotationError("Completed reason differs from its submitted form.")

    def validate_state(self):
        state = self.state
        if (state["binding"] != self.binding or len(state["records"]) != len(self.rows)
                or type(state["revision"]) is not int or state["revision"] < 0
                or type(state["cursor"]) is not int or not 0 <= state["cursor"] < len(self.rows)):
            raise AnnotationError("Saved progress does not match this frozen sample/schema.")
        for key, form in state["drafts"].items():
            if key not in {str(i) for i in range(len(self.rows))}:
                raise AnnotationError("Invalid saved draft identity.")
            self.validate_form(form)
        for index, record in enumerate(state["records"]):
            self.validate_record(record, index)
            if record["workflow_status"] == "complete":
                self.validate_confirmations(record, state["drafts"][str(index)])

    def snapshot(self):
        # Whitelist the fields displayed to annotators. Ratings never enter the API.
        return dict(
            revision=self.state["revision"], cursor=self.state["cursor"],
            sample_id=self.manifest["sample_id"],
            rows=[{name: row[name] for name in
                   (*IDENTITY, "app_name", "sample_rank", "stage", "title", "body")}
                  for row in self.rows],
            records=self.state["records"], drafts=self.state["drafts"],
            enums=dict(aspect=self.schema["$defs"]["aspect"]["properties"]["aspect"]["enum"],
                       target_domain=self.schema["$defs"]["aspect"]["properties"]["target_domain"]["enum"],
                       sentiment=self.schema["$defs"]["aspect"]["properties"]["sentiment"]["enum"],
                       annotation_status=[s for s in self.schema["properties"]["annotation_status"]["enum"]
                                          if s is not None]),
        )

    def save(self, payload):
        self.verify_inputs()
        if payload.get("revision") != self.state["revision"]:
            raise Conflict("Newer progress exists. Reload this page before editing.")
        index = payload.get("index")
        if type(index) is not int or not 0 <= index < len(self.rows):
            raise AnnotationError("Invalid review index.")
        form = payload.get("form")
        self.validate_form(form)
        action = payload.get("action")
        if action not in ("draft", "submit"):
            raise AnnotationError("Invalid save action.")
        updated = deepcopy(self.state)
        updated["drafts"][str(index)] = form
        record = self.pending(self.rows[index])
        if action == "submit":
            reviewer = payload.get("reviewer")
            if not isinstance(reviewer, str) or not reviewer.strip():
                raise AnnotationError("Enter your reviewer identity before submitting.")
            reviewers = {r["reviewer_id"] for r in self.state["records"]
                         if r["workflow_status"] == "complete"}
            if reviewers and reviewers != {reviewer.strip()}:
                raise AnnotationError("This progress file belongs to a different reviewer.")
            record.update(language=form["language"], workflow_status="complete",
                          annotation_status=form["annotation_status"],
                          no_aspect_reason=form["no_aspect_reason"] or None,
                          aspects=form["aspects"], reviewer_id=reviewer.strip(),
                          annotated_at=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"))
            self.validate_record(record, index)
            self.validate_confirmations(record, form)
        # Editing a completed record returns it to pending until resubmitted.
        updated["records"][index] = record
        updated["cursor"] = index
        updated["revision"] += 1
        atomic_json(self.path, updated)
        self.state = updated
        return dict(revision=updated["revision"], record=record)

    def export(self, revision):
        self.verify_inputs()
        if revision != self.state["revision"]:
            raise Conflict("Newer progress exists. Reload before exporting.")
        self.validate_state()
        # Every row is exported. Draft fields never become final pending labels.
        records = deepcopy(self.state["records"])
        path = self.root / f"annotations-export-{self.state['revision']}.json"
        atomic_json(path, records)
        return dict(filename=path.name, records=records)


def make_handler(store, token, page):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass

        def respond(self, status, body, content_type="application/json"):
            raw = body if isinstance(body, bytes) else json.dumps(body, ensure_ascii=False).encode()
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(raw)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Security-Policy",
                             "default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; "
                             "connect-src 'self'; img-src 'self' data:; frame-ancestors 'none'; base-uri 'none'")
            self.end_headers()
            self.wfile.write(raw)

        def authorized(self):
            expected = f"127.0.0.1:{self.server.server_port}"
            if self.headers.get("Host") != expected:
                return False
            if self.headers.get("Origin") not in (None, "http://" + expected):
                return False
            return secrets.compare_digest(self.headers.get("X-Annotation-Token", ""), token)

        def do_GET(self):
            if urlsplit(self.path).path == "/" and self.headers.get("Host") == f"127.0.0.1:{self.server.server_port}":
                self.respond(200, page, "text/html; charset=utf-8")
            elif self.path == "/api/state" and self.authorized():
                self.respond(200, store.snapshot())
            else:
                self.respond(403, {"error": "Access denied."})

        def do_POST(self):
            if not self.authorized():
                self.respond(403, {"error": "Access denied."})
                return
            try:
                size = int(self.headers.get("Content-Length", "0"))
                if not 0 < size <= 2_000_000:
                    raise AnnotationError("Request size is invalid.")
                payload = json.loads(self.rfile.read(size))
                if not isinstance(payload, dict):
                    raise AnnotationError("Expected a JSON object.")
                if self.path == "/api/save":
                    result = store.save(payload)
                elif self.path == "/api/export":
                    result = store.export(payload.get("revision"))
                else:
                    raise AnnotationError("Unknown operation.")
                self.respond(200, result)
            except Conflict as error:
                self.respond(409, {"error": str(error)})
            except AnnotationError as error:
                self.respond(400, {"error": str(error)})
            except (ValueError, TypeError, KeyError):
                self.respond(400, {"error": "Validation failed. Check language, status, reviewer, aspects and original evidence."})
            except OSError:
                self.respond(500, {"error": "Private save failed. Keep this page open and retry."})

    return Handler


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sample-dir", required=True, type=Path)
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--schema-path", type=Path)
    args = parser.parse_args(argv)
    repo = Path(__file__).resolve().parents[3]
    store = AnnotationStore(args.sample_dir, args.schema_path or repo / "docs/APPLE_ABSA_ANNOTATION_SCHEMA.md")
    try:
        token = secrets.token_urlsafe(32)
        page = Path(__file__).with_name("annotation_tool.html").read_bytes()
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

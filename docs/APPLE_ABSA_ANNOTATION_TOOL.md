# Local ABSA Annotation Tool

The local browser interface reads the frozen eighty-review sample and the
JSON Schema in [the annotation contract](APPLE_ABSA_ANNOTATION_SCHEMA.md).
Follow the [frozen guidelines](APPLE_ABSA_ANNOTATION_GUIDELINES.md).
Every aspect, language decision and rationale is entered by a human.

## Launch and resume

Run from the repository root using Python 3.10+ with `jsonschema` 4.10+.
The workstation's system `python3` already supplies that dependency.
For another environment, install the project's optional `annotation` extra.
Set `PRIVATE_ABSA_SAMPLE_DIR` to the existing private frozen sample directory.

```sh
PYTHONPATH=src python3 -m feasibility.apple_ingestion.annotation_tool \
  --sample-dir "$PRIVATE_ABSA_SAMPLE_DIR"
```

Open the complete local URL printed by the command, including its fragment.
The server binds to `127.0.0.1` on port 8765. Use `--port 0` to select
an available port when that port is occupied. Keep the command running while
using the page. Stop it with Ctrl+C. Repeat the same command and sample
directory to resume saved work. Each start prints a new access URL.
For an installed package outside this checkout, pass `--schema-path`
pointing to the frozen Markdown schema document.

One process locks the private progress file. Multiple tabs detect stale
revisions and require a reload before further changes. Use one progress
directory for one consistent reviewer. Independent reviewer work requires
a separate private copy of the complete frozen sample directory with its
own progress files.

## Annotate

1. Enter the actual reviewer identity. It is written to a final record only
   when a submission succeeds. Re-enter that same identity after reopening.
2. Select the first-twenty stage or the remaining-sixty stage. Read the
   complete original title and body. The interface omits star ratings and
   previous usefulness labels from its data response.
3. Verify language manually and enter its language tag. Confirm the language
   checkbox. Mixed or unresolved languages stay in draft. A confirmed
   non-English out-of-scope record also requires confirmation that the
   language is outside the reviewer's competence and a reason.
4. Select the review status. For `annotated`, add one or more aspect entries
   and enter category, target domain, target, sentiment and rationale.
   All choices initially remain unselected.
5. Select exact original text in the title or body and click the evidence
   button for the intended aspect. Repeat for discontinuous or mixed
   evidence. The interface converts browser UTF-16 positions to Unicode
   code points. The server validates the exact original substring.
6. For a zero-aspect status, remove aspect entries and supply its reason.
   Confirm evidence and sentiment for aspect-bearing records. Click the
   submission button to complete the record with the server's actual UTC
   time. Human confirmation establishes the truth of the decisions.

Drafts autosave after a short input pause. The explicit draft-save button
flushes pending changes. Wait for the saved indicator before closing.
Navigation flushes the current draft first. Closing during an unfinished
save triggers a browser warning. Incomplete typed work lives separately
from final records. Editing a completed record returns it to pending
until it is submitted again. Progress counts submitted records.

## Private storage and export

All application writes remain in the selected private sample directory.

| File | Purpose |
| --- | --- |
| `annotation-progress.json` | Drafts, final records, last edited position and input bindings |
| `annotation-progress.lock` | Prevents simultaneous writers |
| `annotations-export-<revision>.json` | Explicitly requested, validated export |

Click the export button to validate all records and write an eighty-element
JSON array in the private directory. Each element follows
`apple-absa-annotation/v1`. Completed records retain their labels.
Pending records contain null final fields and an empty aspect array.
Draft notes and incomplete labels remain in progress storage.
The interface reports the export filename and creates no browser download.

The tool checks the frozen sample checksum, manifest review/version sequence,
exact parent identities, Schema, workflow status, language confirmations,
reviewer consistency and evidence offsets. Export revalidates all records.
Source sample, manifest and Schema changes invalidate the running session.
Review text, evidence and annotations stay private. The server serves only
the interface and authenticated annotation operations, with no directory
browsing, database access, external services or external page assets.
Files use mode 0600 within the existing mode-0700 directory.

Automated validation checks structural consistency and exact evidence
location. A human remains responsible for aspect meaning, sentiment,
language competence and whether a mixed entry contains both directions.
Retain all original sample files when backing up progress privately.

## Verification

Synthetic tests cover empty pending exports, rating-blind responses, atomic
draft saves, restart/resume, submission timestamps, Unicode evidence,
zero-aspect and language decisions, stale tabs, exclusive locking, source
changes, tampered version references and local request authentication.
Browser checks exercise the full workflow on synthetic reviews at desktop
and mobile widths.

```sh
PYTHONPATH=src python3 -m unittest discover -s tests \
  -p test_apple_annotation_tool.py -v
```

# Focused First-Round ABSA Adjudication

## Scope

This review covers the nineteen flagged reviews within the existing
eighty-review sample. The private audit supplies the exact review/version
references and question categories. An audit question invites a human
decision; the original labels remain the historical first-round record.

The local tool loads the frozen sample, original completed export,
first-round progress and private audit. It verifies their recorded hashes
and the original Schema before preparing the queue. A byte-identical
mode-0400 copy of the original export is stored with the queue.
The original annotation tool's lock prevents simultaneous edits during
adjudication.

## Launch and resume

Run from the repository root.
Set `PRIVATE_ABSA_SAMPLE_DIR` to the existing private frozen sample directory.

```sh
PYTHONPATH=src python3 -m feasibility.apple_ingestion.adjudication_tool \
  --sample-dir "$PRIVATE_ABSA_SAMPLE_DIR"
```

Open the complete local URL printed by the command. The interface listens
on `127.0.0.1:8766`. The same command restores saved review progress.
Use `--port 0` when an automatically selected free port is needed.
`--prepare-only` creates or verifies the private queue without serving it.

## Human review

The interface contains nineteen records. Each record displays its complete
original title and body, existing review status, aspects, evidence,
rationales and all associated audit questions. The original annotation
can be expanded separately while editing the adjudication form.
Structured star ratings and earlier usefulness labels remain hidden.

The queue is ordered by earliest applicable issue group and original
sample position. A review may appear under several group filters.

1. Evidence missing sentiment context, including partial target coverage.
2. Vehicle condition and service-environment classification boundaries.
3. Mixed-aspect target breadth.
4. Zero-aspect decisions.
5. Unsupported rationale or target interpretation.
6. Software versus transaction attribution.
7. Potentially omitted aspects.

For each record, enter the actual adjudicator identity and select one action.

| Action | Required human decision |
| --- | --- |
| Keep original annotation | Confirm the original label content as displayed and explain why it is supported. |
| Modify under frozen v1 | Edit aspects, sentiment, evidence, rationale, language or review status using existing v1 rules. Explain the correction. |
| Guideline change required | Describe the rule that would need redefining. The proposal is saved separately, and further adjudication and Gold freezing pause for discussion. |

No action is preselected. Existing labels populate the editing form as
historical annotations for review. Selecting keep requires the final label
content to equal the original. Selecting modify requires an actual change.
Use one consistent adjudicator identity for this round.

Read the complete source and original rationale before deciding. Confirm
language and evidence manually. Select exact source text and use the
existing evidence controls to add or replace spans. Multiple aspect entries
and zero-aspect decisions follow the frozen
[guidelines](APPLE_ABSA_ANNOTATION_GUIDELINES.md) and
[Schema](APPLE_ABSA_ANNOTATION_SCHEMA.md).

Each submitted decision requires a short reason. The server records the
actual adjudicator and UTC submission time. Draft decisions have no final
reviewer or completion time. Editing a submitted decision returns it to
draft until it is resubmitted. Automatic saving and the explicit draft
button preserve interruption/resumption.

A correction that applies an existing definition can retain v1. A changed
definition requires an explicit new-guideline decision before affected
labels are applied. The guideline-change action preserves the proposed
question without applying the edited labels. It blocks other submissions
until that question is resolved. Withdrawal in favor of an existing v1
interpretation requires a new explicit decision on the same record.

## Private artifacts

Files are under the existing sample directory's `adjudication-v1/` child.

| Artifact | Content |
| --- | --- |
| `round1-original.json` | Byte-identical read-only first-round export |
| `queue-private.json` | Nineteen original records, source text, parent hashes and audit questions |
| `adjudication-progress.json` | Separate drafts, decisions, reviewed records and revision counter |
| `gold-v1/annotations.json` | Frozen eighty-record adjudicated annotation array |
| `gold-v1/adjudication-decisions.json` | Nineteen decisions with original/result record hashes and exact source/version references |
| `gold-v1/aggregate-results.json` | Recalculated review, aspect, sentiment, language, app and category statistics |
| `gold-v1/manifest.json` | Gold version, frozen contracts, input hashes, output hashes, freeze time and validation summary |

The Gold files are created only after all nineteen human decisions are
resolved and the reviewer explicitly clicks the freeze button. Until then,
the dataset remains the original eighty plus a separate pending review
queue. The completed Gold array retains all eighty parent records and all
out-of-scope records. The sixty-one unflagged records retain their exact
original values. Confirmed records also retain their original annotation
metadata. Modified records carry the actual adjudicator and correction time;
their decision records identify the exact historical parent.

Gold v1 is published locally as one completed directory after validation,
with owner-read-only files and content hashes. Repeated freeze requests
verify the same output. Further edits require a new dataset version.
The original annotation-results report remains a historical first-round
summary; the new aggregate artifact describes the adjudicated snapshot.

## Validation and limits

Before each save and freeze, verify bound source files, frozen guidelines,
Schema, historical copy and review queue. Validate each submitted correction
against exact parent identity, version, enum values, language/status rules,
zero-aspect reason and original Unicode code-point evidence slices.
Require human language and evidence confirmations.

Freezing checks all eighty records, nineteen resolved decisions, parent
and result hashes, actual reviewer metadata and preservation of unflagged
records. It recalculates statistics from the resulting eighty-record array.
Aspect entries remain grouped under their parent reviews. Their total may
change after human corrections.

Human review determines whether a target is justified, whether evidence
supports polarity and whether a mixed target has a defensible scope.
Structural validation supplies consistency checks. A second independent
reviewer and agreement measurements remain separate from this adjudication.

Synthetic tests exercise keep, correction, evidence rejection, required
reasons, resume, guideline-change pause, source mutation checks, original
preservation and the complete eighty-record freeze.

```sh
PYTHONPATH=src:tests python3 -m unittest discover -s tests \
  -p test_apple_adjudication_tool.py -v
```

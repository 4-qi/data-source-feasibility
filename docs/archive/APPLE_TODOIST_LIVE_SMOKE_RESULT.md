# Todoist first live smoke result

**Decision: PASS — the technical chain is ready to enter a separately initiated
seven-day pilot. Phase F was not started.** This verifies Todoist's observed
window, not all eight applications, complete coverage or data-use rights.

- Baseline: `d5eefe333bf1bbe85c5d30ea5a364dc2ed320df1`; existing runbook executed once, with no implementation changes.
- Run ID: `e9cf632f-9c1a-45de-9b2f-fdf5e995211e`.
- Batch ID: `360bde73-ef0a-4e71-a195-dbad7b6cfdca`.
- Source/scope: Apple RSS, Todoist `572688855`, US, mostrecent.
- Run time: November 3, 2026, `13:04:22.675625Z`–`13:04:30.932972Z`.
- Status: `succeeded`; coverage `baseline`; stop reason `page_budget`.

| Actual result | Count |
| --- | ---: |
| Logical pages committed | 5 |
| HTTP requests / HTTP 200 responses | 5 / 5 |
| Automatic retries / XML fallback | 0 / 0 |
| Distinct reviews | 250 |
| Full-text review versions | 250, all version 1 |
| Review observations | 250 |
| Conflicts / duplicates | 0 / 0 |
| HTTP, transport, parsing or persistence errors | 0 |
| Recomputed fingerprint mismatches | 0 |
| Ownership / integrity issues | 0 |

All five requests were JSON pages 1–5, each returning 50 accepted reviews.
The existing limits remained five pages, ten HTTP requests, zero retries,
two-second transport spacing, 10/25-second connect/read timeouts, 2,000,000-byte
response cap and 900-second target deadline. No extra request was made to test
XML or repeat the collection.

All 250 titles/bodies were present and nonempty. Stored body lengths were
4–1,451 characters, totaling 60,600 characters; title lengths were 4–100.
Full text was read privately to recompute content/metadata fingerprints, never
printed or exported into this report. Observed-version ownership, current
pointers and version sequences passed the existing integrity report; all six
issue counters are zero. Every attempt is finished, parsed successfully and
committed. No unknown or unresolved attempt/persistence state remains.

The observed source-update range was `2025-12-16T17:08:16Z` to
`2026-11-01T13:13:50Z`. These are observed update times, not measured publication
latency. This first run establishes an eligible baseline; it does not prove
overlap sufficiency, edit capture or complete source coverage. Other apps, Atom
fallback and cross-day behavior remain matters for the actual pilot.

Cleanup succeeded: Todoist disabled, all eight targets disabled, Smoke project
disabled, pilot project still disabled. No scheduler was installed. Private
pre/post-run backups were created; the post-run dump is mode 0600, 102,141 bytes.
No stored title/body string of at least 20 characters was found in the private
server logs or safe reports during the performed scan. No raw responses or
review text were added to Git, and no administrative confirmation was fabricated.

Private metadata verification report:
`/home/l2838/.local/state/data-source-feasibility/smoke-runs/todoist-20261103T130421Z/verification-report.json`.
The same private operation directory retains the exact active technical scope,
one-invocation marker and safe SQL verification output. Full text remains only
in the private PostgreSQL data and private backup.

The immutable software label follows the existing runbook's content-digest
formula (`uncommitted-7c2432d07bd6c67b82a2`); the verified execution checkout was
the clean `d5eefe3` baseline. No code was changed to alter that label.
No commit or push was performed. Data-use/retention questions remain unresolved after this technical validation.

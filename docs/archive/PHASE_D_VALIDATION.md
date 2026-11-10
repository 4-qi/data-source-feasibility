# Phase D synthetic rehearsal and offline CLI validation

Status: **assigned Phase D work complete; final validation recorded
whole-suite acceptance**, November 3, 2026. This is synthetic engineering
evidence only. Phase C was accepted before this work began. The coordinating
chat owns final whole-project acceptance; this session stops at D.
No live RSS, other source, human labels, deployment, E/F, commits or pushes were
performed.

## Implementation and public interfaces

- `synthetic.rehearse(engine, output_dir, *, disposable=False,
  start_date=DEFAULT_START, software_revision=...)` returns a safe summary and
  output path. It requires the explicit disposable flag, an `apple_phase_a_`
  database reached through a private `/tmp` Unix socket, the exact migrated
  seven-table schema and no existing core rows. It refuses remote/service
  indirection, unsafe SQL logging, symbolic socket paths and existing outputs.
- `scenario_response(app_index, day, page, format)` deterministically supplies
  invented JSON/Atom bytes. `ScenarioSession` has no real HTTP implementation;
  real `BoundedTransport`, Controller, parser, normalizer and reconciler consume
  these fixtures. `SimulatedClock` advances without waiting real days.
- `python -m feasibility.apple_ingestion.cli` offers only `rehearse`, `report`
  and `assessment`. There is no live command. All require an explicit database
  URL, `--disposable` and a fresh `/tmp` output directory. No ambient/default DSN
  is used; `--help` never connects. CLI errors use fixed safe codes without
  credentials, bound review text or exception messages.
- `scripts/run_apple_ingestion_synthetic.sh` creates a new temporary PostgreSQL
  cluster, disables TCP, rejects host authentication, initializes the empty
  database explicitly, calls the CLI, then stops and removes only its cluster.
  It neither installs nor changes system services.

Reporting uses `reporting.batch_report(..., outcomes=...)` and
`integrity_report`; assessment uses `build_sample`, `pending_labels`,
`export_assessment` and `summarize_assessment`. Their logic is not duplicated in
the scenario generator. Full text appears only in the private assessment
subdirectory; routine reports never contain review IDs/text or alternate bodies.

## Seven-calendar-day protocol

The fixed fixture dates are **October 29–November 4, 2026**, at 09:00 each day in
America/Los_Angeles. They are simulated dates, not observed live collection
days. UTC conversion respects the DST change; one local day interval is 25
hours. There are **7 batch UUIDs and 56 planned app/day slots**, with no extra
diagnostic runs entering that denominator. Batch identities derive from the
protocol/start date; controller-generated run UUIDs identify this execution.
Scenario inputs and semantic results are deterministic, while execution UUIDs
mean repeated report bytes/checksums need not be identical.

All runs freeze the approved defaults: **2 minimum / 5 maximum logical pages,
20 distinct overlapping IDs AND 20% overlap, 10 physical requests, zero retry,
2-second global spacing**, plus the unchanged timeout/body/deadline settings.
No threshold is lowered for a small window.

| Application | Invented scenario behavior |
| --- | --- |
| Todoist | New visible IDs on later days, unchanged records, metadata change, full-text A → B → A with three retained versions. |
| Microsoft To Do | Twelve-record windows remain count-limited despite complete overlap; later app-version metadata change. |
| Duolingo | Fifty-record windows share only five IDs; low count and low ratio stay distinct. |
| Khan Academy | Missing JSON entry → XML fallback; later selected empty XML page yields a coverage caution but usable nonempty reference. |
| Amazon Shopping | One later-page 503 produces partial execution; a separate malformed first page produces failed execution. Later runs skip those references. |
| Etsy | Same-page duplicate plus later conflicting snapshot retains the first accepted text; another day has a duplicate-only coverage caution. |
| Uber | A prior identity disappears from later bounded windows but remains in database history; no deletion is inferred. |
| Lyft | Long Unicode full text is retained; one all-empty JSON/XML day does not become a reference or imply feed completion. |

## Reproduce

From the repository root, use the shared project environment and choose a fresh
output directory:

```bash
conda activate data-source-feasibility
task_artifact_parent=$(mktemp -d /tmp/apple-ingestion-phase-d-artifacts.XXXXXX)
bash scripts/run_apple_ingestion_synthetic.sh "$task_artifact_parent/rehearsal"
```

Without shell activation, the actual execution used:

```bash
task_artifact_parent=$(mktemp -d /tmp/apple-ingestion-phase-d-artifacts.XXXXXX)
PYTHONNOUSERSITE=1 APPLE_TEST_PYTHON=/home/l2838/miniconda3/envs/data-source-feasibility/bin/python bash scripts/run_apple_ingestion_synthetic.sh "$task_artifact_parent/rehearsal"
```

The managed sandbox requires reviewed permission for the private Unix socket.
The environment was Python 3.12.16, PostgreSQL 16.15 and the pinned project
dependencies. No additional dependency or `/tmp` Python installation was used.

## This session's actual retained rehearsal

Output root:
`/tmp/apple-ingestion-phase-d-artifacts.7KGpXp/rehearsal`

| Measured result | Count |
| --- | ---: |
| Planned / attempted / missing slots | 56 / 56 / 0 |
| Succeeded / partial / failed / interrupted | 53 / 2 / 1 / 0 |
| Simulated physical requests | 190 |
| Committed logical pages | 181 |
| Private assessment eligible / selected / shortfall | 992 / 80 / 0 |
| Human assessed / unassessed | 0 / 80 |
| Human usefulness rate | null |
| Integrity issue counts | All six zero |
| Pending attempts / pending terminal coverage | 0 / 0 |

The two partial and one failed outcomes are deliberate fixture cases retained
in the 56-slot denominator. They were not converted to successful execution or
removed from the report. No live request total or human utility rate is claimed.

Retained artifacts, all outside Git:

- `summary.json`: safe execution counts, paths, Python/PostgreSQL versions,
  software revision and source-file SHA-256 identities.
- `safe/protocol.json`: synthetic protocol, fixed dates, full frozen config,
  parser/hash versions, manifest hash and scenario limitations.
- `safe/day-01.json` through `safe/day-07.json`: per-day eight-target reports.
- `safe/integrity.json`: read-only integrity checks, all issue counts zero.
- `safe/assessment-pending.json`: aggregate pending-human assessment summary.
- `private-assessment/`: full-text sample manifest, reading HTML, blank pending
  responses and rubric. Ratings are not rendered in the first-pass reading
  material; no label or full-text-read confirmation is manufactured.
- `checksums.json`: SHA-256 for **15 artifacts**, excluding itself.

After execution this session independently rehashed all 15 indexed files:
all matched. Every JSON had top-level `evidence_kind='synthetic'`; all output
files were mode 0600. Safe JSON contained none of the synthetic title/body or
disputed-alternate sentinels. The private pending responses contain no actual
human assessment. No `apple-synthetic-pg.*` cluster directory remained after
the runner exited. These `/tmp` artifacts are retained local evidence, not a
permanent archive or committed repository deliverable.

## Tests actually executed

```bash
PYTHONNOUSERSITE=1 APPLE_TEST_PYTHON=/home/l2838/miniconda3/envs/data-source-feasibility/bin/python bash scripts/test_apple_ingestion_postgres.sh --full-suite tests/test_apple_ingestion_synthetic.py tests/test_apple_ingestion_cli.py -q --tb=short --junitxml=/tmp/phase-d-synthetic-cli-final.xml
```

Final result: **20 passed in 9.34 seconds**, **0 failed, 0 skipped, 0 warnings**.
JUnit: `/tmp/phase-d-synthetic-cli-final.xml`. Earlier staged validation was
19 passed before the real CLI success-path test was added, then 20 passed; the
final result above includes the finalized private-artifact evidence markers.

Meaningful checks include the complete seven-day real-PostgreSQL pipeline,
56 runs/seven batches, A/B/A version history, source absence without deletion,
long text, pending terminal-state queries, default thresholds, safe artifacts
and checksums, no output overwrite, local/disposable DB guard, DST conversion,
help/no-DB behavior, no live command and sanitized credential-bearing errors.
The actual CLI `report` and `assessment` commands also run against committed
fixture data: ten selected records remain unassessed, the seven other apps'
70-record shortfall remains visible, and usefulness rate stays null. Thus
successful command behavior is validated rather than only help/rejection paths.
All test execution used the existing Python TCP guard and PostgreSQL Unix socket.

Integration adjustments were limited to actual API alignment: pending-label
envelope use, recognition of real Git markers rather than an empty protected
`.git` directory, and the assessment owner's explicit synthetic artifact marker.
No core schema, reference, stop or reconciliation rule was changed by this work.

## Separate integration validation

A separate wrapper run was recorded at
`/tmp/apple-ingestion-phase-d-main-20261103`, with the same 56/56 slots,
53/2/1 execution distribution, 190 simulated requests, 181 committed pages,
zero integrity issues, 80 selected/zero human-assessed sample, and all 15
artifact checksums validated. This wrapper run is recorded separately from the retained execution and
20-test measurement above.

The final whole-suite result was:
**516 passed in 35.86 seconds**, **0 failed, 0 skipped, 0 warnings**, JUnit
`/tmp/apple-phase-d-main.xml`. This separate integration measurement supported final Phase D acceptance;
implementation stopped at that checkpoint.

Design, models and initial migration SHA-256 values still match the Phase C
review baseline. `git diff --check` passed. Branch remained `main`, HEAD
`474736abcee2a67f186299f09d196125400eb1ab`. This session made no Git commit/push
and stops with D; no E/F or live operation is initiated.

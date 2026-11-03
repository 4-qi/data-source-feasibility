# Apple ingestion pilot — implementation through Phase D

> Subsequent authorization: A–D passed external document-level review. Phase E
> preparation and offline validation are recorded separately in
> [the live-readiness report](PHASE_E_LIVE_READINESS.md). Historical counts and
> stop boundaries below describe the A–D delivery. No real RSS request or Phase F
> execution is authorized by that later preparation task.

**Review date:** November 3, 2026 (America/Los_Angeles).  
**Current state:** B, C and D accepted for synthetic engineering delivery; stopped for external review.  
**Baseline:** [approved design](APPLE_INGESTION_SYSTEM_DESIGN.md).

This is an engineering delivery report, not live-source or production acceptance.
The current authorization covers B, C and D using synthetic data and disposable
PostgreSQL. E/F, real Apple RSS collection, commits and pushes are outside scope.
The main coordinating chat owns integration and phase gates; the three independent
execution chats are identified in [Phase A delivery](PHASE_A_DELIVERY.md).

## Environment and preservation

Use the shared project Conda environment `data-source-feasibility`, Python
3.12.16, PostgreSQL 16.15, and the dependency versions in
`requirements/project-test.lock`. `PYTHONNOUSERSITE=1` isolates the environment
from unrelated user-site packages. There is no separate environment per phase.
All database checks use private temporary clusters with TCP disabled; these are
stopped and removed after execution. No existing service/database is reused.

The original feasibility evidence under `results/` and `research/`, the original
probes and tests, and existing uncommitted work are protected. The approved
schema remains seven core tables; `alembic_version` is migration bookkeeping.
The approved design, Phase A models and initial migration remain unchanged.
Final preservation and artifact checks are recorded below.

## Stage gates and measured results

| Gate | Main-chat verification | Outcome |
| --- | --- | --- |
| A, previous delivery | 228 passed, no failures/skips | Accepted before this task. |
| B | 336 passed, no failures/skips, 6.66 seconds | Accepted before C was dispatched. |
| C | 444 passed, no failures/skips, 21.93 seconds | Accepted with completed internal architecture review before D was dispatched. |
| D | 516 passed, no failures/skips/warnings, 35.86 seconds; seven-day synthetic rehearsal verified | Accepted; stop after D. |

B main-chat JUnit: `/tmp/apple-phase-b-main.xml`. C main-chat JUnit:
`/tmp/apple-phase-c-main.xml`. D main-chat JUnit: `/tmp/apple-phase-d-main.xml`. Those temporary files are execution artifacts;
[Phase B validation](PHASE_B_VALIDATION.md), [Phase C validation](PHASE_C_VALIDATION.md)
and [C architecture review](PHASE_C_ARCHITECTURE_REVIEW.md) preserve readable
commands, results, findings and evidence boundaries. Skipped tests without a
configured database do not count as real-PostgreSQL acceptance.

Full-suite reproduction in the activated project environment:

```sh
bash scripts/test_apple_ingestion_postgres.sh --full-suite -q
```

The runner's historical default Phase A behavior is preserved. `--full-suite`
discovers every maintained test without duplicate collection. New PostgreSQL
fixtures isolate each test in a migrated database, allowing genuine page
commits and rollbacks. The automatic test guard rejects Python IPv4/IPv6
connections and permits the PostgreSQL Unix socket. This is a test safeguard,
not an OS firewall or a claim about all possible external processes.

## Phase B — parsing, comparison and reconciliation

`parser.py` handles JSON and Atom through one ordered `ReviewRecord` contract.
It distinguishes a missing JSON entry member from a valid empty response and
an invalid envelope. Malformed review candidates fail the entire page. Known
catalog records are excluded by explicit structural rules; duplicate review IDs
retain their returned order. Authors are excluded. DTD/entities are rejected;
nested XML/XHTML or external content is explicitly unsupported and rejected
rather than silently losing text.

`normalizer.py` implements `apple-observed-v1`. Complete stored title/body remain
unaltered. Comparison normalizes CRLF/CR to LF and Unicode to NFC; fixed UTF-8
JSON encodings generate separate content and metadata SHA-256 values. Complete
canonical fields are compared alongside hashes. Null/empty values remain
separate, whitespace/case/entities are not silently collapsed, and equivalent
source timestamp offsets map to a fixed UTC representation.

`reconcile.py` accepts the already validated whole page and a dedicated locked
connection. It atomically persists identity, version, observation, diagnostics
and the selected attempt's committed marker. NEW creates V1; UNCHANGED still
records an observation; CHANGED appends N+1; A → B → A retains three observed
versions. Same-run duplicates increment occurrence counts; incompatible
occurrences mark the first committed snapshot disputed without another version.
No missing ID is inferred deleted. A committed page replay changes no counters.
A page failure rolls back the entire page while preserving earlier pages and
separately recording safe diagnostics. Bounded details retain exact totals.

## Phase C — control, attempts, references and recovery

`controller.py` runs sequential targets, commits request intent before invoking
the injected transport, persists response/parse metadata separately, and calls
B reconciliation on the same held application session. JSON-empty responses
get one XML fallback on the same logical page. Empty pages do not end the feed;
ordinary duplicates and blocking coverage cautions are distinguished. Page and
HTTP budgets remain separate. Default settings stay 2/5 pages, 20 overlapping
IDs AND 20% overlap, ten requests, zero retries and global spacing; explicit
valid target/snapshot configuration is preserved rather than silently replaced.
There is no automatic threshold relaxation. The controller rejects live mode.

`reference.py` selects the latest earlier successful, nonempty, internally
consistent, compatible comparison window. Its own insufficient overlap or
coverage-only caution does not disqualify it. Age above 72 hours warns, without
dropping valid evidence; exactly 72 hours does not warn. Initial anchors and
compatibility restarts retain explicit provenance. Execution, coverage and
comparison eligibility are independent. Low observable window size and low
measured overlap have separate nonexclusive reason codes; neither proves total
review population or complete collection.

`transport.py` requires an explicitly supplied session and does not create a
network session at import or construction. It fixes HTTPS/host/app routes,
discloses project headers, clears credentials/cookies, disables redirects and
retries, enforces global spacing and bounded streaming/timeouts/deadlines, and
returns safe error codes without response text in repr or diagnostics. All
executed sessions in this task are synthetic.

`recovery.py` holds a session advisory lock per application, pins the actual
backend/driver and refuses silent reconnection after loss. Recovery terminates
abandoned runs under that lock, preserves committed pages, retains unknown
request outcomes and starts a new run at page 1. A restricted, fsynced JSONL
spool outside Git retains safe diagnostics when DB writes fail. Event-level
fingerprints support idempotent replay while importing newly appended events;
committed markers and known HTTP metadata remain authoritative.

## C internal architecture review and fixes

The required [internal review](PHASE_C_ARCHITECTURE_REVIEW.md) closed C-01–C-10
before D started. Important corrections included:

- Isolate usable history by run mode; distinguish a new baseline from a
  same-mode compatibility restart. Exclude malformed/pending terminal states
  and validate snapshot identity against actual application/target rows.
- Align lock-busy errors and spool stages across components; preserve a safe
  intended run UUID before a database row can be committed.
- Preserve newly appended spool events and explicitly retain unknown request
  outcome codes when response metadata was never durable.
- Restore explicit configurability without changing defaults or the AND stop rule.
- Fix one shared transaction root cause across controller, reconciliation and
  recovery: SQLAlchemy commit failure can detach its logical transaction while
  the driver still holds an unfinished transaction. Clear/discard actual driver
  state before subsequent marker reads, diagnostics or session cleanup. Tests
  distinguish failure before COMMIT from successful commit/acknowledgement loss.

Initial failing tests were not waived or counted as acceptance. Owners fixed
causes and the final complete suite passed. No schema relationship, version
state machine, reference policy or stopping rule was changed to make tests pass.

## Phase D — reports, rehearsal and human assessment

`reporting.py` supplies read-only run/batch reports and integrity queries. It
separates intents, known HTTP responses, a conservative known-sent lower bound,
transport/parsing failures and unknown outcomes. Committed observations and page
summaries provide version/duplicate/conflict counts. Source time bounds use the
observed versions, not the current parent pointer. Reports expose each stopping
predicate, reference age/eligibility, coverage cautions and low-volume reasons.
Unexpected targets do not change the planned batch denominator. Interrupted or
unknown outcomes cannot be reported as ready to stop on sufficient overlap.
Routine exports exclude title/body, external review IDs, authors and policy refs.

`synthetic.py`, `cli.py` and `scripts/run_apple_ingestion_synthetic.sh` provide a
bounded rehearsal through the real controller/parser/reconciler/database paths.
They accept only explicit disposable local PostgreSQL databases, use invented
responses, require a fresh output directory and offer no live collection command.
The default seven simulated local dates are October 29–November 4, 2026 at 09:00
America/Los_Angeles, intentionally crossing the daylight-saving transition.
Advancing a fake clock is not elapsed observation time or actual source evidence.

The main chat executed:

```sh
PYTHONNOUSERSITE=1 \
APPLE_TEST_PYTHON=/home/l2838/miniconda3/envs/data-source-feasibility/bin/python \
  bash scripts/run_apple_ingestion_synthetic.sh \
  /tmp/apple-ingestion-phase-d-main-20261103
```

| Measured synthetic result | Count |
| --- | --- |
| Planned / attempted target slots | 56 / 56; zero missing |
| Daily batches | 7, each containing the fixed eight US applications |
| Run execution | 53 succeeded, 2 partial, 1 failed, zero interrupted |
| Fake request invocations / committed logical pages | 190 / 181, below 560 / 280 protocol ceilings |
| Coverage | 8 baseline, 30 sufficient overlap, 12 insufficient overlap, 5 indeterminate, 1 empty window |
| Per-run distinct observations / occurrences | 2,514 / 2,536; these are not distinct corpus sizes |
| NEW / UNCHANGED / CHANGED observations | 992 / 1,518 / 4 |
| Duplicate occurrences / cross-page duplicates / conflicts | 22 / 21 / 1; conflict is a duplicate subset |
| Missing-entry JSON responses / XML fallback intents | 1 / 7 |
| Integrity issue counts / terminal pending states | All zero |
| Quality sample | 80 unique synthetic reviews; 10 per app, 20 per category |
| Actual human assessments | Zero; all 80 pending, usefulness rate null |

The two partial runs and one failed run are intentional scenario outcomes, not
unresolved software-test failures. Their prior committed pages and safe failure
diagnostics remain in the reports. The rehearsal also exercises long Unicode
full text, A → B → A, metadata-only edits, empty windows, low volume, low overlap,
and absence without deletion. Independent C tests cover denial, session loss,
spool outages and commit uncertainty; those are not extra days in this denominator.

Artifacts remain outside Git at `/tmp/apple-ingestion-phase-d-main-20261103`:

- `summary.json`, `safe/protocol.json`, seven `safe/day-*.json` batch reports;
- `safe/integrity.json`, `safe/assessment-pending.json` and `checksums.json`;
- `private-assessment/sample-manifest.json`, complete rating-hidden
  `reading-material.html`, `responses.pending.json` and `rubric.json`.

The main chat verified all 15 checksummed payload files, explicit synthetic
markers on JSON artifacts, 0600 files and absence of text/source-review-ID
sentinels from routine safe reports. The cluster was removed; exported evidence
is sufficient for external review without retaining the disposable database.
Temporary artifacts must be copied deliberately if durable retention is wanted.

`assessment.py` fixes cutoff, sampling seed, logical review/version IDs, query and
rubric versions. It ranks within each app by a deterministic identity hash,
reports shortfalls without substitution, excludes disputed observations and
keeps full text in a separate private export. The cutoff reproducibility test
found and fixed future observations changing exclusion totals/manifest identity.
Only observations already eligible at that cutoff contribute to the sample.
Individually committed clean observations may support content review even when
the run is not a reliable coverage reference; that does not upgrade its coverage.

U0–U3 are usefulness labels; U2/U3 are useful, independent of stars and sentiment.
The tool supplies pending responses and validates membership, exact version,
reviewer/time/language/full-read declarations and provenance on later input.
Synthetic-test labels are separate from human labels. A fixed optional 16-record
second-reviewer subset and comparison utility do not manufacture human agreement.
No actual human labels or usefulness conclusion were generated by this task.

## Architectural deviations and remaining limits

No core architectural deviation has been accepted. The seven-table/full-text
model, reconciliation, reference eligibility and stopping predicates are the
approved baseline. Implementation-level transaction and interface corrections
above enforce that baseline. Nested XML/XHTML is explicitly rejected; it is not
silently normalized or truncated.

Remaining limitations are explicit:

- No real source request or seven actual observation days occurred. ID stability
  after Apple edits, edited-review ordering, empty-feed causes, arrival/edit
  capture and complete coverage remain empirically unverified. Absence is not deletion.
- Full text is supported and preserved, but actual live collection/retention
  conditions were not assessed or cleared here. E/F is not started; the controller
  remains synthetic-only. No model training or downstream-use grant is implied.
- No human has assessed the exported sample. Rates stay null and optional
  double-review agreement stays unmeasured until independently supplied human input.
- The exercised runtime is Linux/WSL with PostgreSQL 16.15. The spool/private-file
  safety paths use Unix locking/open flags; Windows-native operation and deployment
  packaging are not accepted by these tests. Alembic scripts are used from the checkout.
- Diagnostic details are capped at 100 objects; exact totals persist. Spool size
  is capped at 10 MB and imported event keys at 100 per group; exhaustion stops
  explicitly instead of silently dropping events. If DB and spool both fail,
  durable diagnostics cannot be guaranteed and execution stops.
- Without a durable response, request intent does not prove physical transmission.
  Reports retain unknown states and a lower-bound sent count rather than guessing.
- Bounded daily feed windows can miss arrivals/edits despite high overlap.
  Low-volume reasons characterize observed windows, not the total source population.
- Source fixture generation is deterministic; run UUIDs and exported execution
  checksums identify the actual run. No byte-identical output across fresh
  database histories is promised solely by using the same sample seed.

No schema relationship, observed-version rule, comparison-reference rule or
stopping predicate was changed. D completion ends this authorization: no E/F,
source requests, commits, pushes, scheduler installation or production operation
will follow automatically.

## Final acceptance and stop

The final suite comprises the complete C baseline (444 tests) plus 19 reporting,
33 assessment, 11 synthetic and 9 CLI tests: **516 passed**, zero failures, errors,
skips or pytest warnings. CLI success paths as well as help/rejection boundaries
were exercised with disposable PostgreSQL. The final real-cluster run used the
project Conda interpreter, automatic Python TCP guard and synthetic sessions.

The main chat verified the standalone rehearsal separately from pytest. The
checksummed artifacts above are from that actual synthetic execution; they do
not constitute actual source observations or human quality review. See also
[Phase D validation](PHASE_D_VALIDATION.md) for the execution chat's separate
commands/results.

Before this task, a SHA-256 baseline captured all 79 tracked files as found in
the existing dirty checkout and the Phase A implementation/design. Original
tracked files remain byte-identical except the intended README guidance update;
Phase A models, contracts, database configuration, permissions, seed, migrations
and approved design remain unchanged. Added earlier-phase tests are retained,
and the complete prior 228-test and 444-test baselines remain part of the final run.
`git diff --check`, local documentation links, dependency consistency, exported
checksums and module-source hash matching were checked. No files were staged.
Branch remains `main`, HEAD `474736abcee2a67f186299f09d196125400eb1ab`.

Implementation is paused at the requested end of D for external review. No E/F,
real Apple RSS request, scheduler, production deployment, Git commit or push
was performed. Further implementation or execution requires another instruction.

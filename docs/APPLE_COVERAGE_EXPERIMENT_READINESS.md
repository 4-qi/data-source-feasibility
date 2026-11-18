# Duolingo Coverage Experiment Readiness

> The replacement series completed all seven observations.
> [Final results](APPLE_COVERAGE_EXPERIMENT_RESULTS.md).

## Current status

The original W0 failed in the isolated runner and was recovered without replay.
The caller defects were fixed, 737 tests passed, and a separate replacement
series was activated for a November 13 21:00 PST W0. The
[repair and replacement record](APPLE_COVERAGE_EXPERIMENT_REPAIR.md) is the
current execution reference. The sections below retain the original preparation
record and its earlier source/test baseline.

## Original preparation status

Engineering preparation and clock verification passed. The approved experiment
was subsequently activated on November 12, 2026; see the
[activation record](APPLE_COVERAGE_EXPERIMENT_ACTIVATION.md) for active task state
and all seven observation times. No Apple requests were sent during preparation
or activation. The completed pilot and earlier probe remain unchanged.

The experiment uses the existing seven-table schema, strict parsers,
normalization, reconciliation, application-lock session, durable request intents,
page transactions, safe diagnostics and bounded HTTP transport. Production
Controller, live-execution policy and migrations are unchanged. There is no
adaptive collection or new scheduling service.

## Implementation and analysis

- `coverage_runner.py` collects contiguous pages 1–10, without production
  overlap-based early stopping. Internal parsing, attempt completion and run
  finalization helpers are composed from the existing Controller.
- `coverage_comparison.py` compares A (24 h/5 pages), B (24 h/10 pages),
  C (12 h/5 pages) and D (12 h/10 pages). The primary 24-hour trajectory uses
  W0/W2/W4/W6; W1/W3/W5 supplies two supplementary 24-hour pairs. Common-current
  endpoints are W2/W4/W6. Intervals use actual timezone-aware UTC timestamps.
- Fixed-depth costs include JSON/XML fallback through the candidate depth.
  Actual interval, distinct ID and incremental window ID counts accompany
  overlap metrics. Request intent is saved before dispatch; an unconfirmed send
  retains its conservative cost and is reported separately. Startup-inclusive requests per actual elapsed day are
  separate from steady-state planning costs.
- Counterfactual production early stopping maintains its own prefix/reference
  chain and request costs. It is reported separately and never changes stored
  acquisition status or production reference eligibility. Missing or failed
  post-run integrity verification makes the affected windows indeterminate.
- A validated complete five-page prefix remains eligible if page 6 or later
  fails. Ten-page comparisons remain indeterminate. A later conflict with an
  earlier prefix ID invalidates the affected prefix. Overall acquisition
  failures remain explicit; failed runs are not promoted to usable production
  references. Overlap does not establish complete coverage.
- `coverage_schedule.py` stores exactly seven slots, persistent request quotas,
  source integrity and nonblocking process locks in private files. It contains
  no timer or daemon. Missed/uncertain slots are never replayed.
- `coverage_experiment.py` supplies `verify`, `observe` and `maintenance`.
  `verify` creates no HTTP session. Observation failures place later slots on
  hold. Each observation disables its target in cleanup. Final maintenance
  records missed slots, consolidates the comparison and retires the manifest;
  the Windows wrapper disables both experiment tasks on retirement.

## Isolated deployment

Database: `apple_coverage_main_20261113`, in the existing private PostgreSQL 16
cluster. Existing maintenance/runtime/reporting logins are reused with their
existing least-privilege grants; no role privileges were expanded. Existing
Alembic migration `0001_apple_ingestion` is applied. The database has exactly
seven ingestion tables plus Alembic bookkeeping, and the original eight-app
seed. Only Duolingo has experimental settings (12 h, 10 pages, 20 requests).
All eight targets are disabled. There are no collection runs, fetch attempts,
reviews, versions or observations in this database.

The private state directory is
`~/.local/state/data-source-feasibility/coverage-main-20261113`.
Directory permissions are 0700; manifests, receipts, diagnostics and metadata
use 0600. Credentials remain in the existing private configuration directory
and are rebound in memory to the experiment database. They are not copied into
repository files or command arguments.

The original `apple_ingestion` database is accessed only through its reporting
login in read-only transactions. A full ordered-row digest over its seven tables
is checked before and after each future observation. Preparation verified these
unchanged counts: eight applications, eight targets, 57 runs, 160 attempts,
4,507 reviews, 4,507 versions and 7,600 observations. The earlier Todoist smoke
and all seven pilot days remain retained.

## Prepared observation times

Timezone: America/Los_Angeles (PST, UTC−08:00 at all seven slots).

| Slot | Planned local start | Planned UTC start |
| --- | --- | --- |
| W0 | 2026-11-13 09:00 | 2026-11-13T17:00:00Z |
| W1 | 2026-11-13 21:00 | 2026-11-14T05:00:00Z |
| W2 | 2026-11-14 09:00 | 2026-11-14T17:00:00Z |
| W3 | 2026-11-14 21:00 | 2026-11-15T05:00:00Z |
| W4 | 2026-11-15 09:00 | 2026-11-15T17:00:00Z |
| W5 | 2026-11-15 21:00 | 2026-11-16T05:00:00Z |
| W6 | 2026-11-16 09:00 | 2026-11-16T17:00:00Z |

These are prepared future slots, not observations or an active collection plan.
If W0 passes before activation, the entire unstarted schedule must be rebound
to seven future slots; it must not be backfilled.

`Apple-Coverage-72h` has these seven one-time triggers and is **Disabled**.
`Apple-Coverage-Closeout` is also **Disabled**; its seven checks are 30 minutes
after each observation, with an additional current-user logon trigger for
missed-execution detection. Both use `IgnoreNew`, zero automatic restarts,
no catch-up (`StartWhenAvailable=false`) and a 25-minute task limit.
The original two Phase F tasks remain disabled.

The tasks use the existing Interactive logon route: Windows must be running
and the configured user must remain signed in. A locked session is supported;
signed-out execution is not established. Wake-to-run is configured but cannot
start a powered-off computer. Missed observations are recorded without HTTP
backfill when closeout next runs. WSL, Conda and local PostgreSQL remain runtime
prerequisites.

Each observation allows at most 20 physical requests (including fallback),
10 logical pages, zero retries, at least two seconds of monotonic spacing,
10-second connection and 25-second read timeouts, a 2,000,000-byte response cap
and a 900-second target deadline. The main hard cap is **140 requests**.
The completed probe used seven; its unused allowance is not transferred.
With the completed probe, the prepared probe-plus-main envelope is at most
**147** requests. Only the earlier seven have actually occurred; main-study
execution has not been activated.

## Clock investigation and resolution

The initial probe and preparation measurements exposed both monotonic/raw
elapsed differences and WSL UTC discontinuities. Those historical measurements
are preserved in the [clock validation](APPLE_CLOCK_RELIABILITY_VALIDATION.md).
A raw-clock difference alone did not demonstrate a request-spacing defect.
Direct mocked calls passed the configured monotonic spacing constraint.

Kernel tracing identified two clock adjusters. Ubuntu's duplicate
`systemd-timesyncd` was stopped and persistently disabled; the existing WSL
system chronyd was retained unchanged. After convergence, Windows/WSL UTC
alignment was within 2.6 ms in bounded steady-state samples, and the unmodified
transport's ten mock calls had start intervals of 2.000093–2.000214 seconds.
The existing collector entry's clock check also passed.

The clock readiness condition is now satisfied. No production or experimental
collector code, historical timestamp, request limit or scheduling window changed.
Execution was kept disabled during the clock investigation; subsequent
activation is recorded separately. The focused report records the actual
scheduled UTC probe, repair, measurements and remaining environment limitations.

## Verification evidence

The final complete regression suite passed: **718 passed in 111.37 seconds**.
This includes 26 new experiment tests, the existing 16 probe tests and all
676 earlier regression cases. Tests used synthetic HTTP fixtures and disposable
PostgreSQL resources; Internet sockets are denied by the test harness.

The test cases cover ten contiguous pages, strict parsing and JSON/XML fallback,
20-request accounting, safe outputs, independent five-page validity after tail
failure, duplicate/conflicting/empty/denied pages, current/reference interval
selection, virtual reference chains, no transaction during HTTP, lost commit
acknowledgement, uncommitted-page recovery, database mismatch, source changes,
duplicate/uncertain invocations, missed slots, persistent study quotas, hold
preservation, retirement and clock rejection.

A temporary, untriggered Windows verification task exercised the real task
command with `verify` in place of `observe`. PostgreSQL was stopped first; the
actual Windows → WSL → private shell entry started it, loaded the Conda
collector and completed database/role/diagnostic/integrity checks with exit 0.
The entry produced a private receipt and no HTTP session. The temporary task was
removed; the two experiment tasks remained disabled. The initial clock receipt remained false at that time. The subsequent focused
clock repair and final verify-only entry passed; no live observation occurred.

Private evidence includes `study.json`, `pilot-baseline.json`,
`setup-verification.json`, `database-readiness.json`,
`scheduler-preparation.json`, `entry-verification.json` and
`windows-entry-proof.json`. Routine reports contain safe metadata only; full
review text belongs in the experiment database, not normal logs or Git.

## Execution boundary

Preparation ended with the experiment manifest, targets and tasks disabled
and no observation reserved. The later approved activation enabled the manifest
and Windows tasks; database targets remain disabled between observations. Clock
readiness has passed; no clock blocker remains. Existing
project-level data-use and long-term-retention questions remain documented
separately; this preparation does not establish data-use rights or introduce an
approval workflow.

The zero-network verification command is:

```sh
PYTHONNOUSERSITE=1 python \
  -m feasibility.apple_ingestion.coverage_experiment \
  --state ~/.local/state/data-source-feasibility/coverage-main-20261113 verify
```

The approved scope and task enablement now allow `entry.sh observe` only in a
due slot. It does not accept app, depth, retry or budget expansion arguments. `entry.sh maintenance`
performs no HTTP. Preparation performed no live collection or adaptive changes;
activation did not send Apple requests. No Git commit or push was performed.

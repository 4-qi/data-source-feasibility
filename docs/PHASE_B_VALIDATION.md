# Phase B validation record

This records synthetic parser/reconciliation validation only. It does not change
the approved system design, authorize live RSS, or establish Phase C/D acceptance.

## Shared test API

`tests/conftest.py` exports function-scoped `apple_database`, yielding a migrated
SQLAlchemy `Engine`. Tests may use `engine.begin()` and real commits. Each test
gets a unique database on the runner's disposable cluster; teardown disposes
the engine and drops only that fixture-created database. This separates Phase B
committed writes from Phase A's downgrade/reupgrade and from other tests.

The fixture requires both `APPLE_INGESTION_DISPOSABLE=1` and explicit
`APPLE_INGESTION_TEST_DSN`; it refuses a bootstrap database whose actual name
does not start with `apple_phase_a_`. Without this environment it skips clearly.
No ambient `DATABASE_URL` or default PostgreSQL DSN is consulted. The test
bootstrap role must be allowed to create databases in this disposable cluster.

An automatic test fixture rejects Python IPv4/IPv6 socket `connect` and
`connect_ex` calls, while allowing Unix sockets used by PostgreSQL. HTTP tests
must use synthetic transports. This Python-level guard is not an OS firewall
and does not claim to intercept networking from unrelated native libraries or
subprocesses.

## Reproduce

```bash
conda activate data-source-feasibility
bash scripts/test_apple_ingestion_postgres.sh --full-suite -q
```

Without activation:

```bash
PYTHONNOUSERSITE=1 APPLE_TEST_PYTHON=/home/l2838/miniconda3/envs/data-source-feasibility/bin/python bash scripts/test_apple_ingestion_postgres.sh --full-suite -q
```

`--full-suite` delegates test discovery to pytest and accepts optional explicit
paths, for example `--full-suite tests/test_apple_ingestion_phase_b_integration.py
-q`. It does not prepend a second database-test module. Without `--full-suite`,
the runner preserves its historical default of running the Phase A database
module and forwarding additional pytest arguments.

The runner always creates its own temporary PostgreSQL cluster and overwrites
the test DSN with its private Unix socket/database. TCP is disabled. It never
uses an existing service or an externally supplied database. The environment
must permit binding the private Unix socket; in the managed sandbox this
requires the reviewed escalation used in Phase A.

## Actual validation

Before Phase B implementation files were available, this session ran the full
existing suite through the updated runner in the shared project conda
environment, with the exact non-activation command above. Result:
**228 passed in 2.24 seconds**, zero failures, skips or warnings. This verifies
runner compatibility with Phase A and the historical offline suite; it does
not accept Phase B functionality.

This session then ran the independent cross-layer tests with the automatic
socket guard enabled:

```bash
PYTHONNOUSERSITE=1 APPLE_TEST_PYTHON=/home/l2838/miniconda3/envs/data-source-feasibility/bin/python bash scripts/test_apple_ingestion_postgres.sh --full-suite tests/test_apple_ingestion_phase_b_integration.py -q
```

Result: **2 passed in 1.10 seconds**, zero failures, skips or warnings. These
tests consume synthetic JSON/Atom bytes through the real parser and normalizer,
call reconciliation using its locked connection API, commit to PostgreSQL and
inspect the resulting versions, observations, pointers, attempts and diagnostics.
They verify:

- JSON decomposed Unicode/CRLF and Atom composed Unicode/LF with equivalent
  timestamp offsets produce one version across two runs; stored first-observed
  text is not normalized in place.
- A metadata-only rating change creates V2 and a historical fingerprint's return
  creates V3. Four runs retain four observations and all four commit markers.
- Same-page duplicates and a later conflicting page yield one version and one
  observation with occurrence count 3/conflict count 1. Replaying both committed
  attempts changes neither counters nor last-observed time. Diagnostics exclude
  the alternate body and the parser-excluded synthetic author.

The function-scoped fixture has therefore also exercised real database
creation/migration, committed transactions and teardown in both tests.

After the reconciliation session completed its real-PostgreSQL checks, this
validation session ran the combined suite on November 3, 2026:

```bash
PYTHONNOUSERSITE=1 APPLE_TEST_PYTHON=/home/l2838/miniconda3/envs/data-source-feasibility/bin/python bash scripts/test_apple_ingestion_postgres.sh --full-suite -q --junitxml=/tmp/data-source-feasibility-phase-b-validation.xml
```

Result: **336 passed in 6.87 seconds**, **0 failed, 0 skipped, 0 warnings**.
This includes the original 228 tests, the parser/normalizer and reconciliation
tests, and both independent cross-layer tests. JUnit evidence is
`/tmp/data-source-feasibility-phase-b-validation.xml`. The runner created and
cleaned up its own PostgreSQL 16.15 cluster. The project interpreter was Python
3.12.16 with `PYTHONNOUSERSITE=1`; no `/tmp` dependency directory or new package
installation was used. The automatic Python socket guard was enabled across
this full run.

The complete reconciliation suite covers the four page-transaction fault
injection stages, commit-time deferred-FK failure, prior-page preservation,
separate rollback diagnostics, replay, application session-lock preconditions,
and bounded diagnostics with exact aggregate counters. These are real
PostgreSQL checks, not SQLite substitutes or skipped environment checks.

The coordinating chat owns the Phase B stage gate. No Phase C or D code or
acceptance is included in this record. No test or implementation remains
failing in this measured Phase B suite. `git diff --check` passed; branch stayed
`main`, HEAD `474736abcee2a67f186299f09d196125400eb1ab`. No commit or push was made.

The coordinating chat separately reported its own stage-gate run: **336 passed,
0 failed, 0 skipped**, with JUnit `/tmp/apple-phase-b-main.xml`. That report is
separate from this session's measured 6.87-second run above. The coordinating
chat accepted Phase B before authorizing Phase C.

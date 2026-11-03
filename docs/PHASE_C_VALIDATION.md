# Phase C validation record

Status: **completed**, November 3, 2026. Only synthetic controller/recovery validation is in
scope. No real RSS, source expansion, Phase D/E/F, commits or pushes are part of
this session.

## Reproduce

```bash
conda activate data-source-feasibility
bash scripts/test_apple_ingestion_postgres.sh --full-suite -q
```

Without activation:

```bash
PYTHONNOUSERSITE=1 APPLE_TEST_PYTHON=/home/l2838/miniconda3/envs/data-source-feasibility/bin/python bash scripts/test_apple_ingestion_postgres.sh --full-suite -q
```

The runner creates its own temporary PostgreSQL cluster and private Unix socket
and cleans them up. `apple_database` isolates each test in its own migrated
database. The automatic fixture blocks Python IPv4/IPv6 socket connects; tests
must inject synthetic transport responses. PostgreSQL Unix sockets stay usable.

## Actual results

The completed Phase B baseline was 336 passed; it was not counted as Phase C
evidence. This session initially measured six cross-layer failures hidden by
durability handling. After the owners aligned the interfaces, it measured nine
passes and one genuine unknown-request recovery failure. That assertion was
retained and the owner fixed its cause. Twelve integration cases then passed
in 4.15 seconds. The review separately identified and tested the shared raw
driver transaction-state issue; two direct psycopg commit-failure cases were
added, bringing the independent integration module to 14 cases.

Final command:

```bash
PYTHONNOUSERSITE=1 APPLE_TEST_PYTHON=/home/l2838/miniconda3/envs/data-source-feasibility/bin/python bash scripts/test_apple_ingestion_postgres.sh --full-suite -q --tb=short --junitxml=/tmp/data-source-feasibility-phase-c-validation.xml
```

Result: **444 passed in 22.55 seconds**, **0 failed, 0 skipped, 0 warnings**.
JUnit: `/tmp/data-source-feasibility-phase-c-validation.xml`. XML totals were
independently checked: 444 tests, zero failures/errors/skips. This was this
validation session's actual run, not a copied coordinating-chat result.

Environment: shared project conda Python 3.12.16 with `PYTHONNOUSERSITE=1`,
PostgreSQL 16.15 in the runner's unique temporary cluster, project-pinned
dependencies, no `/tmp` dependency installation. The sandbox-reviewed private
Unix socket escalation was used. The cluster was stopped and removed on exit.

The full run included all earlier tests and these module totals:

| Module | Passed |
| --- | ---: |
| Independent Phase C integration | 14 |
| Controller | 28 |
| Reference/coverage | 17 |
| Transport | 24 |
| Recovery | 23 |
| Reconciliation, including shared transaction regression | 23 |

These are included within the 444 total, not additional runs. The independent
cases use the real controller, bounded transport with synthetic HTTP session,
parser, normalizer, reconciliation, recovery and database. They cover:

- Insufficient-overlap predecessor chain and exact/above-72h warning boundary;
  independent connection sees committed attempt intent before every fake fetch,
  while the lock-holder connection is idle outside a DB transaction.
- Nonempty successful duplicate-only and empty-XML cautions remain comparison
  references, without claiming sufficient coverage or end of feed.
- Eight-target batch rate denial stops after one request, and incomplete
  JSON/XML fallback at request-budget exhaustion cannot count a committed page.
- Real advisory-lock contention performs no run/attempt/fetch; real backend
  termination prevents old-run writes and restarts a new run at page one with
  null HTTP result and explicit unknown-outcome diagnostic.
- Lost commit acknowledgement reads the durable marker without replaying
  observations; min logical pages cannot be bypassed by first-page count/ratio.
- Failures before lock or run insertion preserve a safe intended UUID without
  inventing a persisted row or sending HTTP. Direct psycopg COMMIT-before-send
  failures at run intent and second page do not leak writes through later
  cleanup/diagnostics; earlier committed page remains intact.
- Terminal rows have no pending parsing/persistence/coverage states. Routine
  diagnostics and result repr exclude synthetic title/body/exception strings.

The separate `PHASE_C_ARCHITECTURE_REVIEW.md` records concrete implementation
paths, ten findings, owner fixes and regression evidence. Internal review
passed after those fixes. The coordinating chat owns the final Phase C gate and
authorization to proceed to D. This session did not implement D.

The coordinating chat separately reported **444 passed in 21.93 seconds**,
zero failures/skips/warnings, JUnit `/tmp/apple-phase-c-main.xml`, and unchanged
design/model/migration hashes. This is its independent gate run, not the
22.55-second run measured by this session. C-01 through C-10 are all closed in
the architecture review; no open finding remains for this C handoff.

Design, models and initial migration hashes matched their review-start values.
`git diff --check` passed; branch remained `main`, HEAD
`474736abcee2a67f186299f09d196125400eb1ab`. No commits/pushes, live RSS, historical
evidence changes or additional infrastructure were performed by this session.

# Phase A disposable PostgreSQL validation

This is an execution record and reproduction guide, not a revision of
`APPLE_INGESTION_SYSTEM_DESIGN.md`. All inserted review content is synthetic.
No RSS requests, historical evidence writes, services, commits or pushes were
part of this database validation.

## Reproduce

From the repository root, use the shared project conda environment defined by
`environment.yml` and `requirements/project-test.lock`:

```bash
conda activate data-source-feasibility
python -m pip install -c requirements/project-test.lock -e '.[test,apple-ingestion]'
bash scripts/test_apple_ingestion_postgres.sh -q
```

If conda activation is unavailable in the shell, select the existing project
interpreter explicitly (no `/tmp` Python dependency directory is required):

```bash
PYTHONNOUSERSITE=1 APPLE_TEST_PYTHON=/home/l2838/miniconda3/envs/data-source-feasibility/bin/python bash scripts/test_apple_ingestion_postgres.sh -q
```

The project conda environment persists `PYTHONNOUSERSITE=1`; activation applies
it automatically. Direct interpreter invocation must set it explicitly as
shown, so packages from the user's site-packages cannot enter the project tests.

The runner defaults to `/usr/lib/postgresql/16/bin` and `python3`. Override
`APPLE_TEST_PG_BIN` or `APPLE_TEST_PYTHON` when necessary. It requires a non-root
Unix user able to run `initdb` and bind a Unix socket. It creates a unique
`/tmp/apple-phase-a-pg.*` cluster, disables TCP, uses a private socket directory,
creates `apple_phase_a_test`, and stops/removes that cluster on exit. Local trust
authentication is confined to that disposable cluster; host authentication is
rejected. No existing database, user service or ambient DSN is selected.

Direct pytest execution without both `APPLE_INGESTION_DISPOSABLE=1` and an
explicit `APPLE_INGESTION_TEST_DSN` skips these tests. The fixture additionally
rejects a database name without the `apple_phase_a_` prefix. Setting those
variables manually authorizes destructive migration tests in that selected
database; prefer the runner, which creates its own database and sets them itself.

## Actual results — November 3, 2026

The main coordinating chat supplied an isolated, offline-installed dependency
directory at `/tmp/phase-a-python`. This session ran:

```bash
PYTHONPATH=/tmp/phase-a-python:src bash scripts/test_apple_ingestion_postgres.sh -q
```

Result: **33 passed, 0 failed, 0 skipped**, 1.16 seconds of pytest time.
PostgreSQL was **16.15 (Ubuntu 16.15-0ubuntu0.24.04.1)**. Python was 3.12;
SQLAlchemy 2.0.44, Alembic 1.17.1, psycopg/binary 3.2.12 and pytest 8.4.2.
The sandbox initially denied private Unix socket binding (`Operation not
permitted`); automatic approval review allowed the isolated runner to execute
outside that restriction. The runner then completed and cleaned up its cluster.

This session's final successful run emitted three Alembic deprecation warnings because
`alembic.ini` lacked `path_separator`. They concern legacy parsing of
`prepend_sys_path`, not constraint failures. Configuration is owned by the schema
session; this validation session did not modify it.

An explicit no-database check also ran:

```bash
PYTHONPATH=/tmp/phase-a-python:src python3 -m pytest tests/test_apple_ingestion_database.py -q
```

Result: **33 skipped**, 0.47 seconds. This only verifies the environment guard;
it is not database acceptance evidence.

### Coordinating chat's reported project conda validation

The coordinating chat prepared the shared project conda environment at
`/home/l2838/miniconda3/envs/data-source-feasibility` (Python 3.12.16), with the
editable project and dependencies installed. It reported **33 database tests
passed** in that environment and **165 passed, 1 skipped** for the separate
offline/contract run. These are results communicated by the coordinating chat,
not reruns performed by this validation session. No elapsed time or skip reason
was supplied in that handoff, so neither is inferred here.

The coordinating chat subsequently reported that `pip check` passed with
`PYTHONNOUSERSITE=1`. It persisted that setting in the conda environment and
recorded it in `environment.yml`; the final combined run will use this isolation.
This is a coordinating-chat report, not an additional check by this session.

The coordinating chat owns the final combined run in one disposable database
and its exact counts in `PHASE_A_DELIVERY.md`. A zero-skip combined result is not
claimed here before that run finishes. The schema session owns the
`path_separator=os` warning fix; the earlier warning record above is retained
as an accurate description of this session's measured run.

## Verified behavior

- Alembic upgrade, downgrade and reupgrade on a real PostgreSQL instance;
  downgrade removes all seven core tables and the guard function.
- Exactly seven core tables plus `alembic_version`; Alembic autogenerate reports
  no model/schema differences after migration.
- Complete synthetic title/body roundtrip (380,003 Unicode characters each),
  combining characters, emoji, CRLF and literal entity text preserved.
- Deferred owned current-version FK allows identity plus V1 to commit; a missing
  reserved version fails specifically at commit. Cross-review current and
  observed-version pointers fail; cross-application detecting runs/observations,
  wrong-target references and wrong-app targets fail.
- Opaque leading-zero/non-numeric IDs survive; review, version and observation
  uniqueness is enforced. Equal hashes on distinct versions remain legal.
- Status/range/JSON/hash/count checks and partial unique indexes reject invalid
  state, two running runs per target and two committed responses per page.
- All seven frozen run identity/snapshot fields reject owner-issued mutations;
  an unchanged snapshot is allowed.
- Seed creates eight disabled targets, is idempotent and preserves a later
  maintenance change. The historical manifest is read only.
- Separate LOGIN connections authenticate as nonowner runtime/report roles.
  Runtime inserts and allowed column updates succeed; version UPDATE/DELETE,
  all table DELETE operations, forbidden identity/configuration updates,
  schema/table/function modification fail with PostgreSQL `42501`. Report role
  SELECT succeeds and INSERT is denied. No superuser `SET ROLE` substitutes for
  these connections.
- PostgreSQL roundtrip timestamps represent the expected UTC instant; the
  application engine explicitly establishes `TimeZone=UTC`.

## Scope and remaining work

No database test remains failing or skipped in the real-cluster run. This is
Phase A synthetic database acceptance only. Parser, normalizer, reconciliation
ordering, controller lifecycle, concurrency/recovery and real RSS behavior are
not implemented or accepted here. Version number contiguity and latest-current
semantics remain later writer responsibilities, not guarantees supplied by
these FKs. Project conda results reported by the coordinating chat are recorded
separately above; whole-repository combined regression acceptance belongs to
that chat's final integration.

Owned artifacts: `tests/test_apple_ingestion_database.py`,
`tests/apple_ingestion_db_helpers.py`,
`scripts/test_apple_ingestion_postgres.sh`, and this record. Existing uncommitted
documentation and other sessions' implementation files were preserved. Branch
remained `main`, HEAD `474736abcee2a67f186299f09d196125400eb1ab`;
`git diff --check` passed.

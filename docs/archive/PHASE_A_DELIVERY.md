# Phase A — Contracts and Database delivery

Phase A is the authorized current engineering scope. The approved design is
[APPLE_INGESTION_SYSTEM_DESIGN.md](../APPLE_INGESTION_SYSTEM_DESIGN.md).
No later phase, live Apple request, production database, commit or push is authorized by this delivery.

## Coordination and ownership

Implementation was divided into three workstreams with distinct file ownership:

| Execution chat | Scope | Chat ID |
| --- | --- | --- |
| Schema and Alembic | Seven SQLAlchemy mappings, fixed migration, immutable-run trigger, explicit permissions and connection configuration | `01a1a0c9-f4b9-7e20-aed1-32ddf85f9cd3` |
| Contracts and seed | Immutable validated configuration/snapshot, full-text record, status/reason contracts, explicit eight-app seed | `01a1a0ca-0bc7-7af0-be76-7075fbeb57a1` |
| PostgreSQL validation | Disposable-cluster runner and actual constraint/migration/permission tests | `01a1a0ca-2057-71f3-9cdc-fb6cf70bd41a` |

Phase acceptance required resolved interface dependencies and combined
implementation validation.

## Project environment

Use one shared project Conda environment, `data-source-feasibility`, throughout
all phases. `environment.yml` defines Python 3.12 and disables user-site package
loading; `requirements/project-test.lock` records the tested dependency set.
The actual local environment is `/home/l2838/miniconda3/envs/data-source-feasibility`.
This is the project environment, not a separate environment per engineering phase.

```sh
conda env create -f environment.yml  # only when the project environment does not exist
conda activate data-source-feasibility
python -m pip install -c requirements/project-test.lock -e '.[test,apple-ingestion]'
python -m pip check
```

When invoking its interpreter by absolute path instead of activating Conda,
set `PYTHONNOUSERSITE=1` explicitly. No existing Python environment or PostgreSQL
service was repurposed. The PostgreSQL 16.15 binaries already present on the
host run only an isolated temporary cluster with TCP disabled.

## Delivered interfaces

- `contracts.py`: `IngestionConfig`, `ConfigSnapshot.to_dict()/from_dict()`,
  `ReviewRecord`, independent execution/coverage/comparison states and structured reasons.
  Snapshot serialization is detached and validates every required versioned field.
  Access-policy references are not grants of live permission.
- `models.py`: `Base.metadata` and seven mapped classes, full review title/body,
  ownership FKs, unique/check/partial-index constraints and deferred circular pointer.
- `migrations/`: stable, self-contained revision `0001_apple_ingestion`, reversible DDL,
  immutable identity/configuration trigger. An eighth `alembic_version` bookkeeping
  table does not add a core ingestion table.
- `db.py`: explicit PostgreSQL/psycopg engine configuration, UTC sessions and
  hidden SQL parameters; no database connection at import.
- `permissions.py`: `RoleConfig`, reviewable `permission_sql()` and explicit
  transactional `apply_permissions()`. Actual roles must already exist; normal
  runtime is nonowner and cannot update/delete versions or delete any core rows.
- `seed.py`: explicit `seed_defaults(connection, manifest_path)` in a caller-owned
  transaction, reading the existing eight-app manifest. Newly seeded targets are
  disabled; repeat seeding preserves existing identities and maintenance settings.

## Acceptance

**Accepted for Phase A synthetic engineering delivery on November 3, 2026:**
the combined suite ran with project Conda Python
3.12.16, PostgreSQL 16.15 and the pinned dependencies: **228 passed, zero failures,
zero skips, no pytest warnings**, in 2.37 seconds of pytest time.

| Group | Passing tests |
| --- | --- |
| Original feasibility regression | 57 |
| Data/configuration contracts and transactional seed | 109 |
| Real PostgreSQL migrations, constraints, ownership and role permissions | 33 |
| Database connection/permission configuration | 29 |
| Total | 228 |

The actual command used the existing project interpreter explicitly:

```sh
PYTHONNOUSERSITE=1 APPLE_TEST_PYTHON=/home/l2838/miniconda3/envs/data-source-feasibility/bin/python \
  bash scripts/test_apple_ingestion_postgres.sh -q \
  tests/test_apple_ingestion_contracts.py tests/test_apple_ingestion_database_config.py \
  tests/test_apple_validation.py tests/test_collectors.py tests/test_http.py \
  tests/test_mainstream.py tests/test_mobile_quality.py tests/test_negative.py \
  --junitxml=/tmp/data-source-feasibility-phase-a-final.xml
```

The runner always includes `tests/test_apple_ingestion_database.py`; the additional
paths cover all other maintained tests without duplicate collection. The cluster
was automatically stopped and removed. The XML is a local execution artifact,
not a committed source-evidence dataset. `python -m pip check` with user-site
loading disabled reported no broken requirements. The environment variable is
also saved on the project Conda environment for activation.

Database checks include full synthetic Unicode title/body roundtrip, commit-time
owned-pointer validation, rejected cross-review/application/target references,
snapshot and identity immutability, migration downgrade/reinstall, metadata/schema
agreement, disabled/idempotent seed and actual authenticated nonowner runtime and
report connections. Their negative operations were rejected by PostgreSQL, not
just by Python validation. Later writer ordering and recovery behavior were not tested.

See [database validation](PHASE_A_DATABASE_VALIDATION.md) for the execution chat's
separate evidence; skipped tests without a disposable database are not counted as
database acceptance. Before acceptance, SHA-256 comparison confirmed all 76
pre-existing protected source/test/probe/research/result files were unchanged.
The approved design document also remains unchanged. `git diff --check` passed;
branch and HEAD remain `main` / `474736abcee2a67f186299f09d196125400eb1ab`.
No files were staged or committed and nothing was pushed.

## Phase dependencies and remaining boundaries

Phase B can build parser/normalizer/reconciler on these contracts and schema after
separate authorization. Phase C owns collection/reference-selection/locking/recovery;
Phase D owns reports, simulated seven-day windows and human-assessment tools.
Reference age remains warning-only and insufficient overlap is not a reference
exclusion; this phase supplies contracts, not an implemented selector.

The existing unresolved live-access/retention basis concerns Phase E/F and does
not block synthetic Phase A engineering. ID stability/edit ordering and source
coverage remain empirical unknowns. No manual review labels or live observations
were fabricated, and no production acceptance is claimed.

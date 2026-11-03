# Phase E deployment preparation and offline validation

> Subsequent authorized local deployment is recorded in
> [the persistent deployment report](APPLE_INGESTION_LOCAL_DEPLOYMENT.md), including
> actual paths, startup, tested backup/restore and the current unconfirmed
> `long_term` policy. The original E preparation boundary below is historical.

Status: **offline deployment preparation and retention compatibility**. This
validation session operates no persistent host and sends no real RSS request.
The example records intentionally remain pending. Phase F
and even a limited real RSS request require separate explicit authorization.
No service, scheduler, credentials or real host has been provisioned here.

## Configuration and responsibility boundaries

Start from `deploy/apple_ingestion/unix.example.json` or
`deploy/apple_ingestion/tls.example.json`. Both use schema
`apple-ingestion-deployment/1`. `DeploymentConfig.from_dict` rejects unknown or
missing required fields; the two optional retention fields described below
have backward-compatible defaults. `long-term-retention.example.json` is an
explicit pending long-term Unix profile, not an approval. The separate
`single-run-approval.example.json` has its own schema and is not a deployment
config. `load_config` uses fixed safe error codes. Importing the module,
loading templates or generating the review plan does not contact PostgreSQL.

The database section names three **distinct environment references**, not DSN
values: owner, runtime and report. Supply those references through the chosen
host's private credential mechanism; do not put credential URLs in repository
JSON, shell command arguments, console output, exception dumps or screenshots.
Do not print Engine/URL objects. There is no `DATABASE_URL` or ambient shared
DSN fallback.

`deployment_engine(config, role, environ=...)` creates an unconnected Engine.
Roles are `owner`, `runtime` and `report`. Each supplied URL must explicitly
name the corresponding configured LOGIN role. When multiple role URLs are
available, they must point to exactly the same endpoint/database; only role
credentials differ. No hostname/socket/port alias is silently accepted. The
live readiness audit also compares actual connected database identity and the
runtime endpoint to the audit connection, so a different database with a
same-named role and seven tables cannot verify this deployment.

| Profile | Required configuration | Validation boundary |
| --- | --- | --- |
| Unix socket | Absolute socket directory through explicit `host` query, optional explicit port, explicit DB and role. No remote host or service/hostaddr/options indirection. | Real private Unix PostgreSQL connections were tested on Linux. Persistent host authentication and Windows ACLs are not validated. |
| TLS | Explicit hostname/DB/role, `sslmode=verify-full`, absolute existing CA file supplied by `tls_root_cert_env`. Downgrade to require/prefer/disable is rejected. | URL/CA-path configuration is tested without TCP. No real TLS handshake, certificate chain or remote host is certified by these tests. |

The factory sets UTC, `search_path=public`, hidden SQL parameters, echo off,
connect timeout and baseline lock/statement timeout. Only the existing public
schema is supported. It creates no database, role, schema, table or service.

## Role and ownership plan

There are three independent, actual LOGIN roles with no superuser, CREATEDB,
CREATEROLE, replication or BYPASSRLS attributes. Runtime/report have no role
memberships and own neither the database nor ingestion objects. This is verified
with real LOGIN connections in tests, not a superuser `SET ROLE` substitution.

An administrator separately provisions roles/authentication and chooses one
of the supported ownership layouts:

1. The nonadmin maintenance role owns the dedicated database; PostgreSQL's
   public-schema ownership through `pg_database_owner` gives it control.
2. The database stays owned by a separate administrator, while `public` is
   owned by the nonadmin maintenance role.

Both layouts were actually tested. Maintenance owns the seven tables, identity
sequences, Alembic version table and immutable-run guard function. It is not
assumed to be `postgres` or a cluster superuser. Database/role creation is not
performed by `deployment.py`; a maintenance LOGIN with NOCREATEDB/NOCREATEROLE
cannot perform that administrative provisioning itself.

The existing `permissions.apply_permissions` remains the authority for grants:
runtime SELECT/INSERT plus exact approved column UPDATEs and sequence USAGE;
no version UPDATE/DELETE, no table DELETE/TRUNCATE, no target/application UPDATE
and no schema CREATE. Report role receives SELECT only. Report SQL access is
not column-level text masking: distribute that trusted account only within the
approved data/assessment scope, and use the existing safe report API for routine
exports. No eighth table or replacement schema is introduced.

## Review before any initialization

This command produces **reviewable SQL/metadata only**, without reading DSNs or
opening a database:

```python
import json
from feasibility.apple_ingestion.deployment import load_config, initialization_plan

config = load_config("deploy/apple_ingestion/unix.example.json")
print(json.dumps(initialization_plan(config), indent=2))
```

The plan includes role SQL without passwords, the fixed Alembic revision
`0001_apple_ingestion`, offline migration DDL, the existing grants plan and an
eight-app US/mostrecent seed description. Alembic's own version table is
additional to the **seven core tables**. Template retention stays pending and
the plan explicitly says `live_authorized=False`.

No execution occurs through `initialize_database` or `grant_permissions` unless
the caller explicitly passes `execute=True`. The caller must provide an active,
non-autocommit transaction on the actual maintenance LOGIN. Administrative or
impersonated connections and a non-public effective schema are rejected.

For an independently authorized, already provisioned **disposable test database**,
the explicit execution shape is:

```python
from feasibility.apple_ingestion.deployment import (
    deployment_engine, initialize_database, grant_permissions,
)

owner_engine = deployment_engine(config, "owner")
try:
    with owner_engine.begin() as connection:
        initialize_database(connection, config, execute=True)
        grant_permissions(connection, config, execute=True)
finally:
    owner_engine.dispose()
```

This work used that shape only against newly created temporary databases. It
does not authorize running it against a persistent host. Helpers never commit
the caller's transaction. Actual rollback tests prove migration, seed and
grants roll back together. After a commit/connection failure, stop and discard
the uncertain handle; verify durable schema/seed/grants from a fresh audited
connection before any independently approved retry. Do not assume a failed
acknowledgement proves rollback.

Seeding reads the existing historical manifest and inserts exactly eight
applications and US/mostrecent targets. New targets are disabled. Repeated
migration/seed is idempotent and does not overwrite existing settings. These
helpers never enable a target or manufacture an access decision.

## Read-only health and live readiness

```python
from feasibility.apple_ingestion.deployment import preflight

owner_engine = deployment_engine(config, "owner")
runtime_engine = deployment_engine(config, "runtime")
try:
    with owner_engine.connect() as audit, runtime_engine.connect() as runtime:
        readiness = preflight(
            audit, config, for_live=True, runtime_connection=runtime,
        )
finally:
    runtime_engine.dispose()
    owner_engine.dispose()
```

The audit creates fresh engines rather than reusing an initialization handle.
The preflight executes SELECT statements only and does not commit,
roll back or replace either caller connection. It checks PostgreSQL major,
UTC/public schema, seven-table set/revision, immutable-run trigger, expected
seed, actual ownership/role attributes, exact runtime column grants, sequence
USAGE, report readonly grants and actual runtime LOGIN on the same deployment.
It never queries or returns review bodies, credentials or a DSN.

Important JSON-safe result fields:

- `database_ready`, `runtime_login_verified`, `retention_ready`, `diagnostics`;
- `for_live`, `ready`, `live_ready`, `status` and explicit `blockers`;
- `scope` with the fixed source, US/mostrecent and eight manifest identities;
- `retention` with documented owner/duration/policy/backup/export/expiry refs;
- revision, parser/hash versions and `db_timeout_profile`.

`live_ready` means only that the checked deployment prerequisites are ready.
The result **always** has `live_authorized=False`, `live_policy_checked=False`
and `real_http_performed=False`. The default `live.ProjectExecutionPolicy` separately validates
confirmed/enabled project conditions, matching operator/references, scope/window
and limits, without per-run approval documents or receipts. The legacy
`live.LiveExecutionPolicy` API remains compatible but is not required. No second deployment authorization
class or independent rights decision exists here. A `ready` flag alone is not
permission to instantiate/send a real request. Current templates fail live
readiness because retention, operator, host/environment and approval decisions
remain pending.

### Effective timeout precedence

The deployment settings do **not** replace every existing pipeline timeout:

| Stage | Effective behavior |
| --- | --- |
| New deployment Engine session | Configured baseline; templates use lock 5000 ms, statement 30000 ms and DB connect 10 s. UTC/public/hidden parameters apply. |
| Existing `application_session` | Temporarily sets fixed lock 5000 ms / statement 10000 ms; restores the previous session settings on healthy exit. |
| Existing page reconciliation transaction | Uses its existing local defaults lock 5000 ms / statement 30000 ms. Controller does not forward arbitrary deployment timeout overrides. |
| HTTP | Existing snapshot settings remain connect/read 10/25 s, bounded stream and target deadline; these are separate from DB timeouts. |

The readiness report exposes these boundaries and explicitly reports that
arbitrary overrides are **not** propagated throughout the pipeline. No core
timeout plumbing was refactored in this task. The supplied templates use the
existing supported defaults.

## Diagnostics, stopping and recovery

Set `diagnostics.spool_path_env` through the deployment environment and name the
responsible operator. The parent directory must already exist outside Git,
be owned by the executing OS user and mode 0700; an existing spool must be an
owned, singly linked regular 0600 file without symlink traversal. The named
operator is accountability metadata; the path check verifies the **current OS
process**, not an unstarted future service account.

`diagnostics_probe(config)` is read-only: it checks path/mode/access without
creating files. `execute=True` explicitly performs a private temporary write,
file/directory fsync and cleanup. It leaves no fabricated run/attempt spool
event. Even a successful probe returns `durability_guaranteed=False`; total DB
and spool failure is explicitly nondurable. Recheck under the actual future
execution identity and host filesystem; no Windows/service-account validation
is claimed here.

Stop before transport when deployment/policy/retention/roles/schema checks fail.
During an independently authorized run, keep the existing behavior: access/rate
denial stops the source, uncertain HTTP outcomes stay unknown, loss of the pinned
application session aborts without reconnecting to continue, and an unpersisted
attempt intent permits no next HTTP request. Log safe code/IDs/stage/time only;
never print raw exceptions, response bodies, SQL parameters or credential URLs.

Recovery uses the existing dedicated application lock and same connection:
`replay_spool(connection, app_id, spool, recovered_at)` then
`recover_interrupted(connection, app_id, recovered_at)`. Event fingerprints make
imports idempotent; committed markers win, unknown HTTP status is not invented,
orphan runs become interrupted and a later separately approved run starts at
page one. Keep the spool and single-use approval receipt; neither deletion nor
automatic retry is a recovery step. No recovery command is executed on a real
host in Phase E.

## Explicit finite or long-term policy; arrangement confirmation still required

All supplied deployment examples retain `state='pending'`, null owner/policy
reference and null backup/export/review references. No duration or confirmation
is inferred. The minimal compatible fields are:

| Field | Legacy/default behavior | Explicit long-term behavior |
| --- | --- | --- |
| `mode` | Omitted means `finite_days`; existing finite-day inputs remain valid. | Must be the literal `long_term`. |
| `duration_days` | Documented finite mode requires the existing positive integer. | Must be null; no invented day count or TTL is created. |
| `arrangement_confirmed` | Omitted defaults to false; legacy finite completeness is unchanged. | Must be explicitly true before retention readiness can pass. |

In either mode, documented technical configuration requires the named owner,
policy, backup/export handling and review references. In long-term mode the
existing `expiry_review_ref` names the periodic policy/arrangement review
process; it does not create an expiry date or imply a TTL. Unknown or misspelled
modes and nonboolean confirmation are rejected.

`technical_complete` reports documented configuration completeness separately
from `complete`/retention readiness. An unconfirmed documented long-term profile
can be technically complete, but remains `retention_ready=False`,
`live_ready=False` with `RETENTION_DECISION_PENDING` and
`LONG_TERM_ARRANGEMENT_UNCONFIRMED`. Only an independently recorded applicable
arrangement may justify changing the explicit confirmation; a requested
technical mode is not evidence that such an arrangement exists.

Even confirmed long-term configuration never grants execution authorization:
`live_authorized` and `live_policy_checked` remain false in deployment preflight.
The default reusable `ProjectExecutionPolicy` validates separate project access
conditions; the legacy single-run API is optional. No human/external approval,
retention permission or legal finding
is manufactured by this boolean. Synthetic unit fixtures use explicitly labeled
test-only finite and long-term records solely to exercise these boundaries.

Before a future live request, the responsible owner must record the applicable
access/retention basis and conditions for this exact RSS use, selected finite or
long-term arrangement, scope and
approver. Supplier/API conditions are not silently substituted for an RSS rule.
The coordinating chat handles current source-condition review; this runbook
asserts no external terms interpretation.

Keep complete title/body and all accepted observed versions under the chosen
policy. Long-term mode adds no automatic expiry, pruning or TTL. A later approved
policy change or finite expiry process needs a separately reviewed scope,
FK-safe whole-history removal plan, backup expiry/restore controls and private
export handling, with an audit record and post-operation integrity check. This
task implements **configuration and maintenance review only**: no purge API,
deletion privilege for runtime, new table, automatic timer or hash-only
replacement is added. Backup/export owners must address copies and restores;
changing the primary database alone is not a full retention operation.

## Actual offline validation

Only the existing disposable PostgreSQL runner is used:

```bash
PYTHONNOUSERSITE=1 APPLE_TEST_PYTHON=/home/l2838/miniconda3/envs/data-source-feasibility/bin/python bash scripts/test_apple_ingestion_postgres.sh --full-suite tests/test_apple_ingestion_deployment.py -q --tb=short --junitxml=/tmp/apple-phase-e-deployment-final.xml
```

The test administrator creates fresh databases and three LOGIN roles in the
runner's temporary cluster. Both database-owner and public-schema-owner layouts
then run migration, seed, grants and caller rollback **as a real non-superuser
maintenance login**. Runtime independently logs in and runs actual Controller →
fake HTTP transport → parser → reconciliation → PostgreSQL through five committed
pages/100 full-text versions/100 observations. Version modification/deletion and
configuration mutation are rejected with 42501. Report independently logs in,
produces a safe report and fails UPDATE. No superuser impersonates either role.

Negative checks include pending retention, missing runtime verification,
unsafe DSNs/TLS downgrade, unknown/shared configuration, insecure diagnostic
mode, excess version-column UPDATE privilege, and a different real database
with the same runtime role. Default plans/probes perform no mutation; explicit
caller rollback leaves no migrated tables. Fake-only networking is enforced by
the existing Python TCP guard; PostgreSQL uses its private Unix socket.

Final measured result: **25 passed in 7.10 seconds**, **0 failed, 0 skipped,
0 warnings**. JUnit: `/tmp/apple-phase-e-deployment-final.xml`. The 25 cases
include 13 pure configuration/plan/probe checks and six real-database checks
repeated across both ownership layouts. Earlier staged checks were 13 pure
passes, then 21 full passes before caller-rollback and cross-database cases
were added; none were skipped or counted as deployment evidence.

The runner stopped and removed its private cluster. Test teardown dropped only
the newly created databases/roles. `git diff --check` passed. This session
changed only `deployment.py`, the two example JSON templates, this runbook and
the deployment test module. It did not change model/migration/controller/
reconciliation/source/reference/stop behavior or historical evidence, and made
no Git commit/push.

Actual readiness remains **blocked for live**: no real host/credential decision,
retention owner/duration/policy/backup/export/expiry decision, diagnostic operator
or independent single-run access/approval is supplied by these examples. No real
TLS handshake, Windows deployment or service-account filesystem behavior was
validated. Passing offline tests proves the prepared mechanisms and default
closure, not actual deployment, Apple permission or live-pilot acceptance.

## Retention compatibility follow-up — November 3, 2026

The separately authorized minimal long-term extension changed only deployment
configuration/validation, its tests, this runbook and the pending long-term
example. The coordinating chat owns actual local persistent setup and its
configuration; this validation session operated no persistent host.

The old seven-field finite-day JSON and positional `RetentionConfig` calls
remain accepted. Two optional fields default compatibly to `mode='finite_days'`
and `arrangement_confirmed=False`. Explicit long-term mode has no duration or
TTL, and documented metadata alone cannot pass retention readiness until its
applicable arrangement is explicitly confirmed. This still does not authorize
any real request. The exact deployed confirmation must reflect an independently
recorded decision, not a technical test fixture.

Deployment template tests now name only the actual deployment templates, so
`single-run-approval.example.json` is preserved and is not parsed as deployment
configuration. The added `long-term-retention.example.json` remains pending,
unconfirmed and duration-null; it contains no credential or real authorization.

Actual verification:

```bash
PYTHONNOUSERSITE=1 APPLE_TEST_PYTHON=/home/l2838/miniconda3/envs/data-source-feasibility/bin/python bash scripts/test_apple_ingestion_postgres.sh --full-suite tests/test_apple_ingestion_deployment.py -q --tb=short --junitxml=/tmp/apple-long-term-retention-compatibility.xml
```

Result: **33 passed in 8.47 seconds**, **0 failed, 0 skipped, 0 warnings**.
This includes the prior deployment checks, legacy finite JSON without either
new field, long-term null-duration/invalid-input tests, and both real
non-superuser ownership layouts proving that technically complete but
unconfirmed long-term retention blocks live readiness. Confirming the test-only
arrangement enables technical readiness but never sets `live_authorized` or
`live_policy_checked` true.

The runner cleaned its temporary cluster and databases. `git diff --check`
passed. Model and initial migration hashes still match the earlier baseline;
there are no schema, pipeline, reconciliation, reference or stop-rule changes,
TTL/purge operations, real RSS/F execution, Git commits or pushes in this
follow-up.

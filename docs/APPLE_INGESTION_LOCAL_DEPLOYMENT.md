# Persistent local PostgreSQL deployment

Verified November 3, 2026, in the existing WSL Ubuntu environment. Phase E
offline review was accepted before this separately authorized deployment.

**Result: the dedicated local database is deployed and survives a PostgreSQL
process restart; explicit long-term retention is configured; live collection
remains blocked.** No actual Apple RSS request, target enablement, seven-day
pilot, Git commit or push occurred. This is a local deployment, not evidence of
real source compatibility or seven-day operation.

> Subsequent authorized preparation: [the first smoke-test runbook](APPLE_FIRST_LIVE_SMOKE_TEST.md)
> now uses a reusable default-closed **technical** project policy. Administrative
> access/retention confirmation fields are no longer runtime gates. The persistent deployment evidence and 640-test gate below remain
> historical results; no real collection has started.

## Actual deployment

The existing PostgreSQL 16.15 binaries at `/usr/lib/postgresql/16/bin` were
reused. The shared Conda environment remains `data-source-feasibility`, Python
3.12.16, with `PYTHONNOUSERSITE=1`; `pip check` passes. No new environment,
package installation, cloud service or scheduler was introduced.

The system-managed `16/main` instance on port 5432 was left running and
unchanged. The project uses a separate, persistent, OS-user-owned instance on
the WSL Linux filesystem, not a temporary test-cluster directory. The project
instance is managed with `pg_ctl`; `pg_lsclusters` lists the Debian-managed
system instance and is not the project instance's status command.

| Item | Actual value |
| --- | --- |
| OS execution identity | `l2838` |
| Project database | `apple_ingestion` |
| Data directory | `/home/l2838/.local/share/data-source-feasibility/postgresql/16` |
| Private Unix socket directory | `/home/l2838/.local/state/data-source-feasibility/socket` |
| Socket port number | `55440`; TCP listening is disabled |
| Configuration/credentials directory | `/home/l2838/.config/data-source-feasibility` |
| Diagnostics, receipts, logs, backups | Separate subdirectories of `/home/l2838/.local/state/data-source-feasibility` |
| Cluster system identifier | `7703908489459282396` |
| Persistent database OID | `16387` |
| Migration | Existing Alembic `0001_apple_ingestion` |
| Automatic startup/collection | Neither configured; manually start PostgreSQL after WSL shutdown |

The instance was left **running** at handoff. Storage is persistent independently
of the creating shell and test runner. A clean postmaster stop/start was actually
tested; shutting down/restarting the entire WSL distribution was not performed.
WSL's existing persistent Linux disk contains the files; this task did not add
a systemd unit or promise boot-time startup.

## Database, roles and actual verification

Initialization and grants ran in transactions using the actual non-superuser
maintenance LOGIN, through the existing `initialize_database` and
`grant_permissions` APIs. They applied the existing migration and seed twice
to check idempotence. No `create_all`, replacement schema or new migration was
used. The core tables are exactly:

`application`, `collection_target`, `collection_run`, `fetch_attempt`, `review`,
`review_version`, `review_observation`. `alembic_version` is bookkeeping.

| Account | Purpose and verified boundary |
| --- | --- |
| `apple_ingestion_owner` | Owns this database and ingestion objects; maintenance login; no superuser, CREATEDB, CREATEROLE, replication or BYPASSRLS |
| `apple_ingestion_runtime` | Existing SELECT/INSERT and exact column UPDATE grants plus sequence usage; no history UPDATE/DELETE, target enablement, schema CREATE, administrative attributes or role memberships |
| `apple_ingestion_report` | SELECT only; no writes, administrative attributes or role memberships |
| `apple_ingestion_admin` | Bootstrap administrator of this dedicated cluster only; used for database creation, isolated restore databases and server verification; never given to Controller |

All three application accounts were verified with actual independent logins,
not `SET ROLE` from a superuser. Runtime version modification/deletion and target
enablement fail with SQLSTATE `42501`; report writes fail likewise. Database
PUBLIC privileges on the project database were revoked and explicit CONNECT
grants issued. Existing table/column/schema grants remain authoritative.

The original eight manifest apps and their US/mostrecent targets are present.
Final persistent counts are:

| Table | Rows |
| --- | ---: |
| `application` | 8 |
| `collection_target` | 8, all disabled |
| `collection_run`, `fetch_attempt`, `review`, `review_version`, `review_observation` | 0 each |

Actual preflight reports `database_ready=true`,
`runtime_login_verified=true`, correct revision/ownership/grants/UTC and eight
seeds. Read-only integrity checks pass with all six issue counters zero.
The private diagnostic write/fsync/remove probe passes. The real spool remains
empty and the receipt directory contains no claims.

## Long-term retention

The technical project decision is **long-term retention without a preset expiry**,
not an arbitrary 30/90-day TTL. The technical configuration is:

```json
{"mode": "long_term", "duration_days": null}
```

Existing private JSON files may still contain `state`, owner/reference metadata
and `arrangement_confirmed=false`; compatibility readers accept them unchanged.
The old confirmation field is ignored and omitted from new canonical output.
No administrator needs to turn it true to invoke the collector. Owner/document
references can be absent and do not block operational preflight.

`technical_complete` / `.complete` describe mode/duration completeness only.
`long_term` with null days is complete technical intent, without asserting data-
use rights. Finite-day inputs remain supported. Database preflight now reports
actual roles, schema, permissions and diagnostics under `operational_ready`;
`live_ready` is a compatibility alias for **deployment operational readiness**,
not overall execution enablement or legal approval. A healthy preflight can pass
while every target and the project execution switch remain disabled.

No deletion timer, TTL, purge job or automatic history deletion is added.
Complete titles/bodies, metadata, observed versions, observations and collection
history remain stored. A review leaving the RSS window never implies deletion.
Reconciliation, comparison-reference and pagination/stop rules are unchanged.

The collector still requires explicit project/target enablement, matching
technical scope/window/budgets and fresh operational checks. It does not require
access-basis references, approval documents or per-run credentials. A tracking
policy ID/digest identifies the technical configuration in immutable snapshots;
it is not an approval. The public [long-term example](../deploy/apple_ingestion/long-term-retention.example.json)
contains no credentials or confirmation flag. Actual private connection values
remain outside Git.

Access/data-use conditions and the suitability of long-term retention remain
project-management discussion items for John and the responsible owner. Removing
software confirmation checks neither resolves those issues nor claims rights.
Future required deletion/change handling remains described below.

## Private storage

Project data/config/state roots, socket, diagnostics, receipts, logs and backups
are mode `0700`; configuration/credential files and backups are `0600`. Local
connections require SCRAM-SHA-256; there is no trust authentication or TCP
listener. PostgreSQL data checksums, fsync, full-page writes and synchronous
commit are enabled. No unrelated database/service was reconfigured.

Credentials are generated locally and kept only in the private configuration
directory and its explicitly private backup. `connection.env.json` supplies
the existing role-specific environment references to `deployment_engine`.
`pg_service.conf` contains connection profiles and `pgpass` provides local
passwords for PostgreSQL tools. Never print/source JSON as shell code, print
SQLAlchemy URLs or use passwords as command-line arguments. Do not copy these
files into the checkout or public reports.

The same WSL OS user owns and can read the private files; this is not isolation
from that user, root or the Windows/WSL administrator. Read-only database access
also allows reading stored review text; use the safe report API for ordinary
exports. Future full-text exports need the same private access and applicable
arrangements as the database. File permissions are verified; disk encryption
and protection against compromise of the host administrator are not certified.

Server statement/duration logging is disabled; error statements and parameter
values are suppressed, error verbosity is terse, and logs are private. SQLAlchemy
echo remains off and bound parameters hidden. The exercised permission errors
and synthetic full-text operations left no synthetic title/body marker,
credential or connection-URL marker in server logs. This is an observed check
of the tested paths, not a claim that every possible future error is safe.

## Start, stop and read-only preflight

Use the existing project environment. These commands operate only the dedicated
project instance; they do not start a collector:

```sh
/usr/lib/postgresql/16/bin/pg_ctl -D /home/l2838/.local/share/data-source-feasibility/postgresql/16 status
/usr/lib/postgresql/16/bin/pg_ctl -D /home/l2838/.local/share/data-source-feasibility/postgresql/16 -l /home/l2838/.local/state/data-source-feasibility/logs/startup.log -w -t 30 start
# Only when an operator intends to stop the project database:
/usr/lib/postgresql/16/bin/pg_ctl -D /home/l2838/.local/share/data-source-feasibility/postgresql/16 -m fast -w -t 30 stop
```

Run only the desired action, not all three in sequence. Do not run a second
start against an already running instance or initialize an existing data directory.

For the same SELECT-only preflight used in deployment:

```python
import json
from pathlib import Path
from feasibility.apple_ingestion.deployment import load_config, deployment_engine, preflight

private = Path('/home/l2838/.config/data-source-feasibility')
config = load_config(private / 'deployment.json')
environment = json.loads((private / 'connection.env.json').read_text())
owner = deployment_engine(config, 'owner', environ=environment)
runtime = deployment_engine(config, 'runtime', environ=environment)
try:
    with owner.connect() as audit, runtime.connect() as actual_runtime:
        print(json.dumps(preflight(audit, config, for_live=True,
            environ=environment, runtime_connection=actual_runtime), indent=2))
finally:
    runtime.dispose()
    owner.dispose()
```

The expected current result is database-ready **and live-blocked**, not an empty
blocker list. This code does not create a Session, run, request or receipt.

## Backup and restore

Manual logical backups are appropriate for this bounded local pilot. Take one
before/after future authorized collection or maintenance, keep a checksum and
paired private configuration/role metadata, and periodically test restore in a
separate database. There is no scheduler or automatic backup deletion policy.
This is not continuous archiving or point-in-time recovery.

The current verified main backup is:

`/home/l2838/.local/state/data-source-feasibility/backups/apple_ingestion-20261103T114508Z.dump`

It is a 40,351-byte custom-format full logical database dump, mode `0600`, with
SHA-256 `bfe2c9022ceaf4f021da9992484ba6122232cee21491802fdc2b2a81b460de60`.
It contains seeds only. The adjacent `.manifest.json` records checksums, the
`.roles.sql` is a **password-free** role creation plan, and the
`.private-config.tar.gz` contains private configuration, credentials and
diagnostic/receipt state. Protect that archive as credentials; never publish it.
An earlier seed-only dump from the initial probe is also retained.

For a future backup, set a fresh absolute `backup_file` in the private backup
directory. Refuse an existing filename; retain new versions rather than
overwriting a known backup:

```sh
umask 077
export PGSERVICEFILE=/home/l2838/.config/data-source-feasibility/pg_service.conf
export PGPASSFILE=/home/l2838/.config/data-source-feasibility/pgpass
unset PGHOST PGPORT PGDATABASE PGUSER PGPASSWORD PGSERVICE PGOPTIONS PGSSLMODE
# Set backup_file to a new dated path in the private backup directory.
: "${backup_file:?Set a new private absolute backup path}"
test ! -e "$backup_file" || exit 1
/usr/lib/postgresql/16/bin/pg_dump --dbname='service=apple_ingestion_owner' --format=custom --file="$backup_file"
/usr/lib/postgresql/16/bin/pg_restore --list "$backup_file" >/dev/null
sha256sum "$backup_file"
```

`pg_restore --list` alone is not a restore test. The actual deployment proof
created a fresh isolated database owned by the maintenance role, revoked PUBLIC
database access, granted the three accounts CONNECT, and used:

```sh
# restore_database must be a separately created verification database, never
# apple_ingestion. backup_file must be the selected verified dump path.
: "${restore_database:?Set the new isolated verification database}"
test "$restore_database" != apple_ingestion || exit 1
/usr/lib/postgresql/16/bin/pg_restore --exit-on-error --single-transaction --dbname="service=apple_ingestion_owner dbname=$restore_database" "$backup_file"
```

Roles must exist before restoring their ownership/grants. On this dedicated
cluster an operator can create a fresh verification database using
`createdb --maintenance-db='service=apple_ingestion_admin' --owner=apple_ingestion_owner NAME`,
then use the admin service in that new database to revoke PUBLIC and grant only
the three intended CONNECT privileges. Choose a fresh verification name. Do not
use `--clean`, restore over the live database, copy a running data directory, or
silently switch a runtime URL to a restored database.

Before promoting any recovery, check revision, seven tables, actual logins and
grants, seed/target states, integrity and backup checksums. Keep targets disabled
and project execution disabled; the dump may contain the historical enablement state
from when it was taken, so verify/reset it through an explicitly authorized
maintenance transaction **before** considering collection. Restoring old
policy state must never authorize replay: retain uncertainty, recheck the actual
current project conditions/scope/window and follow existing recovery rules.
Legacy receipt records are not required by the new project workflow.
Do not resume an RSS page or retry automatically after a recovery.

Both main dump restore and an additional full-text synthetic dump restore were
actually executed, not just listed. The latter remains clearly separated at
`backups/validation/SYNTHETIC_ONLY-20261103T114508Z.dump`; it is not a source-data
backup and must not be restored into the collection database. The fresh proof
databases were dropped after verification. Local copies on the same WSL disk
help with operator mistakes but do not protect against loss of that entire
disk/WSL distribution. A protected second storage location and its access rules
remain an operational decision before relying on the pilot for durable evidence.

## Future retention changes

`long_term` means no preset expiry, not irrevocable retention under every future
obligation. The responsible project owner must confirm applicable access and
retention arrangements and revisit them when scope or obligations change.
No invented periodic deletion deadline is implied by the existing
`expiry_review_ref` field; here it references this change/request handling process.

If deletion, restricted access or a finite duration becomes necessary, first
pause collection and identify the affected relational history, full-text
exports, backup generations and restore paths. Review an FK-safe maintenance
plan, authorized scope and verification record; retain runtime's no-delete
boundary. Update policy and future backup/restore handling together. Do not
infer source deletion from window disappearance or rewrite historical versions
to hashes. No purge tool or destructive retention operation was added here.

## Tests and evidence

Main-chat full regression, using a **separate temporary test cluster**, not the
persistent deployment:

```sh
PYTHONNOUSERSITE=1 APPLE_TEST_PYTHON=/home/l2838/miniconda3/envs/data-source-feasibility/bin/python bash scripts/test_apple_ingestion_postgres.sh --full-suite -q --junitxml=/tmp/apple-persistent-full-suite.xml
```

**640 passed in 65.99 seconds; 0 failures, 0 errors, 0 skipped, no pytest
warnings.** This includes all original tests, 33 deployment cases (previously
25) and 50 live-readiness cases (previously 48). New coverage checks legacy
finite-day compatibility, explicit long-term/null-day validation, technical
versus arrangement readiness, and unconfirmed long-term rejection before HTTP
Session/receipt/run creation. A template-discovery test now names deployment
templates precisely rather than treating the unrelated approval template as a
deployment config. No historical feasibility test was removed.

Persistent verification was separate: actual roles and permissions, exact
schema/seed, diagnostic probe, clean postmaster restart, unchanged cluster
identifier/database OID/counts, offline page checksums, logical backup and
isolated restore. Full-text proof used only isolated synthetic databases:
27,010-character title, 272,012- and 272,040-character bodies, two versions and
two observed-version references. Values and 32-byte hashes survived restore.
All ten fake request operations were injected in-process; no socket to Apple
was created. Main database history remains empty.

The first isolated verification probe used an incorrect standalone `run_mode`
column in a verification query. It was corrected to read the approved immutable
`config_snapshot` JSON field; the fresh verification passed. This required no
schema or Pipeline change. Its temporary database was cleaned up.

Private detailed records are `initialization-evidence.json` and
`verification-evidence.json` in the configuration directory. Sanitized working
copies are `/tmp/apple-persistent-initialization.json` and
`/tmp/apple-persistent-verification.json`; temporary paths are convenience
artifacts, not the only durable evidence. Source changes remain uncommitted on
`main`, HEAD `474736abcee2a67f186299f09d196125400eb1ab`.

## Current operational boundary and remaining validation

1. Actual project execution remains disabled and its technical ID/window have
   not been populated; all eight targets remain disabled. A later operator action
   must enable only the intended smoke scope. This task does not perform it.
2. Actual Feed structure and external DNS/TLS behavior remain untested. The
   bounded smoke must inspect its actual result; legitimate unsupported nested
   content stops for correct support, rather than record skipping.
3. Applicable data-use and long-term-retention considerations remain documented
   for review with John. They are not software preflight blockers or mandatory
   approval records, and this correction does not mark them confirmed.

The previously missing local host, database, roles, private operational paths
and tested local backup/restore now exist. Same-disk backup limitations and
manual post-WSL startup remain explicit operational limits. Windows-native
execution, full WSL reboot, real source coverage, human assessment and seven-day
live continuity are not claimed. **Stop after this deployment preparation.**

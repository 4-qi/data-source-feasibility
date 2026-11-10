# Apple ingestion deployment

## Environment

The pilot used Ubuntu under WSL, PostgreSQL 16 and the shared
data-source-feasibility Conda environment with Python 3.12. The database is a
dedicated persistent instance, separate from the disposable clusters used for
tests.

| Component | Configuration |
| --- | --- |
| Database | apple_ingestion |
| PostgreSQL data | /home/l2838/.local/share/data-source-feasibility/postgresql/16 |
| Connection | Private Unix socket, port 55440 |
| Maintenance role | apple_ingestion_owner |
| Runtime role | apple_ingestion_runtime |
| Reporting role | apple_ingestion_report |
| Private configuration | /home/l2838/.config/data-source-feasibility/ |
| Private state | /home/l2838/.local/state/data-source-feasibility/ |

The existing Alembic migration initializes seven ingestion tables. The original
eight applications and US/mostrecent targets are seeded. Credentials remain
outside the repository.

## Access and storage

The maintenance role manages initialization and controlled administration.
Collection uses the runtime login; reporting uses the read-only login.
Version history is append-only for the runtime role. SQL parameter logging is
suppressed, and diagnostic and backup storage is private.

The long_term configuration retains complete title/body versions and observations
without a preset expiry or scheduled TTL. Disappearance from a feed window does
not delete history. Applicable data-use and retention conditions remain
unresolved in the [access and retention record](archive/PHASE_E_ACCESS_RETENTION.md).

## Verification

The persistent deployment passed migration, seed, actual-login, permission,
full-text storage and restart checks. The final technical audit verified
4,507 stored versions, database integrity and the original Smoke evidence.
All 14 daily backups matched their recorded checksums. The final backup was
restored into an isolated database, checked and removed.

Backups remain on the same local WSL storage. Independent-storage and
whole-machine recovery were outside the demonstrated validation scope.

## Deployment and recovery references

The [detailed deployment record](archive/APPLE_INGESTION_LOCAL_DEPLOYMENT.md)
retains initialization, startup, permission, backup and restore commands.
The [deployment runbook](archive/PHASE_E_DEPLOYMENT_RUNBOOK.md) preserves the
configuration contracts and preparation checks.
The [technical validation](APPLE_INGESTION_TECHNICAL_VALIDATION.md) records final
database and backup evidence.

At the end of the pilot, all collection targets, the project execution policy
and both Windows scheduled tasks were disabled.

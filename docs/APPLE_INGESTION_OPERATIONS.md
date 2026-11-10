# Apple ingestion operations

## Completed pilot

The pilot ran November 3–9, 2026, with one sequential eight-application batch
per day at 09:00 America/Los_Angeles (17:00 UTC). Seven actual daily batches
produced 56 persisted application runs. Windows Task Scheduler launched the
existing Ubuntu/WSL environment and project Conda interpreter.

Both Apple-Phase-F-Days-2-7 and Apple-Phase-F-Closeout are disabled following
the final batch. The retirement marker is present, the project execution
configuration is disabled and all eight collection targets are disabled.

## Execution controls

The fixed scope used the original eight apps, US storefront and mostrecent
ordering. Each target/run used 2–5 logical pages, no more than ten HTTP requests,
zero automatic retries, at least two seconds between requests, bounded timeouts
and the approved overlap stopping criteria.

The scheduler ignored overlapping task instances and disabled automatic
catch-up, retries and on-demand starts. The WSL operator used a shared process
lock and an exclusive daily invocation record. Missed slots were recorded
without backfilling. Failed or uncertain invocations were retained without
automatic replay.

Each batch enabled only the pilot scope for execution and disabled it during
cleanup. Source-denial and recovery conditions retained their existing stop
behavior. Immutable configuration snapshots identified the code and policy
used by each run.

## Evidence and diagnostics

Daily evidence records planned and actual UTC start times, application/run IDs,
request attempts, committed pages, review actions, overlap, reference intervals,
coverage, integrity and cleanup. Routine reports omit review bodies, author
information and credentials. Full-text review versions remain in PostgreSQL;
human reading materials and responses remain in private project storage.

The [technical validation](APPLE_INGESTION_TECHNICAL_VALIDATION.md) contains
the per-run evidence index and anomaly analysis.
The [review quality assessment](APPLE_REVIEW_QUALITY_ASSESSMENT.md) documents
the completed 80-review assessment.

## Environment constraints

The verified Windows task mode required the account to remain signed in and
supported a locked desktop. S4U registration was denied with 0x80070005.
Wake timers were enabled, but physical sleep/wake and whole-machine recovery
were not demonstrated. The project PostgreSQL instance could be started by
the WSL operator if stopped.

## Supporting operating records

- [Fixed schedule and collection protocol](archive/APPLE_PHASE_F_PILOT_PROTOCOL.md)
- [Unattended task setup and verification](archive/APPLE_PHASE_F_UNATTENDED.md)
- [First smoke procedure](archive/APPLE_FIRST_LIVE_SMOKE_TEST.md)
- [Todoist smoke result](archive/APPLE_TODOIST_LIVE_SMOKE_RESULT.md)
- [Day 1 result](archive/APPLE_PHASE_F_DAY1_RESULT.md)
- [Database startup, backup and restore](archive/APPLE_INGESTION_LOCAL_DEPLOYMENT.md)

These archived files preserve setup-time and execution-time states. The
completed pilot's disabled state is recorded above.

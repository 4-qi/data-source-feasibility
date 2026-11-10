# Phase F — seven-day actual-observation protocol

Authorized scope: original eight Apple applications, US, `mostrecent`, one
sequential batch per planned day. Implementation baseline `d5eefe3`; no new
source/table/service or ingestion algorithm. Day 1 completed under the one-time wakeup. The subsequent authorization
activates only the six remaining Windows Task Scheduler slots below.

## Fixed schedule

Time zone: `America/Los_Angeles`. First available future 09:00 at planning time
was November 3, 2026. Compute each local calendar date with IANA timezone rules;
all seven dates below are PST (UTC−08:00). Do not replace local calendar scheduling
with a UTC assumption for future extensions crossing DST.

| Day | Planned local start | Planned UTC start | Actual UTC start |
| --- | --- | --- | --- |
| 1 | 2026-11-03 09:00 PST | 2026-11-03 17:00Z | 2026-11-03 17:00:50.412440Z |
| 2 | 2026-11-04 09:00 PST | 2026-11-04 17:00Z | Not observed |
| 3 | 2026-11-05 09:00 PST | 2026-11-05 17:00Z | Not observed |
| 4 | 2026-11-06 09:00 PST | 2026-11-06 17:00Z | Not observed |
| 5 | 2026-11-07 09:00 PST | 2026-11-07 17:00Z | Not observed |
| 6 | 2026-11-08 09:00 PST | 2026-11-08 17:00Z | Not observed |
| 7 | 2026-11-09 09:00 PST | 2026-11-09 17:00Z | Not observed |

The reusable technical policy window is `[2026-11-03T17:00:00Z,
2026-11-10T17:00:00Z)`. This covers seven scheduled dates, not permission for an
eighth daily batch or a rolling retry loop. Actual invocation/batch/run starts,
completion and delay seconds are recorded in private metadata; public reports
contain only safe IDs/counts/times. Never populate future actual timestamps.

No early start, catch-up batch or compressed/simulated day is allowed. If Day 1
delivery is delayed on its local date, record the actual start, delay and reason;
do not claim 09:00 precision. If its local calendar date has passed, mark the slot
missed instead of backfilling. An interrupted/failed invocation is reported, not
automatically retried. Later dates need their own actual scheduled invocation.

The Day 1 desktop wakeup was retired after execution. Windows Task Scheduler
now owns Days 2–7. The current Windows account must stay signed in. A locked
session is supported and the Codex app is not needed. Windows requests a wake
timer, subject to the machine's power settings. Shutdown, sign-out or a
disabled wake timer can cause a missed slot. The scheduler and WSL checks are
recorded in the [unattended operations runbook](APPLE_PHASE_F_UNATTENDED.md).

The private operator procedure uses only the existing collection/report APIs:

```sh
PYTHONNOUSERSITE=1 /home/l2838/miniconda3/envs/data-source-feasibility/bin/python /home/l2838/.local/state/data-source-feasibility/phase-f/execute_day1.py
```

Its actual-clock guard was checked before 09:00: `waiting_not_started`, zero
HTTP, no invocation record. A local exclusive invocation record prevents a
second batch; it is scheduling/idempotency evidence, not an approval credential.
Do not start a manual duplicate alongside the scheduled invocation. The plan,
active policy revision, operation record, pending assessment and backups remain
private outside Git. Day 1 completed; see the metadata-only
[actual Day 1 result](APPLE_PHASE_F_DAY1_RESULT.md). Later days remain unobserved.

## Fixed order and limits

1. Todoist — `572688855`
2. Microsoft To Do — `1212616790`
3. Duolingo — `570060128`
4. Khan Academy — `469863705`
5. Amazon Shopping — `297606951`
6. Etsy — `477128284`
7. Uber — `368677368`
8. Lyft — `529379082`

Preserve this manifest order and effective settings for all dates. Minimum two,
maximum five logical pages; at least 20 overlapping IDs AND 20% for the existing
overlap stop; maximum ten physical HTTP requests per target including fallback;
zero automatic retries; at least two seconds between requests on one shared
sequential transport; existing 10/25-second HTTP limits, 2,000,000-byte response
cap and 900-second target deadline. No volume expansion or lower thresholds.
There are 56 planned target slots, at most 560 planned HTTP-budget slots, not
56 already completed runs or evidence that every request will be made.

The existing `Controller.run_batch` stops subsequent apps on source denial or
infrastructure/recovery conditions. Preserve its skipped/missing outcomes rather
than forcing all eight targets to finish or inventing records. Each day's batch
gets a runtime UUID; future batch IDs/actual run IDs remain unset until execution.

## Preserve and distinguish the smoke evidence

Retain smoke run `e9cf632f-9c1a-45de-9b2f-fdf5e995211e`, batch
`360bde73-ef0a-4e71-a195-dbad7b6cfdca`, its 250 complete versions and 250
observations. Never reset/reinitialize the database. Private metadata binds each
formal pilot date to its own batch UUID, so smoke is excluded from seven-day
slot/request totals. Immutable smoke version/observation checksums are checked
after Day 1; review current pointers/last-seen times can legitimately advance.

Do not alter reference selection to separate cohorts: a later Todoist run can
legitimately use the eligible smoke run. Day 1's Todoist reference interval is
then about four hours, **not a cross-day 24-hour observation**. Record actual
same-app/reference start intervals and age in the report. Daily delays and
sequential per-app timing shift the observed overlap window; no timing/coverage
normalization or completeness claim is invented. Other apps may establish their
first baselines. Insufficient overlap does not disqualify a clean comparison
reference; >72h is a warning, not automatic exclusion.

## Day 1 operator sequence

1. At/after the planned time, check the current project scope and applicable
   conditions; report any concrete applicable restriction or unresolved
   execution prerequisite. Do not fabricate data-use/retention clearance. The
   bounded private research scope is unchanged; no text publication/training.
   The bounded Day 1 operation was authorized; this
   is not recorded as Apple permission or a data-use/retention determination.
2. Verify actual PostgreSQL, real restricted logins, seven-table migration,
   diagnostic permissions, current smoke preservation and no prior Day 1 batch.
   Take a private backup. Before this time leave project/targets disabled.
3. Enable only the eight manifest targets and the existing `purpose=pilot`
   technical policy; call the existing `prepare_project_controller` and
   `Controller.run_batch` exactly once, with snapshots in the fixed order.
4. Record planned/actual UTC times, delay and source/technical stop outcomes.
   Read-only validate each run's attempts/pages/status, first actions, overlap,
   reasons, fingerprints, versions/observations, reference intervals and integrity.
5. Check retained smoke versions/observations, save safe metadata/private backup,
   and prepare the pending private human sample. No raw text in normal reports.
6. Disable the pilot policy and all targets after this single batch; leave later
   days unexecuted until separately scheduled. The Day 1 report records
   the state at completion before the later authorization.

## Human usefulness assessment and final reporting

Use the existing deterministic `build_sample`/`export_assessment` protocol on
actual LIVE data after Day 1, at an actual cutoff, up to ten reviews per app.
Export only into a private 0700 directory with 0600 files. Labels remain
`PENDING_HUMAN`; usefulness/sentiment is not inferred by the collector or Codex.
The interim sample uses the actual LIVE corpus available at cutoff, including
retained smoke-supported reviews under the existing sampling rule. State that
provenance; it is not a claim that every sampled review was observed by Day 1's
formal batch. Daily cohort metrics remain strictly separated by batch UUID.

The existing U0–U3 rubric, full-text reading declaration, language handling,
ratings-hidden material and optional second-reviewer subset remain unchanged.
Final sampling/reporting follows actual Day 7 data; it cannot be completed now.
The final evidence report must account for all seven planned slots, actual times,
missing/skipped/failed runs, request budgets, actual intervals/overlap, new versus
unchanged/changed observed versions, conflicts, integrity, private backups and
human assessment status. Successful smoke/JSON does not prove all-app/Atom
compatibility, source edit identity/order or complete review coverage.

Data-use and long-term-retention questions remain in
[the project review memo](PHASE_E_ACCESS_RETENTION.md) as unresolved project conditions.
This operational schedule records no approval, licensing or retention-rights
confirmation. No commit/push is authorized.

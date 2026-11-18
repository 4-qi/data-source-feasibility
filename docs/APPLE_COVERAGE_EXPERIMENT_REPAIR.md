# Coverage Experiment Runner Repair and Replacement Series

> The replacement series completed all seven observations.
> [Final results](APPLE_COVERAGE_EXPERIMENT_RESULTS.md).

## Outcome

The isolated experiment runner defects were corrected and the full regression
suite passed **737 tests**. The failed original W0 was recovered to a consistent
terminal state without another Apple request. A separate replacement series was
then activated, following explicit confirmation, for **November 13, 2026 at
21:00 PST through November 16 at 21:00 PST**.

The old series is retired and its hold was not released. Its failed W0 is
separate diagnostic evidence, not the replacement baseline. No Apple requests
were made during repair, recovery, Windows entry checks or activation. New W0
will run only at its scheduled time.

## Root cause and correction

The runner passed one `now()` value to request-completion persistence and a
second value to `persist_page`. Reconciliation correctly requires the selected
attempt's `finished_at` to equal the page's observation timestamp. With a
progressing real clock, the two values differed. The earlier integration clock
advanced during simulated request spacing but not between those two calls,
which concealed the defect.

The caller now captures `observed_at` once for each response and reuses it for
that response's completed attempt and selected page transaction. JSON fallback
and the selected Atom response retain their own distinct response timestamps.
Reconciler validation, UTC precision and page-transaction boundaries are unchanged.

A healthy-session reconciliation precondition failure now retains an allowlisted
safe detail code and finalizes the run as failed/partial as appropriate, with
the uncommitted attempt resolved. Connection or commit uncertainty continues to
use the existing recovery path; it is not converted into fabricated certainty.

The CLI also distinguishes normal JSON output from operational success:

| Outcome | Process exit |
| --- | ---: |
| Successful observation or successful maintenance operation | 0 |
| Failed, partial, interrupted, recovery-required or blocked observation; failed readiness; exception | 1 |
| No eligible due observation | 2 |

The existing Windows wrapper forwards that exit status. Cleanup still disables
the target and closes sessions/engines. No production Controller, Reconciler,
reference selection, Atom parser, migration or core schema was modified.

## Original W0 recovery

Original study: `72a1a0cf-fef5-454e-937e-145add238d24`.
Original run: `182e9527-ae24-472b-8ba5-4abc9e46d042`.
Database: `apple_coverage_main_20261113`.

| Evidence | Preserved result |
| --- | --- |
| Scheduled W0 | November 13, 09:00 PST |
| Actual slot entry | 2026-11-13T17:00:05.272290Z |
| HTTP requests | 1 |
| Response | HTTP 200; JSON parsed successfully |
| Parsed entries | 50 |
| Committed pages / reviews / versions / observations | 0 / 0 / 0 / 0 |
| Recovered run status | `interrupted` |
| Recovered coverage status | `indeterminate` |
| Selected attempt persistence | `rolled_back` |

Recovery used the existing `application_session`, `replay_spool` and
`recover_interrupted` functions under the application lock. The actual request
start/completion times, HTTP status, parsed count and response-byte metadata
remained identical. The original generic spool diagnostic and failure-sidecar
contents were preserved; the confirmed caller defect is documented separately.
The immutable run snapshot still identifies the original source revision.

A second recovery pass imported zero new events and recovered zero additional
runs. The database still contains exactly one run and one attempt, with no review
or observation rows. Integrity checks passed with zero pending attempts. Spool
bytes and the original seven-day pilot's ordered-row digest were unchanged.
No request was replayed and no source response or successful baseline was invented.

The old manifest is disabled and retired, with `hold=true`. Its remaining planned
slots were cancelled at study level, not relabelled as observations or backfilled.
`Apple-Coverage-72h` and `Apple-Coverage-Closeout` remain disabled, as do both
original eight-app pilot tasks.

## Regression and entry verification

- **45 targeted tests passed** in 40.14 seconds, including all existing coverage
  experiment tests and 19 new repair regressions.
- **737 complete regression tests passed** in 124.59 seconds, using disposable
  PostgreSQL and synthetic responses with external test sockets blocked.
- Advancing-clock and actual progressing UTC tests verified ten successful
  page transactions with and without JSON/Atom fallback. Stored attempt and
  observation timestamps match exactly while successive pages have different times.
- Deliberately mismatched timestamps remain rejected. The experiment caller
  persists a failed terminal run, preserves response metadata and commits no page.
- Recovery preserves response metadata, is idempotent, and creates no duplicate
  request, review version or observation.
- Subprocess tests verify actual OS exit codes, not only a Python helper result.
  Cleanup/hold behavior and suppression of unsafe exception messages are covered.
- Temporary Windows tasks exercised the exact replacement action through WSL:
  readiness returned **0**; a disabled observation returned **1** before any
  request or invocation marker. Both temporary tasks were removed. The replacement
  database remained empty throughout these checks.

Pinned replacement source SHA-256:
`71bc3f36c53bb50857c2419902adb1ec9b92a8c55a867e8ceb8fad6156c4edbe`.

## Replacement identity and schedule

Study: `ae32055e-e3c9-4f3b-9150-8d91e18a257f`.
Database: `apple_coverage_main_20261113_2100`.
Private state directory: `coverage-main-20261113-2100` under the existing private
project state root.

The database was initialized with the existing Alembic migration, seven core
tables and existing least-privilege maintenance/runtime/report roles. All live
history starts empty. The original eight-app seed is retained, but only the
Duolingo target is within the executable scope; all targets remain disabled
between observations.

| Observation | Planned PST start | Planned UTC start |
| --- | --- | --- |
| W0 | November 13, 21:00 | 2026-11-14T05:00:00Z |
| W1 | November 14, 09:00 | 2026-11-14T17:00:00Z |
| W2 | November 14, 21:00 | 2026-11-15T05:00:00Z |
| W3 | November 15, 09:00 | 2026-11-15T17:00:00Z |
| W4 | November 15, 21:00 | 2026-11-16T05:00:00Z |
| W5 | November 16, 09:00 | 2026-11-16T17:00:00Z |
| W6 | November 16, 21:00 | 2026-11-17T05:00:00Z |

`Apple-Coverage-R2-72h` and `Apple-Coverage-R2-Closeout` are the active tasks.
Their actions use the replacement state directory and pinned tested source.
The closeout task has checks 30 minutes after each observation and a current-user
logon trigger. Exclusive locks, `IgnoreNew`, zero retries/restarts, no catch-up
and the existing clock/validity safeguards remain in effect.

Scope remains Duolingo `570060128`, US, `mostrecent`, contiguous pages 1–10,
maximum 20 physical HTTP requests per observation and 140 across this series.
The old failed request is accounted for separately and does not create an
observation or reference in the new series. The earlier probe allowance is not
transferred. Timeouts, response limits, two-second spacing, stopping conditions,
reference rules and independent five-page validity are unchanged.

The final offline analysis task has been moved to **November 16, 22:00 PST
(November 17, 06:00 UTC)**. It reads only actual replacement evidence, excludes the
old failed W0 from all A/B/C/D baselines, and reports diagnostic request cost
separately. It does not collect data or implement adaptive scheduling.

## Readiness and retained evidence

Clock, database identity, source pin, entry exit status, task commands and exact
triggers passed before activation. The new database had zero runs and attempts;
all seven slots were unstarted. There were no remaining activation blockers.
Normal Windows Interactive-logon, WSL/PostgreSQL and local report-app availability
requirements remain as documented in the
[activation record](APPLE_COVERAGE_EXPERIMENT_ACTIVATION.md).

Private recovery and replacement evidence includes `w0-before-recovery.json`,
`w0-recovery.json`, `replacement-readiness.json`, `scheduler-preparation.json`,
`windows-entry-verification.json` and the replacement `activation.json`.
No private review text, credentials or assessment labels were added to reports.
No Git commit or push was performed.

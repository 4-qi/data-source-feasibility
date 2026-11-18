# Duolingo Coverage Experiment Activation

> The replacement series completed all seven observations.
> [Final results](APPLE_COVERAGE_EXPERIMENT_RESULTS.md).

## Current status

The original series recorded below failed at W0 and was recovered, stopped and
retired. Its activation facts are retained as history. The replacement series
was activated for November 13 at 21:00 PST through November 16 at 21:00 PST;
see the [repair and replacement record](APPLE_COVERAGE_EXPERIMENT_REPAIR.md) for
the current database, source revision, task names and final-analysis time.

## Original activation status

The approved 72-hour experiment was activated on **2026-11-12 at
22:54:29.847831 UTC**. Activation enabled the existing private experiment
manifest and the two prepared Windows tasks. It did not invoke the collector,
reserve an observation or send an Apple request.

Study: `72a1a0cf-fef5-454e-937e-145add238d24`.
Database: `apple_coverage_main_20261113`.
Pinned source SHA-256:
`92a74cb3a9e9936730732ce74732029fe3d8bac177aac6db1498e243fcd812da`.

The [experiment plan](APPLE_HIGH_VOLUME_COVERAGE_EXPERIMENT.md),
[engineering readiness](APPLE_COVERAGE_EXPERIMENT_READINESS.md) and
[clock validation](APPLE_CLOCK_RELIABILITY_VALIDATION.md) remain the applicable
technical records. No implementation, tests, parser rules or database schema
changed during activation; the accepted 718-test source baseline is unchanged.

## Verified activation checks

- The existing `entry.sh verify` passed the real database/role, seven-table
  migration, safe-diagnostics and integrity checks without creating an HTTP
  session.
- Current clock check: wall 2.000099 s, monotonic 2.000101 s and raw 2.000106 s;
  Windows UTC and WSL UTC were consistent in the activation check. The validated
  single-clock-owner configuration remains applicable.
- The source digest matched the accepted baseline. Scheduled action commands
  matched the prepared commands, including automatic retirement actions.
- All seven observation triggers and seven closeout times matched the approved
  manifest. `IgnoreNew`, zero automatic restarts, no catch-up, and Interactive
  logon settings were retained.
- The isolated database contained zero runs, attempts, reviews, versions and
  observations. All targets were disabled. Ordered-row digests confirmed the
  original pilot was unchanged.

These are activation-time facts, not future observation results.

## Active observation schedule

Timezone: America/Los_Angeles; all dates below are PST (UTC−08:00).

| Observation | Planned local start | Planned UTC start |
| --- | --- | --- |
| W0 | 2026-11-13 09:00 | 2026-11-13T17:00:00Z |
| W1 | 2026-11-13 21:00 | 2026-11-14T05:00:00Z |
| W2 | 2026-11-14 09:00 | 2026-11-14T17:00:00Z |
| W3 | 2026-11-14 21:00 | 2026-11-15T05:00:00Z |
| W4 | 2026-11-15 09:00 | 2026-11-15T17:00:00Z |
| W5 | 2026-11-15 21:00 | 2026-11-16T05:00:00Z |
| W6 | 2026-11-16 09:00 | 2026-11-16T17:00:00Z |

At activation, Windows reported:

| Task | State | Next scheduled UTC |
| --- | --- | --- |
| `Apple-Coverage-72h` | Enabled / Ready | 2026-11-13T17:00:00Z |
| `Apple-Coverage-Closeout` | Enabled / Ready | 2026-11-13T17:30:00Z |
| `Apple-Phase-F-Days-2-7` | Disabled | None |
| `Apple-Phase-F-Closeout` | Disabled | None |

The next authorized observation is W0. No observation was started early.

## Scope and unattended operation

Only Duolingo (`570060128`), US storefront, `mostrecent` is in scope. Each
invocation acquires one due observation and contiguous pages 1–10, with at most
20 physical requests including JSON/XML fallback. The main study cap remains
140, with zero retries, at least two seconds between requests and the existing
10/25-second timeouts, response-size bound and 900-second target deadline.

The database target intentionally remains disabled between observations.
The existing operator enables only the isolated Duolingo target inside the
actual invocation and disables it in cleanup. Enabling it during activation
would violate the existing disabled-target preflight. The other seven targets
and the original pilot remain disabled.

The exclusive file/application locks, pre-dispatch reservations, immutable run
snapshots and duplicate-slot protection remain in force. Failures preserve
committed pages and diagnostics, place subsequent slots on hold according to
the approved rules, and never trigger automatic retry, backfill or rescheduling.
Independent five-page analytical validity remains separate from full-depth run
status and production reference eligibility.

Windows must be running with the configured user signed in; the tested route
uses Interactive logon. Existing wake and missed-slot handling remain unchanged.
No new collection scheduler or service was added.

## Completion and final analysis

The existing W6/terminal closeout path runs the offline comparer, writes private
`comparison.json` and `technical-report.md`, retires the execution manifest and
disables both experiment tasks. Closeout also has a current-user logon trigger
for missed-execution accounting. No missing observation is fabricated or replayed.

One separate offline report task is scheduled in the existing project chat for
**November 16, 2026, 10:00 PST (18:00 UTC)**, after the planned W6 and closeout.
Its identifier is `duolingo-72-hour-experiment-final-analysis-nov-16`. It performs
no collection and has no authority to enable targets, retry slots or extend
the experiment. It reads actual evidence and prepares
`APPLE_COVERAGE_EXPERIMENT_RESULTS.md`, including:

- A/B/C/D primary, supplementary and common-endpoint comparisons;
- fixed-depth continuity and request costs, separate early-stop replay;
- independent prefix validity, failures and coverage uncertainty;
- a bounded daily-deeper versus twice-daily-shallower recommendation;
- implications for future per-app adaptation, without implementation.

Incomplete evidence produces a partial/inconclusive report. The report task
runs once and then stops. Local reporting requires the computer and desktop app
to remain running; this does not change the Windows collection task's execution
path. See the [official scheduled-task documentation](https://learn.chatgpt.com/docs/automations?surface=app).

Private `activation-preflight.json` and `activation.json` retain activation
checks and actual task state. The original pilot and assessment records remain
unchanged. Activation records technical execution scope and does not invent
project-level data-use or retention confirmations. No commit or push occurred.

# Phase F unattended operations

Windows Task Scheduler task `Apple-Phase-F-Days-2-7` is enabled with six
one-time triggers at 09:00 America/Los_Angeles, 17:00 UTC, on November 4–9,
2026. The next trigger on readback was November 4 at 09:00 PST. The existing
eight-app scope, fixed order, project policy and limits are specified in the
[pilot protocol](APPLE_PHASE_F_PILOT_PROTOCOL.md). Earlier observations remain
separate and intact. See the [Day 1 result](APPLE_PHASE_F_DAY1_RESULT.md).

Each action uses hidden, noninteractive PowerShell to invoke the following
command under the signed-in Windows account. No Codex session is needed.

```powershell
& "$env:SystemRoot\System32\wsl.exe" -d Ubuntu -u l2838 --exec /usr/bin/env PYTHONNOUSERSITE=1 /home/l2838/miniconda3/envs/data-source-feasibility/bin/python /home/l2838/.local/state/data-source-feasibility/phase-f/execute_scheduled.py --scheduled
```

The private operator reuses the Day 1 procedure and existing controller.
It starts only the dedicated persistent PostgreSQL instance if stopped,
checks the current roles and immutable Day 1 and Smoke rows, takes a private
backup, enables the eight scoped targets and invokes the existing controller
once. The operator disables the project policy and targets after each batch.
Windows ignores overlapping instances, disables on-demand start, and has
zero retries or catch-up launches. A WSL process lock and an exclusive daily
invocation marker protect against duplicate dispatch. The task accepts only
the scheduled date and a start before 09:10 PST, including preflight time.
This ten-minute bound is an operator dispatch limit. The collection request
limits and per-target deadlines are unchanged.

The enabled `Apple-Phase-F-Closeout` task runs the same command with
`--maintenance` at sign-in and has one final maintenance trigger at 09:00 PST
on November 10. That mode cannot collect. The next scheduled invocation or
sign-in records elapsed slots as missed or interrupted using the private
invocation records. No slot is backfilled. If an interruption leaves controls
enabled, the next operator invocation disables the scoped policy and targets
and records the interrupted slot for review. A source stop or recovery-required
outcome holds subsequent live collection. No failed or uncertain slot is
replayed.

Daily private metadata under
`/home/l2838/.local/state/data-source-feasibility/phase-f/dayN/` records
planned and actual UTC, application and run IDs, attempts, committed pages,
new/changed/unchanged counts, overlap and actual reference intervals, coverage,
fingerprints, integrity and cleanup. The operator retains backups and human
sample exports privately. Reports carry no review text or credentials. Use
the actual same-app reference interval when interpreting delayed starts.

After Day 7, the operator verifies the disabled state, generates
`phase-f-technical-report.md` and its JSON companion in the private state
directory, and disables both Windows tasks. If the last slot was missed,
closeout occurs when the maintenance task can next run. The report accounts
for every planned slot and any failures or missing days. Human labels remain
pending. Project data-use and long-term retention questions remain unresolved.
See the [project review memo](PHASE_E_ACCESS_RETENTION.md).

## Activation evidence

- Task Scheduler accepted and started a temporary task using the current
  Windows identity and the Ubuntu distribution. Its actual WSL action started
  the existing PostgreSQL 16 cluster from a stopped state. The owner, runtime
  and report connections, schema and role preflight, disabled targets and
  preserved historical evidence passed. The probe made zero Apple requests.
- A second temporary task invoked the exact production Windows action with
  the schedule inactive and exited successfully. The account demonstrated
  task retirement permissions by disabling the probe. The probe was removed.
- Six isolated guard checks exercised early dispatch, maintenance-only dispatch,
  today's slot selection, the lateness cutoff, next-day missed-slot accounting
  and an already completed day. These checks did not invoke the live collector.
- Windows readback showed both tasks ready, with wake enabled, no automatic
  retries, no catch-up, no on-demand start, and `IgnoreNew` overlap behavior.
  Day 2 had not started at activation.

Windows denied S4U registration with `0x80070005`. The verified mode launches
automatically while the user is signed in, including with the desktop locked.
A logged-out or powered-off computer cannot run these tasks. A full WSL
shutdown and physical wake from sleep were not exercised. No new scheduler
service, database or source was introduced.

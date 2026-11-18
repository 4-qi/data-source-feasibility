# Clock Reliability Validation

## Result

Clock readiness passed on November 12, 2026. The original November 13–16
observation schedule remains usable. The experiment is still disabled; this
investigation sent no Apple requests and created no collection observations.

The transport spacing check passed independently of the raw-clock comparison.
A separate, reproducible WSL UTC discontinuity required an environment repair.
The repair removed competing clock adjustment in the current Ubuntu distribution;
no collector, parser, comparison algorithm, database schema or request limit changed.

## Clock use

| Purpose | Implementation |
| --- | --- |
| Global request spacing | Existing `BoundedTransport`, default `time.monotonic()` and `time.sleep()` |
| Absolute target deadline | Same monotonic clock, 900 seconds |
| Per-attempt and total duration | Monotonic elapsed time; transport duration includes spacing waits |
| Connection/read timeout | Existing relative 10/25-second timeout values passed to requests; installed urllib3 also uses `time.monotonic()` for connection timing |
| Planned observations | Windows Task Scheduler; 09:00/21:00 America/Los_Angeles, stored with explicit UTC instants |
| Actual observations and database timestamps | Timezone-aware `datetime.now(timezone.utc)`; PostgreSQL UTC sessions |
| Raw clock | Diagnostic comparison, not the transport's rate-limiter clock |

Different monotonic/raw elapsed values alone do not demonstrate a spacing defect.
Actual call boundaries were measured separately using the transport's own clock.
No historical request or observation timestamp was corrected or replaced.

## Confirmed findings and repair

The initial local test exercised ten mock HTTP calls, including five JSON-to-Atom
fallbacks. All nine monotonic start intervals passed: 2.002490–2.065366 seconds.
At the same time, bounded Windows/WSL handshakes demonstrated an independent
wall-clock problem: one Windows UTC interval advanced 0.973 seconds while WSL UTC
went backwards by 0.067969 seconds. Its monotonic elapsed time was 1.003847 seconds.
This was an actual UTC discontinuity, not an inference from raw-clock disagreement.

Earlier preparation measurements remain historical evidence:

| Measurement before repair | WSL wall elapsed | WSL monotonic elapsed | Raw / Windows comparison |
| --- | ---: | ---: | --- |
| Preparation cross-check | 14.0874 s | 15.6539 s | Difference −1.5665 s |
| Earlier streamed interval | 0.4101 s | 2.1101 s | Raw 2.0053 s; Windows 2.006 s |
| Entry check at 2026-11-12T22:13:17Z | 2.003117 s | 2.003118 s | Raw 1.952023 s |

These observations justified investigation; they are not retrospective
measurements of the probe's HTTP start boundaries.

Read-only kernel measurements showed matching libc and direct-syscall clock
values, excluding the Python wrapper as the source of that observation. Kernel
time discipline also showed a nonstandard tick value. Linux derives its NTP
frequency from the tick setting and frequency correction, so resetting one
readiness flag would not repair the underlying clock. See the
[Linux NTP implementation](https://raw.githubusercontent.com/torvalds/linux/v6.6/kernel/time/ntp.c).

A bounded trace in a temporary, isolated trace instance recorded both `chronyd`
and Ubuntu's `systemd-timesyncd` issuing clock-adjustment syscalls. A one-time
standard-tick reset did not hold while both adjusters were active. The existing
WSL system chrony interface reported a PHC0 reference.

The controlled repair stopped Ubuntu's duplicate `systemd-timesyncd`, leaving
WSL's existing chronyd and its configuration unchanged. Clock discipline needed
time to converge: the first short control interval still drifted and was not
accepted. Subsequent measurements showed the tick restored to 10000 microseconds,
normal small frequency correction, stable UTC alignment and matching elapsed clocks.
The Ubuntu unit was then persistently disabled with:

```sh
wsl.exe -d Ubuntu -u root --exec systemctl disable --now systemd-timesyncd
```

Its verified final state is `disabled` and `inactive`; its prior state was
`enabled` and `active`. This establishes one existing clock-discipline owner.
No new time service was installed, no WSL clocksource was changed, and the
Windows Time service was not modified. Temporary kernel tracing was removed.
The exact history of how both adjusters became active was not investigated.

## Direct post-repair measurements

The unmodified transport performed five local logical pages, deliberately
falling back from empty JSON to valid synthetic Atom on each page:

| Measurement | Result |
| --- | --- |
| Mock physical calls / fallback calls | 10 / 5 |
| Apple calls | 0 |
| Successive starts on rate-limiter monotonic clock | 2.000093–2.000214 s; all nine at least 2 s |
| Successive starts on raw clock, diagnostic only | 2.000093–2.000214 s |
| Steady Windows/WSL alignment | 24 bounded handshakes, conservative offset bounds within 2.6 ms |
| Wall-clock reversals after convergence | None in the measured interval |
| Existing entry's final clock check | Wall 2.000110 s; monotonic 2.000112 s; raw 2.000120 s; passed |

The initial handshake includes PowerShell process startup and is excluded from
steady-state alignment statistics. Each remaining handshake records the Windows
UTC sample and both WSL request/response bounds; transport delay is not treated
as clock offset.

A real, temporary one-shot Windows task then verified scheduled invocation:

| Event | UTC |
| --- | --- |
| Planned trigger | 2026-11-12T22:40:37.3452637Z |
| Windows action started | 2026-11-12T22:40:38.0046204Z |
| WSL helper entered | 2026-11-12T22:40:38.069335Z |
| Windows action returned | 2026-11-12T22:40:38.1596940Z |

The action started 0.659 seconds after its planned instant. WSL's aware UTC
entry timestamp fell inside the Windows action interval. The task exited 0
and was removed. Task Scheduler's separate `LastRunTime` field has coarser
precision; the action's high-resolution timestamp establishes the actual delay.
Neither the real experiment task nor its closeout task was enabled.

## Tests and execution boundaries

The focused regression selection passed **32 tests** in 20.86 seconds, covering
transport spacing across formats, timeout/deadline behavior, request safeguards,
timezone/DST conversion, early/expired/duplicate invocation rejection, source
integrity, missed slots, quotas and retirement. Internet sockets were blocked.
The direct real-clock mock tests above supplemented these deterministic tests.

The accepted **718-test** complete regression remains applicable: implementation
and tests did not change during this investigation. The pinned source digest
remains `92a74cb3a9e9936730732ce74732029fe3d8bac177aac6db1498e243fcd812da`.
The existing `entry.sh verify` also passed actual PostgreSQL role, schema,
diagnostic and integrity checks with `real_http_performed=false`.

The existing ten-minute start window, study validity window, duplicate-slot
protection, source-integrity check, monotonic spacing/deadlines and operational
clock guards remain intact. No missed observation is backfilled. The seven
prepared UTC instants still correspond to November 13 09:00 through November 16
09:00 PST, exactly 12 hours apart. The main budget remains 140 requests.

Current clock readiness is established; future arbitrary sleep/resume or
external time-service changes are not certified by this short validation.
The existing runtime preflight and guards remain necessary. Interactive Windows
logon and the existing WSL/PostgreSQL prerequisites are unchanged. No whole-WSL
shutdown or cold-restart experiment was performed during this investigation.

Private evidence includes the timestamped `focused-clock-*.json` measurements,
`clock-adjustment-trace.json`, `clock-tick-repair.json`,
`clock-single-owner-control.json`, `clock-single-owner-repair.json`, and
before/after `clock-task-invocation` receipts. They contain timing and operational
metadata only. Collection history, review text and assessment data were unchanged.

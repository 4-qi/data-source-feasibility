# Phase F — Day 1 actual collection result

Day 1 completed successfully on 2026-11-03. Exactly one sequential eight-application
batch ran against the persistent local PostgreSQL deployment. This is **one of
seven planned observation days**, not a completed seven-day validation.

Implementation baseline: `d5eefe333bf1bbe85c5d30ea5a364dc2ed320df1`.
Batch: `83f488fa-b705-4c9d-b51d-7f380b5749e1`.

## Timing and scope

- Planned: **2026-11-03 09:00 America/Los_Angeles**, `2026-11-03T17:00:00Z`.
- Operator invocation: `2026-11-03T17:00:50.114579+00:00`.
- Actual batch start: `2026-11-03T17:00:50.412440+00:00`.
- Verification report completion: `2026-11-03T17:02:01.734027+00:00`.
- Start delay: **50.412440 seconds**. Planned-to-operator invocation took
  50.114579 seconds (scheduler wakeup, inspection and dispatch); final procedure
  preflight before batch start took 0.297861 seconds. The first component is not
  a measurement of scheduler delivery latency alone.
- US storefront, `mostrecent`, fixed manifest order; minimum two/maximum five
  logical pages, maximum ten HTTP requests per target, zero automatic retries,
  shared transport with at least two seconds between requests. Existing timeouts,
  fallback, stop conditions and database transaction protections were retained.

## Actual runs

All eight runs `succeeded`; none failed or was skipped. HTTP 200 count equals
request count for every application. Overlap is observed ID overlap, not proof
of complete source coverage.

| Application | Run ID | HTTP / pages | Observations | New / changed / unchanged | Overlap IDs / ratio | Coverage / stop |
| --- | --- | ---: | ---: | ---: | --- | --- |
| Todoist (`572688855`) | `5a12a0f1-abf9-4d19-b41b-93f09d29f253` | 2 / 2 | 100 | 0 / 0 / 100 | 100 / 100% | `overlap_sufficient` / `overlap_met` |
| Microsoft To Do (`1212616790`) | `4d26620b-1141-49d5-91de-af97856f06f5` | 5 / 5 | 250 | 250 / 0 / 0 | — | `baseline` / `page_budget` |
| Duolingo (`570060128`) | `988b3813-74e2-44cf-abbb-c63a90d0e7e1` | 5 / 5 | 250 | 250 / 0 / 0 | — | `baseline` / `page_budget` |
| Khan Academy (`469863705`) | `52fa95d8-f081-4b31-8b4e-5c413c423bfc` | 5 / 5 | 250 | 250 / 0 / 0 | — | `baseline` / `page_budget` |
| Amazon Shopping (`297606951`) | `9dc01631-eda2-4c03-b4c0-958a2ca4ddd9` | 5 / 5 | 250 | 250 / 0 / 0 | — | `baseline` / `page_budget` |
| Etsy (`477128284`) | `787025a2-f9bc-47df-b667-ea440e2d341a` | 5 / 5 | 250 | 250 / 0 / 0 | — | `baseline` / `page_budget` |
| Uber (`368677368`) | `c0b60412-33a9-4f34-8475-13b53a181eb7` | 5 / 5 | 250 | 250 / 0 / 0 | — | `baseline` / `page_budget` |
| Lyft (`529379082`) | `c45228a3-af9e-4d1e-a868-193d97d4fb01` | 5 / 5 | 250 | 250 / 0 / 0 | — | `baseline` / `page_budget` |

Totals: **37 HTTP requests, 37 committed pages, 1,850 observations; 1,750
new-to-database reviews/versions, 0 changed and 100 unchanged**. New-to-database
reviews are not necessarily newly published reviews. There were zero HTTP,
transport or parse failures, unresolved attempts, disputes or duplicate
occurrences. The seven baseline runs have reason `BASELINE_ANCHOR`; no prior
reference exists for them, so overlap is unmeasured rather than zero.

Todoist references the retained smoke run
`e9cf632f-9c1a-45de-9b2f-fdf5e995211e`. Actual start-to-start interval was
**3.9410601864 hours**, on the same local date. Its 100 matching IDs met the
approved overlap stop after two pages. This does **not** establish cross-day
coverage, edit behavior or complete review coverage. Future same-app intervals
must use actual run starts, including this day's delay and sequential offsets.

## Verification and retained evidence

- Existing read-only integrity report: `ok=true`; all six issue counters zero;
  no running pending request attempts. No source deletion was inferred.
- **1,850 observed versions checked; zero fingerprint mismatches**, validating
  stored title/body and version fingerprint consistency for this batch without
  publishing private review text in this report.
- Original smoke evidence preserved: **250 versions and 250 observations**;
  saved immutable-row checksums still match. Smoke remains historical evidence,
  separate from this batch's run/request totals.
- Private before/after database backups created. Before: 102,141 bytes, SHA-256
  `9513686fc503a38ea769ec2e1dbeef50bfa22d4ccfa3aede1eb7388cca5ec97f`.
  After: 459,193 bytes, SHA-256
  `75bc4689f43db00afe8111a7c378129ca2f449c6a313311317077b9f2c09e11f`.
  These backup files contain private data and are outside the repository.
- Safe metadata: private `phase-f/day1/day1-verification.json` and
  `execution-outcome.json` under the existing local project state directory.
  Diagnostics, raw review exports and credentials remain outside Git.
- Cleanup verified: **pilot execution disabled; all eight targets disabled**.
  No second invocation, automatic retry or later-day collection was performed.

## Human assessment and remaining limitations

The existing deterministic protocol exported an interim actual-LIVE sample:
**80 selected from 2,000 eligible reviews; 0 assessed, 80 pending**, no shortfall.
Six selected records are supported by retained smoke evidence. The sample uses
the actual corpus through Day 1, rather than claiming all sampled records were
observed in the formal Day 1 batch. Full text stays in the private export;
labels remain pending human review and no usefulness rate is reported.

Sample manifest SHA-256:
`5505a714d827a71c762f4d21e77c9445d0c70ca15729987e23f995843594d9e6`.

No concrete execution blocker was reported. Data-use and long-term-retention
questions remain documented as unresolved project conditions; this successful run
is not a confirmation of data-use or retention rights. Cross-day overlap,
observed edits, later-day stability and human usefulness remain unverified.
The single Day 1 wakeup is retired after handling this result. Days 2–7 remain
unexecuted and unscheduled; no Phase F completion claim, code commit or push.

# Duolingo pagination feasibility probe

## Result

The single bounded probe completed on November 12, 2026 using seven physical
requests of the fourteen-request allowance. Pages 1, 5, 6, 7, 8, 9 and 10 were
requested once in that order for Duolingo (570060128), US, mostrecent.

Every response was HTTP 200 and strict JSON parsing succeeded. Each page
contained 50 distinct review IDs, with 350 distinct IDs across the probe.
Pages 6–10 supplied 250 additional IDs relative to the sampled anchors and
preceding deep pages. No Atom fallback, duplicate occurrence, conflicting
occurrence, empty page or parsing failure occurred. The stop reason was
requested_pages_completed.

Depth ten is supported by the tested deep pages at this observation time.
No smaller K was forced by the evidence. Pages 2–4 were intentionally not
requested, so this probe does not establish a complete contiguous ten-page
window or novelty relative to those omitted pages. It does not establish a
maximum source pagination cap, stability across times or improved overlap.

## Actual page outcomes

Novel IDs are relative to all previously observed pages in this probe.

| Page | Response | Distinct IDs | Novel IDs | Duplicate occurrences | Earliest source timestamp UTC | Latest source timestamp UTC |
| --- | --- | ---: | ---: | ---: | --- | --- |
| 1 | JSON / 200 | 50 | 50 | 0 | 2026-11-11T02:17:20Z | 2026-11-11T11:09:20Z |
| 5 | JSON / 200 | 50 | 50 | 0 | 2026-11-10T02:33:39Z | 2026-11-10T11:56:42Z |
| 6 | JSON / 200 | 50 | 50 | 0 | 2026-11-09T23:54:24Z | 2026-11-10T02:26:27Z |
| 7 | JSON / 200 | 50 | 50 | 0 | 2026-11-09T22:07:51Z | 2026-11-09T23:54:02Z |
| 8 | JSON / 200 | 50 | 50 | 0 | 2026-11-09T19:47:06Z | 2026-11-09T22:06:11Z |
| 9 | JSON / 200 | 50 | 50 | 0 | 2026-11-09T12:30:30Z | 2026-11-09T19:43:08Z |
| 10 | JSON / 200 | 50 | 50 | 0 | 2026-11-09T03:04:08Z | 2026-11-09T12:26:59Z |

There were no ascending source-timestamp inversions within any sampled page.
The source-time ranges of successive sampled pages were also ordered without
interleaving. The page 1-to-5 boundary skips three pages. These observations
support the encountered ordering only; they do not prove permanent chronological
ordering, original publication times or a complete review history.

Probe ID: d5ad4e57-346a-4b20-b08b-7b5db57b665a.
Recorded UTC start: 2026-11-12T17:27:49.707964+00:00.
Recorded UTC finish: 2026-11-12T17:28:00.551528+00:00.
Total response size: 283,522 bytes.
The monotonic observation duration was 12.444449 seconds.

The UTC start/finish difference was 10.843564 seconds, differing from the
12.444449-second monotonic duration. The measurements indicate a wall-clock
discontinuity or timing-domain discrepancy during the probe; its underlying
cause was not established. Request spacing uses the unchanged monotonic
transport clock. Per-attempt duration_seconds measures the complete transport
call, including spacing waits; attempt started_at is the durable dispatch
intent timestamp, not an exact HTTP send timestamp. The main experiment's
preflight must check clock synchronization and record this distinction.

## Implementation and offline validation

The isolated module
[pagination_probe.py](../src/feasibility/apple_ingestion/pagination_probe.py)
reuses BoundedTransport, IngestionConfig, parse_feed, canonical_fields and
fingerprint, including the existing privacy-safe parser diagnostics.
Its app and page sequence are fixed. Request intents and results are written
to an fsynced private checkpoint before another request is permitted.
A per-evidence lock and exclusive reservation reject repeated invocation,
including after an uncertain result write. The live operator additionally
held the existing cross-process collection lock.

The probe writes a private diagnostic manifest rather than non-contiguous
collection_run or fetch_attempt rows. The isolated database was initialized
using the existing Alembic migration, eight-app seed and restricted roles.
A reporting connection checked its identity and schema using SELECT-only
transactions. Probe evidence stores IDs, normalized fingerprints, source-time
metadata and aggregate outcomes. It stores no titles, bodies, authors or raw
responses.

Targeted validation recorded **16 passed** in 1.70 seconds with a disposable
PostgreSQL cluster. The complete regression recorded **692 passed** in
92.06 seconds. Tests cover deep-page novelty, repeated/duplicate-only pages,
same-page duplicates, conflicts, empty/malformed feeds, strict nested-XHTML
rejection, fallback, fourteen-request success, budget exhaustion, HTTP denial
and redirects, durable-intent failure/no replay, database isolation and
independent five/ten-page prefix eligibility after a tail failure.
Production controller, live policy, schema, parser and normalizer were unchanged.

One outer preflight invocation failed before entering the probe because the
pilot checksum serializer did not handle PostgreSQL Decimal values.
The probe reservation did not exist and no HTTP was reachable at that stage.
The failure record was retained, the serializer was corrected and the still
unexecuted probe was then run once. No source request was retried.

## Evidence isolation and final state

The private probe database is apple_coverage_probe_20261112. Its seven tables
contain only seed data: zero collection_run and zero fetch_attempt rows, with
all targets disabled. The completed diagnostic is identified by the probe UUID,
not a formal pilot run ID.

All seven original pilot tables were hashed before and after the probe using
the reporting role. The digests matched. The retained pilot still contains
57 runs, 160 attempts, 4,507 reviews and versions, and 7,600 observations.
The earlier seven-day results, human labels and Smoke evidence remain intact.

Both original Windows tasks remain disabled. No main-experiment schedule was
created. The diagnostic's exclusive reservation remains consumed, its private
operator records execution_disabled=true, and no additional run is automatic.
The PostgreSQL service was restored to its pre-task stopped state.

Private evidence is retained under
coverage-pagination-probe-20261112 in the existing project state directory.
The probe.json SHA-256 is
10c7a4e7fda88ad2176849af845bb7b2e966be75c7cfebdaf3b699603fb5a8ae.
The original-source digest verification and safe aggregate summary are retained
alongside it. Raw review text and credentials are excluded from public artifacts.

## Main-experiment depth and remaining readiness

The observed results support **ten pages as the maximum-depth candidate** for
the shared 72-hour study, subject to review and a contiguous 1–10 check at T0.
Fixed five-page prefixes and ten-page windows can then support the four planned
12/24-hour comparisons. Five pages remain an independently evaluable strategy
even if a later page fails. No existing result establishes which interval/depth
combination gives better continuity.

The probe used seven requests. The unchanged main-study ceiling is 140 requests,
so this probe plus a maximum-cost main study would use at most 147 actual
requests within the original 154-request envelope. Unused probe allowance does
not expand the number of observations or the per-observation budget.

The isolated fixed-depth acquisition/lifecycle driver and offline lag/depth
comparer still need implementation and synthetic/PostgreSQL validation. The
current production live policy still rejects 12-hour, ten-page or twenty-request
profiles, and the production controller still stops early on sufficient overlap.
No production settings were relaxed for the probe.

Before scheduling, review the probe, bind the absolute seven observation times,
verify clock behavior and validate the isolated main-study entry. The
[experiment plan](APPLE_HIGH_VOLUME_COVERAGE_EXPERIMENT.md) defines the fixed
design; the [adaptive design note](APPLE_ADAPTIVE_COLLECTION_STRATEGY.md)
retains escalation/cooldown/de-escalation numbers as unvalidated hypotheses.

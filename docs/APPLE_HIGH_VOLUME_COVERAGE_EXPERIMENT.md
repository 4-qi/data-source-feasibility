# High-volume Apple review collection: coverage experiment

> The replacement series completed all seven observations.
> [Final results](APPLE_COVERAGE_EXPERIMENT_RESULTS.md).

## Objective and status

This proposed follow-up compares fixed collection depth and interval for
Duolingo (570060128), using the US storefront and mostrecent ordering. Its
purpose is to identify a bounded configuration with more reliable observed
window continuity and to inform a future per-application adaptive policy.

The design was reviewed with independent prefix-level analytical eligibility.
Step 1's single pagination probe completed on November 12, 2026: seven JSON
requests returned 350 distinct IDs across pages 1, 5 and 6–10. See the
[probe result](APPLE_PAGINATION_FEASIBILITY_PROBE.md). The main 72-hour experiment
was initially activated for November 13–16, 2026. After its W0 failed in the
caller, a corrected independent series was activated for **November 13 at
21:00 PST through November 16 at 21:00 PST**. See the
[repair and replacement record](APPLE_COVERAGE_EXPERIMENT_REPAIR.md). The
[original activation](APPLE_COVERAGE_EXPERIMENT_ACTIVATION.md) and
[readiness record](APPLE_COVERAGE_EXPERIMENT_READINESS.md) remain supporting
history. The completed seven-day pilot is preserved.

## Existing evidence

The [technical validation](APPLE_INGESTION_TECHNICAL_VALIDATION.md) records the
seven-day results. A fresh SELECT-only audit of the persistent pilot database
confirmed the following Duolingo outcomes.

| Day | Parsed/committed pages | Requests | Shared IDs / current distinct IDs | Reference interval | Classification |
| --- | ---: | ---: | --- | ---: | --- |
| 1 | 5 | 5 | No reference | — | Baseline |
| 2 | 5 | 5 | 25/250, 10% | 23.984941 h | Insufficient |
| 3 | 3 | 3 | 31/150, 20.67% | 24.000186 h | Sufficient; overlap stop |
| 4 | 5 | 5 | 0/250, 0% | 23.999818 h | Insufficient |
| 5 | 5 | 5 | 48/250, 19.2% | 24.000289 h | Insufficient |
| 6 | 0 | 2 | Unusable window | 24.000215 h | Failed parsing |
| 7 | 5 | 5 | 0/250, 0% | 48.000540 h | Insufficient |

All 160 fetch attempts in the pilot database, including the earlier Smoke,
had page numbers at most five. No retained source response establishes the
availability, novelty or stability of pages 6–10. Existing URL construction
and configuration types accepting a page number do not establish source support.

Microsoft To Do succeeded on all seven days. After its initial five-page
baseline, two-page observations shared 98–99 of 100 IDs at approximately
24-hour intervals. This supports limiting the experiment to Duolingo.
No new control application is included in the proposed request budget.

The historical Day 3 three-page window is early-stop censored. Its result is
not an observation of a full five-page window. Day 7 compared against Day 5
because Day 6 was unusable. Historical figures motivate the experiment; they
do not supply its new 12-hour or ten-page measurements.

## Candidate strategies

| Strategy | Nominal interval | Fixed diagnostic depth | Comparisons |
| --- | ---: | ---: | --- |
| A: baseline configuration | 24 h | 5 pages | Five-page windows 24 h apart |
| B: deeper | 24 h | 10 pages, conditional on feasibility | Ten-page windows 24 h apart |
| C: more frequent | 12 h | 5 pages | Five-page windows 12 h apart |
| D: combined | 12 h | 10 pages, conditional on feasibility | Ten-page windows 12 h apart |

A uses the original interval and maximum depth, but fixed-depth acquisition
differs from production's overlap early stop. All four primary comparisons use
fixed-depth windows. An explicitly separate offline analysis estimates the
production stopping rule's depth and request cost.

One shared deepest observation at each time supplies both depth prefixes.
There are no parallel strategies or duplicate baseline requests.

## Implementation constraints

The inspected implementation at commit 28b44bc has these boundaries.

| Component | Existing behavior | Study consequence |
| --- | --- | --- |
| IngestionConfig and seven-table schema | Positive configurable interval, depth and request budget; no schema maximum of five | Twelve hours, ten pages and twenty requests fit the existing storage contracts |
| ProjectExecutionConfig | Requires interval_hours=24, max_pages<=5, max_http_requests<=10; smoke is one app and pilot is all eight | Candidate B/C/D settings are rejected by the current live entry |
| Controller._validate | Accepts exact approved live-policy classes | An injected arbitrary policy/subclass is not an authorized shortcut |
| Controller._validate_target | Requires snapshot settings to match the actual target | An in-memory depth override alone is insufficient |
| Controller.run_target | Stops after the first threshold-satisfying committed prefix | A complete ten-page observation cannot be guaranteed |
| BoundedTransport | Fixed host/path, no credentials/redirects, zero retries, bounded streaming and global spacing | Reuse unchanged with a separately bounded experimental caller |
| Parser/normalizer/persist_page | Strict full-page parsing, fixed fingerprints and page transactions | Reuse unchanged; duplicate Atom content still fails |
| Reference and coverage functions | Reference eligibility independent of sufficient overlap; ratio denominator is the current window | Reuse the formulas without changing the production reference chain |

Changing thresholds, forging configuration, changing run_mode to synthetic,
monkeypatching policy validation or disabling the production overlap stop would
invalidate this study.

The smallest proposed implementation is one isolated fixed-depth diagnostic
entry plus an offline comparison command. It composes existing transport,
parser, normalizer, application-session locking, reconciliation, diagnostic
recovery and reporting primitives. It needs an explicit, tested technical scope
check for the experiment because the production factory rejects these settings.
This check is limited to app, endpoint, window, fixed depth, request accounting
and enablement; no administrative approval service is involved.

A new orchestration loop is required even though the reusable components exist.
It must preserve durable pre-request intents, database identity/role checks,
no open database transaction during HTTP, same-session page ownership,
terminal-state handling and cleanup. It must not copy a second parser or
reconciler, subclass the production controller to fake overlap metrics, or
claim the current factory can execute the design without changes.
Any need to change shared production behavior is a review point before implementation.

## Separate pagination feasibility probe

The proposed probe runs once before the main schedule, with no historical-pilot
writes. Its exact request sequence is page 1, page 5, then pages 6, 7, 8, 9 and
10, sequentially, all for Duolingo. Page 1 is a current anchor; page 5 is the
boundary anchor. Pages 2–4 are omitted to bound the initial feasibility cost.

Each selected page first requests JSON. Only a valid JSON feed with no review
entries permits one XML fallback for that same logical page, matching the
existing format policy. A malformed JSON page, HTTP failure or timeout is not
retried through another format.

The cap is seven logical page slots and **14 physical requests**, with zero
retries, at least two seconds between starts, 10-second connect and 25-second
read timeouts, a 2,000,000-byte response cap and a 900-second observation deadline.
The fourteen-request cap is a proposed explicit experiment limit, not a change
to the production ten-request limit. Both time and request limits apply.

Record each page's parsed entry count, distinct IDs, new IDs relative to all
earlier probe pages, duplicate/conflicting occurrences, format and source-time
ranges. Detect exact page-ID-set repetition, duplicate-only deep pages, empty
feeds, malformed entries and timestamp-order inversions. Raw bodies and author
fields are not saved. Private full review versions can be retained in the
isolated database under the existing seven-table contracts.

The probe stops immediately on denial/rate limit, unexpected redirect, other
HTTP failure, timeout, unsupported structure, persistence/recovery failure,
selected empty page, conflicting occurrence or a duplicate-only deep page.
No later page is used to evade the stop. Mixed overlap at page boundaries is
recorded rather than automatically treated as a cap.

A successful page 10 requires valid review retrieval with new IDs relative to
the observed probe anchors/deep pages, not HTTP 200 alone. It only establishes
bounded availability at that time. Because pages 2–4 are absent, probe novelty
does not prove independence from those pages. The first full observation checks
the complete contiguous 1–10 sequence; every later observation repeats that check.

If all requested pages through 10 are usable, propose depth 10 for the main
study. If an apparent cap or repetition ends the probe earlier, a verified
contiguous deep prefix through K, where 6<=K<10, can support a separately
reviewed 5-versus-K design. Otherwise use only five pages at 12/24 hours.
Denial, parser or infrastructure failure blocks the probe and requires review;
it is not evidence that a particular pagination depth is unsupported.
The main depth is sealed before T0 and remains fixed for all seven observations.
A later depth failure yields indeterminate deeper comparisons rather than an
automatic switch to a different strategy. If even a valid contiguous five-page
window cannot be acquired, A/C are not fully evaluable; report that limitation
rather than relabelling a shorter window as five pages.

The probe remains a separate feasibility event and is not T0.

## Proposed real-time schedule

After probe review and offline readiness checks, bind T0 to the next agreed
09:00 or 21:00 America/Los_Angeles slot. The active replacement uses 21:00. Require at least two hours between the probe
and T0 for review and configuration. Record seven explicit future instants;
do not schedule from an unreviewed example date.

| Observation | Elapsed plan | Local slot | Comparison pairs available |
| --- | ---: | --- | --- |
| W0 | T0 | Day 1, 21:00 | Initialization only |
| W1 | +12 h | Day 2, 09:00 | W1/W0, 12 h |
| W2 | +24 h | Day 2, 21:00 | W2/W1, 12 h; W2/W0, 24 h |
| W3 | +36 h | Day 3, 09:00 | W3/W2, 12 h; W3/W1, 24 h |
| W4 | +48 h | Day 3, 21:00 | W4/W3, 12 h; W4/W2, 24 h |
| W5 | +60 h | Day 4, 09:00 | W5/W4, 12 h; W5/W3, 24 h |
| W6 | +72 h | Day 4, 21:00 | W6/W5, 12 h; W6/W4, 24 h |

For dates in the current PST period, 09:00 is 17:00 UTC and 21:00 is 05:00 UTC
the next date. If the agreed dates cross a time-zone transition, calculate and
publish actual UTC instants and elapsed intervals before enabling the study.

The primary 24-hour trajectory uses W0,W2,W4,W6: three transitions.
The offset W1,W3,W5 trajectory contributes two supplementary 24-hour pairs.
The 12-hour trajectory supplies six transitions. Compare frequency on the same
current windows W2,W4,W6 using lag-one versus lag-two references, as well as
reporting every pair. The five lag-two pairs are dependent observations, not
five independent experiments.

Windows Task Scheduler with the existing WSL environment or an explicit manual
procedure can invoke a single observation driver. No new scheduling service is
required. Reuse process locks, exclusive invocation markers, default-disabled
scope and finally cleanup. Permit a start only in [planned, planned+10 minutes);
record delay and all actual timestamps. Unavailable or missed slots are recorded,
never backfilled. No automatic replacement observation or extension beyond W6.

## Acquisition and comparison definitions

Let P(i,p) be the ID set from committed page p of observation i.
For depth d, let S(i,d)=union(P(i,1),...,P(i,d)).
Repeated IDs are counted once for set metrics. Their occurrences, first
positions, versions and any conflicts remain recorded separately.

For an actual comparison i versus j at the same depth d:

- Shared count O(i,j,d)=|S(i,d) intersection S(j,d)|.
- Current count N(i,d)=|S(i,d)|.
- Overlap ratio R(i,j,d)=O(i,j,d)/N(i,d), undefined when N=0.
- Relative-new IDs E(i,j,d)=|S(i,d) minus S(j,d)|.
- Sufficiency requires at least two processed pages, O>=20 and R>=0.20,
  with complete usable required prefixes and no consistency/blocking cautions.

Reuse coverage_metrics with both same-depth sets. E measures new-to-comparison
IDs, not new publications or necessarily new-to-database records. Report database
new/changed/unchanged actions separately; shared acquisition makes them
dependent on all prior experimental observations, not a standalone A/B/C/D run.

Both current and reference prefixes must have all requested pages committed
and validated. Mark a missing, empty, failed, conflicting or interrupted
required window indeterminate. Do not divide by the planned page capacity,
treat missing IDs as zero overlap, or lower thresholds. A clean window with too
few distinct IDs gets the existing low-volume reason codes.

Analytical eligibility is evaluated independently for each required prefix,
in both current and reference observations. Complete, internally consistent
pages 1–5 remain eligible for the primary five-page comparison if page 6 or
later fails. The ten-page comparison is indeterminate and the overall
acquisition remains partial/failed, with its diagnostics retained. An anomaly
invalidates the five-page prefix only if it affects that prefix's trustworthiness,
such as a later conflicting occurrence of an ID already present in pages 1–5,
unknown commit state or corrupted evidence. A tail parse failure alone does not.

Prefix-level analytical references do not change stored reference_run_id or
production reference eligibility. A partial/failed full run is never promoted
to a successful ten-page run or to an eligible production reference. Report
overall reliability and prefix-specific evaluability/sufficiency separately.
The offline comparer must test both prefixes independently, including the
case of five valid pages followed by a page-six Atom error.

Use the specified lag-one or lag-two window, not the most recent available
window at a different interval. An invalid required prefix in the lagged observation makes that strategy pair
indeterminate; a failure outside that prefix does not automatically do so. A separate recovery analysis may compare with the last usable
experimental window using its actual longer interval. That is not counted as
the missing 12/24-hour pair. Stored reference_run_id follows the existing clean
latest-reference rules; additional analytical references are explicit in the
comparison metadata.

More depth does not mathematically guarantee a higher ratio: adding mostly
non-overlapping IDs can dilute the denominator. Record every prefix from two
pages through the acquired maximum and do not stop at the first success during
fixed-depth acquisition.

## Production early-stop analysis

For each strategy's clean historical experimental reference, evaluate the
unchanged count/ratio predicates after each acquired current prefix k>=2.
Record the first satisfying k and the physical attempts consumed through k.
If none meets them, record the depth cap. Compare a current prefix to the
reference window that the strategy would actually have retained.

A trajectory replay must carry forward that strategy's own previous stopped
prefix and existing reference eligibility, starting with a full-depth baseline
when no eligible experimental history exists. Looking only at full-depth
references would underestimate or overestimate production stopping cost.
For the 24-hour primary trajectory, do not inject the intervening 12-hour
windows into its reference chain.

This is offline predicate replay of acquired evidence. It cannot prove the
responses that a separately executed early-stopping collector would have
received, reproduce omitted requests after a failed fixed-depth run, or
manufacture a successful production run. Incomplete counterfactual inputs
remain indeterminate. Report fixed-depth findings and replay results separately.

## Metrics and safe evidence

Each observation manifest records study/app/snapshot/run UUIDs, planned and
actual UTC start, each page request's start/end/duration, total duration,
requested/reached/committed depth, format/fallback, physical request intent and
known response counts, HTTP/parse/persistence outcomes and stop reason.
Request timing is a new safe sidecar field; existing fetch_attempt start/end
also include orchestration and diagnostic work.

Record ordered per-page IDs and fingerprints privately, distinct counts,
cross-page duplicate counts, additional deep IDs, min/max source_updated_at,
missing source timestamps, ordering violations and page-boundary interleaving.
Do not equate feed updated timestamps with publication or ingestion latency.
The seven-table observation's first_observed_page supports prefix ID unions,
but not all later duplicate positions or their text variants. Preserve safe
page-level occurrence projections during acquisition rather than trying to
reconstruct all order anomalies from aggregate counts later.

Public output contains aggregated counts, times, reasons and opaque run IDs.
No raw response, source review text, author, credential or response-derived
exception message appears in Git or ordinary logs. Diagnostic error categories
retain the existing allowlisted field names and entry positions.

## Request-cost accounting

There are no retries or duplicate acquisitions for A–D. Reserve a request
before each physical attempt, including fallback. An unknown send outcome
consumes its reserved allowance; it never earns a replacement request.
The main ledger persists across process restarts. The completed probe has a
separate immutable ledger; its seven used requests remain separate and none of
its unused seven-request allowance is transferable to the main study.

| Scope | Valid JSON-only planning cost | Physical hard cap |
| --- | ---: | ---: |
| One seven-slot pagination probe | 7 | 14 |
| One ten-page observation | 10 | 20 |
| Seven ten-page observations | 70 | 140 |
| Complete proposed ten-page study including probe | 77 | **154** |
| Seven five-page observations, if depth is unavailable | 35 | 70 |
| Five-page alternative including the full probe allocation | 42 | **84** |

A partial probe can spend fewer requests, but the maximum remains reserved.
A K-page alternative costs 7+7K JSON-only requests with a 14+14K hard cap.
No control requests are allocated. Adding one would require an explicit amended
budget, not use of an unused Duolingo allowance.

For standalone fixed-depth strategy costs, excluding the separate probe:

| Strategy | Windows on the primary 72 h trajectory | JSON-only total | Hard cap | Steady-state requests/day, JSON / cap |
| --- | ---: | ---: | ---: | ---: |
| A | 4 x 5 pages | 20 | 40 | 5 / 10 |
| B | 4 x 10 pages | 40 | 80 | 10 / 20 |
| C | 7 x 5 pages | 35 | 70 | 10 / 20 |
| D | 7 x 10 pages | 70 | 140 | 20 / 40 |

The horizon includes the initial observation at both interval choices.
Relative to A, finite-horizon JSON costs are +20, +15 and +50 for B,C,D;
hard-cap differences are +40,+30,+100. Steady-state differences are
+5,+5,+15 JSON requests/day and +10,+10,+30 maximum requests/day.
Requests per observation and per day use actual consumed attempts in final
analysis; startup-inclusive cost/3 elapsed days is a separate statistic.

Five-page cost from shared acquisition counts attempts through page five,
including JSON/XML fallback. Ten-page cost includes all attempts. Report
counterfactual early-stop costs separately from this full-depth table.
Budget and timeout exhaustion may yield fewer than ten usable pages even with
twenty permitted requests. No assumption of fifty reviews per page is used.

## Data isolation and operating stops

Prepare a fresh isolated experiment database with the existing Alembic migration
and seven-table schema, original eight-app seed and identical least-privilege
roles. Only the Duolingo target can be enabled. The retained pilot database
remains outside the experiment's write scope. Experimental history starts empty;
no pilot references are copied in as new observations.

Keep probe and main-study evidence separate. Prefer a separate disposable probe
database; its seven non-contiguous page requests do not constitute a normal
contiguous controller run or main-study reference. A private probe manifest
can retain this evidence without forging a successful controller run.
The main database records seven contiguous fixed-depth runs using the existing
table relations. Comparison sidecars do not introduce core tables.

A single cross-process lock covers both probe and main execution; the
application database lock alone cannot coordinate different databases.
Before each request enforce scope, validity, quotas and revocation. On denial
or rate limit, stop the study. On malformed/unsupported content or
infrastructure failure, stop the observation and place subsequent slots on
hold pending review. Mark them blocked if the condition is unresolved; do not
retry the affected observation, switch to unapproved formats or continue deeper.
Selected empty or duplicate-only pages stop the depth acquisition with a
source-window limitation. Future strategy changes never occur automatically.

Retain committed-page evidence on failure, prohibit reconnect/replay under lost
session ownership, use the private diagnostic spool, and verify integrity and
target/policy disablement after each observation. At W6 or terminal cancellation,
retire only the experiment's tasks. The original pilot remains retired.

## Evaluation criteria and readiness

A strategy has a preliminary continuity pass only if every eligible transition
in its primary trajectory meets both thresholds: three of three at 24 hours or
six of six at 12 hours. A missing or indeterminate pair prevents that pass, and
all planned pairs remain in the denominator. Report evaluable-pair success and
all-planned-pair success separately. Compare the three common-current endpoints
before preferring frequency over depth; report offset-pair sensitivity.

Three or six correlated transitions over 72 hours support a bounded study result,
not a long-term guarantee. If strategies tie on primary continuity and have
similar common-endpoint findings, prefer lower observed request cost, then
simpler scheduling. Failed minimum observation counts produce an inconclusive
study without automatic extension. No universal eight-app setting is inferred.

Before execution, complete these minimal steps:

1. Review the bounded probe (14 requests maximum) and main-study envelopes
   (140 requests maximum if depth 10 is supported). Confirm absolute T0–W6
   timestamps and feasibility branch before activation.
2. Implement the isolated technical entry and shared per-observation accounting
   described above, with a default-disabled manifest and immutable software and
   configuration hashes. Keep production policy and Controller.run_target unchanged.
3. Implement the offline depth/lag comparer using coverage_metrics and private
   committed-page projections; verify formulas and the separate early-stop replay.
4. Test synthetic ten-page novelty, repeated/capped pages, fallback budget
   exhaustion, nested/duplicate Atom rejection, partial persistence, independent prefix validity after a tail failure, no
   transaction during HTTP, disconnect/spool behavior, revocation, duplicate
   invocation, missed slots, 12/24-hour references and no pilot DB writes.
   Use disposable PostgreSQL; run related tests and the full suite if shared
   code changes. Stop for review if safe lifecycle reuse requires redesign.
5. Verify actual experiment DB identity/roles, directory permissions and
   zero-network startup. Keep original pilot targets/tasks disabled.
6. After separate execution authorization, run exactly the probe once. Review
   the actual result and bind depth 10, a smaller justified K, or the five-page
   alternative. No ten-page main schedule is enabled in advance.
7. After the chosen schedule is approved, invoke the existing local scheduling
   mechanism for the seven explicit slots. Generate the comparison report,
   verify retained evidence and retire the experiment.

### Implemented operator interface

The isolated entry is `feasibility.apple_ingestion.coverage_experiment`. The
private manifest binds Duolingo, seven explicit slots, the isolated database,
source digest, a 20-request observation cap and a 140-request study cap.
Production Controller, live policy and migrations are unchanged.

```sh
PYTHONNOUSERSITE=1 python \
  -m feasibility.apple_ingestion.coverage_experiment \
  --state ~/.local/state/data-source-feasibility/coverage-main-20261113 verify
```

`verify` checks the real database, roles, disabled targets, diagnostic path,
integrity and clocks without constructing an HTTP session. `observe` acquires
one currently due slot; it refuses disabled, early, expired, duplicate or
uncertain execution. `maintenance` records missed slots without backfill,
disables the isolated target and consolidates/retires the study after the last
slot. These commands do not install a scheduler or create approval records.

The prepared Windows wrapper starts the existing private PostgreSQL cluster
when needed, invokes the entry through WSL, and disables only the experiment's
two tasks after retirement. No scheduler or live execution is activated by
preparation. See [experiment readiness](APPLE_COVERAGE_EXPERIMENT_READINESS.md)
for exact timestamps, validation results, clock evidence and activation limits.

The independent probe remains complete; no second probe is required. A
contiguous 1–10-page window must still be observed at T0. The
[adaptive strategy note](APPLE_ADAPTIVE_COLLECTION_STRATEGY.md) remains
hypothesis-only; no adaptive frequency or depth adjustment is implemented.

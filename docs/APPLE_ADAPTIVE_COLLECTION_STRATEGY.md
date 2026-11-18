# Bounded adaptive collection: design hypotheses

## Purpose and evidence boundary

This note defines candidate per-application controls for later evaluation.
The [coverage experiment](APPLE_HIGH_VOLUME_COVERAGE_EXPERIMENT.md) first
compares fixed 24/12-hour intervals and five/ten-page depths for Duolingo.
No automatic adaptation, scheduler change or production policy change is
implemented here.

The completed pilot establishes that clean insufficient-overlap runs can remain
comparison references. Duolingo had four such successful windows and one parsing
failure. Microsoft To Do usually stopped at two pages with 98–99% overlap.
These results motivate per-app settings; they do not identify the appropriate
new Duolingo interval. The subsequent [single probe](APPLE_PAGINATION_FEASIBILITY_PROBE.md)
returned usable, distinct reviews on all tested deep pages 6–10; repeated
contiguous ten-page windows remain untested.

## What already adapts and what remains fixed

The controller already varies actual request consumption within a run. After
each committed page it checks at least two pages, twenty shared IDs and 20%
overlap. When all predicates hold without conflicts/cautions, it stops early.
Otherwise it continues within the fixed depth, request and time limits.
JSON with no review entries can trigger one same-page Atom fallback. This
changes format use, not collection frequency.

Reference selection chooses eligible committed history independently of the
previous coverage verdict. It excludes failed, partial, interrupted, malformed,
conflicting or otherwise inconsistent runs. A reference older than 72 hours
produces a continuity warning instead of an automatic exclusion.

Maximum depth and target interval are not currently adjusted from observations.
Although the schema and IngestionConfig can represent per-target values, the
current live ProjectExecutionConfig fixes the interval to 24 hours and caps
depth and requests at five and ten. It applies one settings object to its app
scope. Production scheduling also uses explicit fixed times.
Per-app adaptive execution is therefore not available by setting a few fields.
A later design would need reviewed live-profile, snapshot and scheduling support.

## Candidate parameter space

If the fixed experiment supports them, evaluate discrete per-app states
(24 h, 5 pages), (24 h, 10 pages), (12 h, 5 pages) and (12 h, 10 pages).
Replace ten with an actually verified K if deeper pagination is limited.
Do not introduce arbitrary intermediate settings until supported by evidence.

A five-page state has a ten-physical-request cap and a ten-page state would
need a separately approved twenty-request cap for worst-case fallback.
Depth is a ceiling, while unchanged production early stopping determines
actual consumption. Twelve-hour scheduling does not imply a second process.
Every state is constrained by an explicit app-level and global time-budget
ledger, independent of unused allowances on another app.

Low-volume apps retain their current settings unless their own evidence
supports a change. The pilot's successful two-page Microsoft To Do windows
provide no rationale for a universal increase.

## Signals

| Signal | Meaning and guardrail |
| --- | --- |
| Shared count and ratio | Same approved formula: intersection divided by current distinct IDs; never equate overlap with completeness |
| Consecutive insufficient clean windows | Evidence of bounded continuity difficulty only when both comparisons are usable and actual intervals are comparable |
| Minimum observed threshold depth | Diagnostic prefix evidence or production early-stop depth; absence beyond an early stop is unknown |
| Window turnover | IDs absent from the previous comparison window, not verified new publications or measured missing reviews |
| Requests per useful comparison | Include fallback, all failures and scheduling startup costs; a low cost from early failure is not efficiency |
| Repeated/empty deeper pages | Evidence against additional useful depth at that time; no endpoint or access workaround |
| Failures and indeterminate windows | Reliability/health evidence; do not classify as ordinary ID churn |
| Actual time since eligible reference | Classifies gaps and warns beyond 72 hours; long-gap insufficiency cannot alone trigger normal-cadence escalation |
| Stable sufficient overlap | Supports staying in a state; it cannot reveal whether a cheaper unobserved state would also work |

Rate limits, denial, parser rejection, recovery uncertainty, source conflicts
or unavailable persistence stop collection under existing safeguards.
They do not trigger faster scheduling or additional HTTP requests.

## Candidate transitions to test later

These numerical rules are hypotheses, not validated production parameters.

1. Keep the current state after clean sufficient windows. Collect no extra
   pages solely to establish more confidence during ordinary production.
2. Consider escalation only after two consecutive clean insufficient comparisons
   at the intended cadence. An invalid required prefix or missed slot resets the consecutive
   counter. Overall acquisition failures are tracked separately; a valid
   five-page prefix is not discarded solely for an error after page five. Gaps enter a separate recovery state and hold adaptation.
3. If paired study observations show depth 10 fixes the same 24-hour endpoints
   at acceptable cost, test a five-to-ten-page ceiling change. If depth is
   unavailable or does not improve those endpoints, test a 24-to-12-hour change
   only when the fixed twelve-hour evidence supports it.
4. If only the combined state meets the preliminary experiment criteria, treat
   it as the highest-cost candidate requiring explicit app/global capacity,
   rather than assuming it is an acceptable default.
5. Change one parameter at a time. Use a cooldown of at least 48 actual hours
   and three usable comparisons after a change before another normal transition.
   A safety stop always overrides cooldown.
6. Consider de-escalation only after at least four clean sufficient comparisons
   and paired observations showing the cheaper state would also pass at a
   comparable interval. For depth reduction, observed threshold depth at most
   four pages can provide a one-page margin; the actual five-page ratio must
   still meet 20%. Interval expansion requires real 24-hour pairs, not an
   extrapolation from twelve-hour success.
7. If lower-cost evidence is unavailable because early stopping censored depth
   or production has no longer-lag observations, retain the current state
   rather than adding unbudgeted validation requests.
8. Apply any future transition to the next immutable run snapshot. Never change
   limits mid-run, rewrite evidence, lower the twenty-ID/20% predicates or
   treat a failed run as a valid reference.

Two escalation windows versus four stable de-escalation windows create
hysteresis. Cooldown and repeated-evidence counters need later validation;
the seven-window fixed study cannot fully validate a closed-loop system or
all proposed de-escalation/cooldown cycles.

## Choosing depth, interval or both

Use paired current endpoints from the fixed experiment. Depth comparisons
have identical observation times and can share acquisition. Frequency
comparisons use actual twelve-hour versus twenty-four-hour intervals with
different references. The primary daily comparison has three transitions;
its offset pairs are supplementary and dependent.

Depth 10 and interval 12 h at depth 5 both have a JSON-only steady-state cost
of ten requests/day before early stopping, versus five for the baseline.
Their worst-case daily caps are twenty versus ten for baseline.
The combined state doubles those escalated costs to twenty JSON requests/day
and a forty-request maximum. The complete shared experiment costs at most
154 physical requests including its separate probe, not the sum of four
standalone experiments.

Compare planned-pair continuity, evaluability and failures before cost.
If continuity is comparable, prefer lower observed request cost and then the
simpler daily schedule. Report any worse overlap ratio at greater depth;
a larger denominator can reduce the ratio even when the shared count increases.

No result is predetermined. A five-page twelve-hour alternative may be the
only defensible test if deep pagination fails. If parsing failures dominate,
additional depth/frequency does not resolve that reliability limitation and
the study may remain inconclusive.

## Reuse and implementation boundary

The fixed study should reuse BoundedTransport, strict parse_feed, canonical
normalization/fingerprints, application locks, persist_page, safe diagnostics,
coverage_metrics and existing schema/report contracts. It should use an isolated
experiment database and an explicitly bounded diagnostic entry, keeping the
production factory and early-stop controller unchanged.

Future automatic adaptation would require separately tested per-app execution
profiles, deterministic state transitions, a budget ledger, revocation,
non-overlapping scheduling, missed-slot handling and safe restart behavior.
A small file-backed state alongside existing immutable snapshots may suffice;
no new core table, LLM decision-maker, service or approval framework is implied.
This task creates none of that state and performs no transitions.

## Evidence needed before an adaptive policy decision

The seven real-time observations should establish usable source depth, incremental
deep-page IDs, paired prefix overlap, actual request costs, parse reliability and
source-time/order cautions. At least three valid primary daily transitions and
six twelve-hour transitions are needed to describe the complete proposed
trajectory. Missing comparisons prevent a preliminary full-trajectory pass.

A fixed strategy can inform a bounded next design only when its usable windows
show an advantage at matched endpoints, its cost fits declared budgets and its
failures are not being counted as evidence of review churn. Original pilot
history supplies context, not extra experimental replicates.

The probe establishes sampled deep-page availability at one time.
Source ordering stability, contiguous ten-page observations over time and the
appropriate Duolingo settings remain unknown pending the targeted study. A successful
fixed strategy would justify proposing a constrained adaptive policy; it would
not by itself validate automatic adjustment or complete source coverage.

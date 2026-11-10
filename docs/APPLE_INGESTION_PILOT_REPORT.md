# Apple ingestion pilot report

## Objective

The pilot evaluated whether Apple App Store review feeds could support bounded, repeatable
collection of consumer-experience text across the project's eight applications,
with full-text history, traceable observations and measurable content usefulness.
Building on the initial source-feasibility comparison, the pilot examined
collection reliability and data quality through an actual seven-day pilot.

## Methodology

The pilot ran November 3–9, 2026, with one sequential eight-application batch
planned for 09:00 America/Los_Angeles (17:00 UTC) each day, using the US storefront
and mostrecent ordering. The same four-category frame contains two apps each
for productivity, education, shopping and transportation.

Each target/run used 2–5 logical pages, at most ten HTTP requests, zero automatic
retries, global request spacing of at least two seconds and existing bounded
timeouts. Reference selection and observed-ID overlap measured continuity
between available collection windows. Earlier Smoke evidence remained separate
from formal pilot totals.

After collection, deterministic sampling selected ten reviews per app from the
accumulated LIVE corpus, giving 80 reviews. Full-text manual assessment
used the U0–U3 rubric with ratings hidden. U2/U3 count as useful;
sentiment was not assessed.

## Implementation

The implementation uses strict JSON parsing with controlled Atom fallback,
normalization, reconciliation and a bounded collection controller. Seven
PostgreSQL tables store complete title/body versions, observations, runs and
fetch attempts. Page-level transactions preserve already committed pages when
later parsing fails, while failed pages are rejected as a whole.

Windows Task Scheduler invoked the existing WSL Python environment and
persistent PostgreSQL database. Private diagnostics, scoped execution policies,
restricted database roles, backup generation and retirement controls supported
unattended operation. The system recorded immutable configuration snapshots and
per-run evidence. The [system design](APPLE_INGESTION_SYSTEM_DESIGN.md) and
[implementation summary](APPLE_INGESTION_IMPLEMENTATION_SUMMARY.md) document
the architecture and engineering history.

## Results

### Engineering reliability

| Measure | Observed result |
| --- | ---: |
| Actual daily batches | 7 / 7 |
| Recorded application runs | 56 / 56 |
| Successful / partial / failed runs | 52 / 1 / 3 |
| HTTP requests / committed pages | 155 / 147 |
| Review observations | 7,350 |
| First-in-database reviews | 4,257 |
| Changed versions observed | 0 |
| Full stored versions checked, including Smoke | 4,507 |
| Fingerprint mismatches | 0 |

All scheduled dates have evidence. Five apps succeeded in all seven runs.
Todoist had one partial run, Duolingo one failure and Etsy two failures.
All 14 daily backups were checked. The final backup was fully restored and
verified in an isolated private database. Collection targets, project execution
and both Windows tasks were disabled after the final batch.

### Human content quality

All 80 manual assessments were completed. **47/80 (58.75%)** were useful under the
rubric, with 21 U3, 26 U2, 28 U1 and five U0 labels.

| Category | Useful / assessed | Rate |
| --- | ---: | ---: |
| Productivity | 16 / 20 | 80% |
| Education | 11 / 20 | 55% |
| Shopping | 12 / 20 | 60% |
| Transportation | 8 / 20 | 40% |

These sample results show concrete experience information across all four
categories, alongside variation in information value by app and category.
The [review quality assessment](APPLE_REVIEW_QUALITY_ASSESSMENT.md) contains
per-app results, rubric, sampling, schema adaptation and provenance.

## Limitations

Duolingo reached the five-page limit with insufficient overlap on four dates.
The comparison chain continued correctly, but daily bounded collection did not
demonstrate sufficient window continuity for that app. Observed overlap cannot
prove complete coverage, and first-in-database counts do not establish source
publication times. Zero observed edits leaves real edit detection unresolved.

Day 6 Atom fallbacks had duplicate content elements in the first entry.
Strict rejection retained earlier committed pages. Day 2 Etsy's exact field
failure remains unknown because that response was not retained. The detailed
[technical validation](APPLE_INGESTION_TECHNICAL_VALIDATION.md) separates confirmed
diagnostics from unresolved source behavior. Local backup/restore verification
does not establish off-host or whole-machine recovery.

The sample allocated ten reviews to each app, without review-volume weighting.
Each application contributes equally to the reported quality results.

In the initial feasibility study, AI-assisted inspection of first-page samples
classified 28/40 Apple reviews (70%) as useful, with some long reviews limited
to text prefixes. The pilot used full-text manual assessment of a different
80-review sample with the U0–U3 rubric. The results are reported separately
because the sampling and assessment methods differ.

## Conclusion

The seven-day pilot demonstrates the technical feasibility of bounded Apple
review ingestion across the selected eight applications. All 56 scheduled runs
have persisted evidence, and the 80-review manual assessment classified 47
reviews (58.75%) as useful.

The observed limitations are concentrated in Duolingo's window continuity,
intermittent Atom parsing failures and the single-reviewer quality sample.
Complete daily coverage, real source-edit behavior and off-host recovery remain
unverified. Applicable data-use and long-term-retention conditions remain
unresolved, as documented in the
[access and retention memo](archive/PHASE_E_ACCESS_RETENTION.md).

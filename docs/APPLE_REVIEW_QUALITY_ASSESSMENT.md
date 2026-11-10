# Apple review quality assessment

## Objective and sample

The assessment examined the usefulness of retained Apple reviews for
consumer-experience analysis. The sample contains 80 reviews from the actual LIVE corpus accumulated through the seven-day pilot,
including retained Smoke-supported records. Eight purposively chosen apps cover
productivity, education, shopping and transportation, with ten reviews per app.
The deterministic sample was drawn at 2026-11-09T17:00:43.340698Z from 4,507
eligible reviews. The four categories each contribute 20 selected reviews.

## Methodology and rubric

Each review was assessed manually from its complete title and body using the
U0–U3 rubric. Ratings were hidden during reading to keep usefulness judgements
focused on the review text.

| Label | Meaning |
| --- | --- |
| U3 | Detailed concrete experience with context, action and consequence |
| U2 | Concrete but limited feedback |
| U1 | Generic reaction with little detail |
| U0 | Unusable or unclear content for experience assessment |

Usefulness is the proportion labelled U2 or U3 among assessed unique reviews.
It is independent of sentiment. The existing summarize_assessment pipeline
validated the compatible response copy and computed the results below.

## Results and interpretation

All 80 reviews were assessed. **47/80 (58.75%)** were useful, consisting of
21 U3 and 26 U2 labels. The other labels were 28 U1 and five U0. There were
zero unassessed records and no sampling shortfall. Productivity had the highest
sample rate at 80%, followed by shopping at 60%, education at 55% and
transportation at 40%. Per-app results appear below.

These rates describe ten records per app, equally allocated across the app frame.
One changed judgement would shift an app's rate by ten percentage points.
The aggregate is not weighted by the corpus's review volumes. No population
generalization, classifier accuracy or platform-wide ranking is established.
The material supports useful examples in all four categories while showing
substantial low-information content. Sentiment and topic classification were outside the assessment scope.

## Validation and provenance

All 80 assessment records passed validation against the sample manifest,
response schema and PostgreSQL review-version bindings. Original labels,
reasons, languages and reviewer identifiers remain intact.

- Manifest ID: `cd52800c5ea5a8d38c109203269864bbd74d0162c735a762bf932c95fbb54d59`.
- Original completed JSON SHA-256: `85e605f373ed53b752e52a0311763f7c14097d90aedef830c9c06f0c82c7a63e`.
- References: 80 unique reviews with matching version bindings.
- Labels: U3=21, U2=26, U1=28 and U0=5.
- Completeness: 80 reasons and full-text reading records, with reviewer R1.
- Languages: English=77, Spanish=2 and Russian=1.
- Pipeline result: 47 useful / 80 assessed = 58.75%, with zero unassessed.

The compatible response file and validation audit are stored in the private
`day7/human-assessment.validated/` directory, with mode 0700 for the directory
and 0600 for its files. The original completed records are retained.
The [assessment summary](archive/APPLE_PHASE_F_HUMAN_ASSESSMENT_SUMMARY.json)
contains the aggregate results and detailed audit metadata.

## Category and application results

| Category | Assessed | U3 | U2 | U1 | U0 | Useful (U2/U3) | Rate |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Education | 20 | 4 | 7 | 9 | 0 | 11 | 55.00% |
| Productivity | 20 | 9 | 7 | 3 | 1 | 16 | 80.00% |
| Shopping | 20 | 5 | 7 | 6 | 2 | 12 | 60.00% |
| Transportation | 20 | 3 | 5 | 10 | 2 | 8 | 40.00% |

| Application | Assessed | U3 | U2 | U1 | U0 | Useful (U2/U3) | Rate |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Todoist | 10 | 6 | 2 | 2 | 0 | 8 | 80.00% |
| Microsoft To Do | 10 | 3 | 5 | 1 | 1 | 8 | 80.00% |
| Duolingo | 10 | 2 | 4 | 4 | 0 | 6 | 60.00% |
| Khan Academy | 10 | 2 | 3 | 5 | 0 | 5 | 50.00% |
| Amazon Shopping | 10 | 2 | 5 | 2 | 1 | 7 | 70.00% |
| Etsy | 10 | 3 | 2 | 4 | 1 | 5 | 50.00% |
| Uber | 10 | 0 | 3 | 5 | 2 | 3 | 30.00% |
| Lyft | 10 | 3 | 2 | 5 | 0 | 5 | 50.00% |

## Limitations

Each application contributes ten reviews to the sample. The reported percentages
summarize these selected reviews and may differ from the proportions across
the full review population.

## Comparison with earlier feasibility evidence

In the initial Apple/Google comparison, 28/40 Apple reviews (70%) were classified
as useful. The sample used the first five page-1 reviews per app and AI-assisted
binary judgements; three Apple records were limited to 500-character prefixes.
The pilot used ten reviews per app from the accumulated corpus and full-text
manual U0–U3 assessment.

Both studies used the same eight-app/four-category frame and hid ratings.
Their results are reported separately because sample selection, reading limits
and assessment methods differ. The percentage difference does not establish
a quality trend, reviewer agreement or a controlled source comparison.
The initial 40-review RSS field sample had a separate length screen and no
semantic usefulness percentage.

Historical comparisons are preserved in
[the mobile feasibility comparison](../results/mobile_review_comparison.md) and
[the initial RSS assessment](../results/mainstream_review_assessment.md).


## Relationship to the pilot

The human results address content quality in the collected sample. The
[technical validation](APPLE_INGESTION_TECHNICAL_VALIDATION.md) separately
documents scheduling, parsing failures, coverage and storage checks. The
[pilot report](APPLE_INGESTION_PILOT_REPORT.md) combines these findings in the overall study results. Project-level access, intended use and long-term retention
questions remain documented in the
[access and retention memo](archive/PHASE_E_ACCESS_RETENTION.md).

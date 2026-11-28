# Apple Review ABSA Exploratory Findings

## Study scope

This study prepares an annotation framework for review-level multi-aspect
analysis across eight applications. It uses retained pilot records through
the approved retrieval and ABSA preparation interfaces. The source database
is `apple_ingestion`; the separate Duolingo coverage database is excluded.
The private sample was created on November 27, 2026.

Codex performed qualitative exploration of the rating-blind text. These
observations supplied the framework review. The focused clarifications are
now frozen as `apple-absa-guidelines/v1` and `apple-absa-annotation/v1`.
Human ABSA annotations, training labels and inter-reviewer agreement remain
pending. The previous U0-U3 assessments were neither changed nor reused.

## Sampling

The current-review pool contains 4,507 records.

| Application | Pool | Selected | Initial exploration |
| --- | --- | --- | --- |
| Todoist | 253 | 10 | 3 |
| Microsoft To Do | 258 | 10 | 3 |
| Duolingo | 1,296 | 10 | 3 |
| Khan Academy | 265 | 10 | 3 |
| Amazon Shopping | 555 | 10 | 2 |
| Etsy | 400 | 10 | 2 |
| Uber | 852 | 10 | 2 |
| Lyft | 628 | 10 | 2 |

A single read-only REPEATABLE READ transaction selected current versions
using `iter_current_reviews`, with explicit database and report-role checks.
The returned records were converted to the approved decoded CSV
representation and passed through `process_reviews`.

Seed `apple-absa-exploration-20261127-v1` is fixed. Within each application,
sort ascending by SHA-256 of UTF-8 compact JSON
`[seed, source, source_application_id, source_review_id]`, using
`ensure_ascii=False` and separators `(",", ":")`. Select the first ten.
The first two per app and the third from the first four applications in
the existing app manifest form the initial twenty. No rating, text,
language, usefulness or aspect criteria influence selection.

The private manifest retains exact source/review/version keys, pool sizes,
seed, stage membership, extraction time and a checksum of the frozen sample.
Its sample SHA-256 is
`ea8a26e27cfe2ee2bce8d331e1c61719784c45f5fa05d91cab1a25c13f8b86e0`.
Reproduction uses the frozen input because database current pointers can
change over time. The remaining sixty received a boundary and language
inspection after the initial twenty; formal annotation has not started.

Equal app allocation supports cross-category exploration. This small,
stratified sample cannot establish population prevalence or guarantee every
experience type. The original app frame was purposive.

## Emerging distinctions

The initial twenty contain task creation and organization, missing
cross-platform capabilities, mobile navigation difficulties, slow input,
inconsistent task completion, learning outcomes and difficulty, missing
items, product defects, unanswered support requests, prices and driver
professionalism. Generic reactions and questions with insufficient context
also occur. These observations support the taxonomy in the
[annotation guidelines](APPLE_ABSA_ANNOTATION_GUIDELINES.md).

The remaining sixty expose further boundaries involving crashes and startup,
synchronization, subscriptions, advertisements, search, privacy concerns,
marketplace authenticity, refunds, vehicle comfort and service punctuality.
Privacy receives its own aspect. Product and learning content quality share
a broad quality dimension with a required target domain.

All examples below are invented.

| Case | Representation |
| --- | --- |
| "The filters are convenient, but the app closes when I save." | Usability positive; reliability negative |
| "The fabric is durable, but the parcel arrived incomplete." | Quality positive for product; fulfillment negative |
| "Support solved one refund and ignored another." | Support mixed when both evaluations concern the same support target |
| "Great!" | No identifiable aspect |
| "The driver was courteous." | Personnel service positive, despite short length |
| "It is too hard." | Insufficient context unless title or surrounding text identifies the target |

Title and body must be read together. Multiple aspect sentiments are recorded
independently. An overall positive introduction supplies no positive
evidence for every specific aspect. Separate positive and negative targets
remain separate even when they share a taxonomy category.

## Language scope

Semantic inspection of the eighty texts suggests 77 predominantly English,
two Russian and one Spanish. The initial twenty include nineteen English
texts and one Spanish text. These are model-assisted exploratory counts;
a competent human must verify each language before a final annotation.
These counts provide no verified language ground truth and cannot establish
that seventy-seven reviews qualify for English annotation.
The preparation output still retains `language_status=unknown`.

English-first is proposed for the first human annotation round. Preserve
all eighty records. Only human-confirmed English enters initial formal
ABSA annotation. A human-confirmed non-English review outside the assigned
reviewer's competence receives `language_out_of_scope`. A non-English
review within that competence remains pending a multilingual-scope decision.
Mixed or unresolved language stays pending with null final language and
annotation status. A future language
detector requires an independently checked multilingual set and reporting
of errors and abstentions. No detector or translation service was added.

## Privacy and limitations

The sample, exact raw text, version keys and rating-blind view reside in
private local storage. Public documentation contains synthetic examples and
aggregate observations. Source text can contain personal information even
when author fields are absent. Keep annotation evidence private as well.

Applicable data-use and retention arrangements remain unresolved in the
[existing access record](archive/PHASE_E_ACCESS_RETENTION.md). This task
stays within bounded local exploration and framework design. Expanded
training, redistribution and retention decisions require project review.

Human annotation accuracy, aspect frequencies and agreement statistics
remain unmeasured. The frozen guidelines govern re-reading the first twenty,
annotating the remaining sixty and revisiting the first twenty. Questions
that require changed label meanings must be resolved through versioning.

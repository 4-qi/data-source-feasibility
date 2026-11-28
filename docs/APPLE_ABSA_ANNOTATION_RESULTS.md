# Apple Review ABSA Annotation Results

## Scope and evidence

The first annotation round contains 80 submitted review records, 61 with
aspect annotations and 88 aspect entries. The dataset follows
`apple-absa-guidelines/v1` and `apple-absa-annotation/v1`.
The source is the frozen eight-application pilot sample from
`apple_ingestion`. Ten current reviews were sampled per application,
covering four analytical categories. The separate Duolingo coverage
experiment is outside this analysis.

The input export SHA-256 is
`f289e076e4470ea97536502993d40cdc3900af94ca365f2e8aed424144198bda`.
The frozen sample SHA-256 is
`ea8a26e27cfe2ee2bce8d331e1c61719784c45f5fa05d91cab1a25c13f8b86e0`.
The completed export matches the saved progress records exactly.
[Sampling methodology](APPLE_ABSA_EXPLORATORY_FINDINGS.md)

Every record passed the frozen JSON Schema with date-time format checking,
parent identity and version checks against the sample manifest, completed
workflow rules, language and evidence confirmations, and exact original
Unicode code-point evidence checks. All 80 source review identities are
unique. All 90 evidence spans match their original stored field slices.
The export records one reviewer identity and a completion timestamp for
each review. These checks establish structural and provenance consistency.
[Frozen annotation contract](APPLE_ABSA_ANNOTATION_SCHEMA.md)

This analysis reads the source files locally. The sample, manifest,
rating-blind view, progress file and completed export retain their input
checksums. Review text, evidence, individual labels and version-linked audit
notes remain in private local storage. The report contains aggregates and
synthetic examples. Statistical analysis uses stored human labels unchanged.

## Counting units

Review-level percentages use 80 sampled reviews unless another denominator
is stated. Sentiment percentages use 88 aspect entries. Entries within one
review share context, and repeated targets can use the same category.
The 88 entries belong to 61 reviews and form 82 distinct review-category
pairs. Entry frequencies and review frequencies are reported separately.

Equal allocation across applications does not balance sentiment or reflect
each application's review volume. The purposive app frame, bounded retained
collection windows and small sample support descriptive comparisons within
this dataset. Population prevalence, independent-sample significance and
model accuracy remain unmeasured.

## Review status and language

| Review status | Reviews | Share of 80 |
| --- | --- | --- |
| annotated | 61 | 76.25% |
| no_identifiable_aspect | 12 | 15.00% |
| insufficient_context | 4 | 5.00% |
| language_out_of_scope | 3 | 3.75% |
| ambiguous | 0 | 0.00% |
| Pending | 0 | 0.00% |

| Recorded human language | Reviews | Aspect-bearing reviews | Aspect entries |
| --- | --- | --- | --- |
| English | 77 | 61 | 88 |
| Russian | 2 | 0 | 0 |
| Spanish | 1 | 0 | 0 |

The English review set contains 77 records, including 16 zero-aspect
decisions. The aspect-bearing English subset contains 61 reviews
(79.22% of 77). The three non-English records remain traceable members of
the sample with an out-of-scope reason and zero aspects. The preparation
field `language_status=unknown` remains intact alongside the annotation's
human-entered language field.

The twelve no-aspect decisions primarily concern broad approval,
disapproval or thanks without a sufficiently specific evaluated target.
The four insufficient-context decisions concern unresolved references,
questions, an occasion label or an unspecified complaint. Borderline cases
receive further scrutiny in the quality audit below.

## Aspect and sentiment distribution

| Aspect | Entries | Reviews containing aspect | Positive | Negative | Neutral | Mixed | Unclear |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| functionality | 16 | 12 | 7 | 4 | 5 | 0 | 0 |
| usability | 11 | 10 | 4 | 7 | 0 | 0 | 0 |
| reliability | 8 | 8 | 0 | 8 | 0 | 0 | 0 |
| performance | 3 | 3 | 0 | 3 | 0 | 0 | 0 |
| pricing | 7 | 7 | 3 | 4 | 0 | 0 | 0 |
| customer_support | 2 | 2 | 1 | 1 | 0 | 0 | 0 |
| quality | 18 | 18 | 12 | 5 | 0 | 1 | 0 |
| fulfillment | 11 | 10 | 3 | 8 | 0 | 0 | 0 |
| personnel_service | 11 | 11 | 11 | 0 | 0 | 0 | 0 |
| privacy | 1 | 1 | 0 | 1 | 0 | 0 | 0 |
| other | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| unclear | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| Total | 88 | 82 review-category pairs | 41 | 41 | 5 | 1 | 0 |

| Aspect sentiment | Entries | Share of 88 |
| --- | --- | --- |
| positive | 41 | 46.59% |
| negative | 41 | 46.59% |
| neutral | 5 | 5.68% |
| mixed | 1 | 1.14% |
| unclear | 0 | 0.00% |

Quality has the most entries (18/88, 20.45%), followed by functionality
(16/88, 18.18%). Quality also has the most positive entries (12), followed
by personnel service (11). Reliability and fulfillment each have eight
negative entries; usability follows with seven.

All five neutral entries are functionality annotations, including requested
capabilities or changes without an explicit negative judgment. The sole
mixed entry is quality. Its broad target and evidence receive a dedicated
audit question below. The zero counts for other and unclear indicate how
this reviewer used the taxonomy on this sample. Taxonomy completeness and
the absence of ambiguity cannot be inferred from those zeros.

The equality of 41 positive and 41 negative entries is descriptive. App
sampling quotas supplied no sentiment balance requirement. Multiple entries
can originate from one review, and the retained windows have selective
coverage.

## Distribution by application

Each application contributes ten reviews.

| Application | Aspect-bearing reviews | Aspect entries | Multi-entry reviews |
| --- | --- | --- | --- |
| Todoist | 8 | 13 | 4 |
| Microsoft To Do | 8 | 10 | 2 |
| Duolingo | 6 | 6 | 0 |
| Khan Academy | 5 | 8 | 3 |
| Amazon Shopping | 10 | 16 | 5 |
| Etsy | 8 | 11 | 3 |
| Uber | 7 | 9 | 2 |
| Lyft | 9 | 15 | 4 |
| Total | 61 | 88 | 23 |

The following cells count entries.

| Aspect | Todoist | Microsoft To Do | Duolingo | Khan Academy | Amazon Shopping | Etsy | Uber | Lyft |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| functionality | 6 | 3 | 0 | 3 | 2 | 0 | 1 | 1 |
| usability | 5 | 1 | 0 | 0 | 4 | 1 | 0 | 0 |
| reliability | 1 | 4 | 0 | 1 | 2 | 0 | 0 | 0 |
| performance | 0 | 2 | 0 | 0 | 1 | 0 | 0 | 0 |
| pricing | 1 | 0 | 0 | 0 | 0 | 1 | 1 | 4 |
| customer_support | 0 | 0 | 0 | 0 | 1 | 1 | 0 | 0 |
| quality | 0 | 0 | 6 | 4 | 1 | 4 | 1 | 2 |
| fulfillment | 0 | 0 | 0 | 0 | 4 | 2 | 1 | 4 |
| personnel_service | 0 | 0 | 0 | 0 | 0 | 2 | 5 | 4 |
| privacy | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 0 |
| other | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| unclear | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| Total | 13 | 10 | 6 | 8 | 16 | 11 | 9 | 15 |

## Distribution by category

Each category contributes twenty reviews.

| Category | Aspect-bearing reviews | Entries | Multi-entry reviews |
| --- | --- | --- | --- |
| Productivity | 16 | 23 | 6 |
| Education | 11 | 14 | 3 |
| Shopping | 18 | 27 | 8 |
| Transportation | 16 | 24 | 6 |

The following cells count entries.

| Aspect | Productivity | Education | Shopping | Transportation |
| --- | --- | --- | --- | --- |
| functionality | 9 | 3 | 2 | 2 |
| usability | 6 | 0 | 5 | 0 |
| reliability | 5 | 1 | 2 | 0 |
| performance | 2 | 0 | 1 | 0 |
| pricing | 1 | 0 | 1 | 5 |
| customer_support | 0 | 0 | 2 | 0 |
| quality | 0 | 10 | 5 | 3 |
| fulfillment | 0 | 0 | 6 | 5 |
| personnel_service | 0 | 0 | 2 | 9 |
| privacy | 0 | 0 | 1 | 0 |
| other | 0 | 0 | 0 | 0 |
| unclear | 0 | 0 | 0 | 0 |
| Total | 23 | 14 | 27 | 24 |

Productivity feedback emphasizes capabilities and interaction design.
Education is dominated by learning quality in the retained annotations.
Shopping spans interface behavior, product quality, fulfillment and support.
Transportation emphasizes personnel, fulfillment and prices. The transport
quality entries also expose a taxonomy-boundary question in the audit.
These comparisons reflect ten reviews per app and the current labels.

## Multi-aspect structure

| Entries per review | Reviews |
| --- | --- |
| 0 | 19 |
| 1 | 38 |
| 2 | 20 |
| 3 | 2 |
| 4 | 1 |

There are 23 multi-entry reviews (28.75% of 80; 37.70% of the 61
aspect-bearing reviews). Eighteen reviews contain more than one distinct
aspect category. The difference arises because the representation also
allows multiple targets within the same category.

Three reviews contain both positive and negative entries for separate
targets. One additional review contains the single mixed quality entry.
Different dated service experiences remain separate targets in a
multi-entry record. The mixed entry aggregates evaluations under a common
marketplace-quality target, whose breadth needs adjudication.

## Targeted evidence-quality audit

Codex read the full title, body and annotation context for all eighty
records. A deterministic targeted set contains 72 distinct reviews selected
by the union of negative or mixed entries, title-only evidence, non-app
target domains, zero-aspect decisions and overlapping evidence spans.
The broader context read also covers positive and neutral comparison cases.
This is model-assisted desk review against the frozen guidelines. It
provides questions for human adjudication and supplies no independent human
agreement statistic or new annotation labels.

The 90 spans comprise 85 body spans and five title spans. Five entries use
title-only evidence. Their full review contexts identify either a software
operation, requested capability or service provider. Title-only evidence
can support a valid decision when it contains the necessary target and
evaluation. Every title-only slice passed exact offset checking.

The cross-entry span-overlap count is zero. Four entries in one review rely
on a shared evaluative clause
outside their disjoint selected fragments. Absence of overlap therefore
does not establish self-contained evidence.

The following audit questions are retained privately with exact parent
review/version references. Counts overlap across rows.

| Audit question | Coverage | Observation |
| --- | --- | --- |
| Evidence lacks the local evaluative or missing-feature clause | 8 entries in 5 reviews | Fragments name a target or activity, while polarity depends on surrounding text. Exact slice matching passes, but span-only use would lose the local basis for sentiment. |
| Vehicle condition and service environment boundary | 3 entries in 3 reviews | Transport-domain quality annotations use cleanliness or vehicle condition. The frozen definitions discuss learning/product quality and include service environment under personnel service. A consistent interpretation needs human adjudication. |
| Breadth of the mixed target | 1 entry in 1 review | Both polarity directions occur, but the target combines marketplace/product quality, imagery, size and price comparison. Confirm whether one shared target is justified. |
| Zero-aspect threshold | 4 zero-aspect reviews | Broad claimed benefits and catalogue praise require comparison with accepted broad outcome or product-quality annotations. Specificity thresholds remain a consistency question. |
| Rationale or target adds unresolved context | 3 entries in 3 reviews | The annotations introduce device-layout details, a software capability or a fee/arrival interpretation beyond what the source clearly establishes. |
| Software versus transaction attribution | 3 entries in 3 reviews | Delayed synchronization, return-initiation navigation and an app-reported booking-date change require consistent causal and domain boundaries. |
| Target exceeds the selected evidence | 1 entry in 1 review | The target covers multiple tools while the selected fragment supports only part of it. |
| Coverage of independently evaluated aspects | 1 review | Explicitly evaluated dimensions in the full text exceed the retained entries. Exhaustiveness requires human review. |

The union of these questions covers 19 reviews. The entry-specific
questions reference 18 distinct existing aspect entries; review-level
questions can overlap those reviews. These are targeted audit flags.
An annotation error rate, accuracy estimate or corrected label set cannot
be derived from them.

All examples below are synthetic and illustrate audit principles.

| Synthetic source | Audit principle |
| --- | --- |
| "The scanner is missing, so receipts take longer." | A span containing only the noun scanner omits the missing-capability and consequence context. |
| "Arrival was quick, the fare was fair, and the car was comfortable." | Separate target fragments can depend on distinct or shared evaluative predicates. Retain the needed wording with each entry. |
| "The parcel arrived incomplete, and the support desk never replied." | Order execution and response to assistance requests are independently evaluated dimensions. |
| "The cabin was spotless." | Apply a consistent vehicle-environment taxonomy boundary before interpreting the category count. |
| "Some listings were excellent, but others used misleading images." | A shared mixed target requires an explicit, defensible aggregation boundary. |

## Limitations and interpretation

The dataset has one recorded human reviewer. Independent second-reviewer
annotations, adjudicated gold labels and inter-reviewer agreement are absent.
Model-assisted audit observations cannot supply those measurements.
Evidence accuracy at the character level does not establish semantic
correctness, complete aspect coverage or consistent target granularity.

The initial annotation interface omits structured star ratings and previous
usefulness labels. This analysis uses the aspect sentiments as entered,
with no conversion from star ratings. The export alone cannot establish
every aspect of the reviewer's annotation process.

Eighty reviews provide a bounded first annotation round. The largest aspect
category has eighteen entries. Reliability, performance, personnel service
and privacy each contain a single observed polarity, and other/unclear have
zero entries.
Sparse cells provide limited evidence for comparisons. Correlated entries
within reviews and repeated application contexts require review-level
grouping in any later evaluation.

The aggregate results establish the observed distribution and exercise
multi-target representation and traceable abstention. The private audit
questions remain unresolved for human review. All original human labels,
the three out-of-scope records and the frozen versions are retained.

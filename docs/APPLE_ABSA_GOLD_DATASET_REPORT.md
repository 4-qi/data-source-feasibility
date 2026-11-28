# First-Round ABSA Gold Dataset Report

## Milestone and scope

The first-round reference dataset `apple-absa-gold/v1` is frozen with
80 reviews, 64 aspect-bearing reviews, 97 aspect entries and 100 source
evidence spans. Nineteen flagged reviews received focused adjudication.
The freeze occurred on November 27, 2026 at 17:33:53 PST
(`2026-11-28T01:33:53Z`).

| Contract | Frozen identifier |
| --- | --- |
| Dataset | `apple-absa-gold/v1` |
| Annotation guidelines | `apple-absa-guidelines/v1` |
| Annotation schema | `apple-absa-annotation/v1` |

The dataset provides a bounded reference for ABSA prototypes and exploratory
evaluation. It has one recorded human reviewer. Independent multi-reviewer
agreement and an independently validated gold-standard accuracy remain
unmeasured.

## Sampling and annotation

The original pilot database supplied 4,507 current reviews. Eight
applications contributed ten reviews each across productivity, education,
shopping and transportation. Selection used seed
`apple-absa-exploration-20261127-v1` and ascending SHA-256 of compact UTF-8
JSON `[seed, source, source_application_id, source_review_id]` within each
application. Selection used no rating, language, sentiment or usefulness
criteria. The frozen sample preserved each exact review/version reference.
[Exploratory methodology](APPLE_ABSA_EXPLORATORY_FINDINGS.md)

The framework supports multiple targets within a review, aspect-specific
sentiment, zero-aspect statuses and evidence in the original title or body.
The workflow organized twenty reviews for framework exploration and sixty
remaining records. The completed array applies the common frozen v1
definitions to the sample. The local interface omitted structured star
ratings and prior usefulness labels.
[Annotation guidelines](APPLE_ABSA_ANNOTATION_GUIDELINES.md)

Initial labels and subsequent adjudication are attributed to one reviewer.
Codex prepared model-assisted audit questions, source-evidence boundary
repairs and explicitly delegated coverage additions. The reviewer supplied
targeted decisions and interpretation principles through chat and confirmed
the reviewer identity for final submission. Assisted contributions and
their approval context remain recorded privately. Submission timestamps
represent actual tool submissions; they do not measure time spent reading.
[Local annotation workflow](APPLE_ABSA_ANNOTATION_TOOL.md)

## Focused adjudication

The first-round audit identified nineteen distinct existing reviews.
Questions concerned evidence context, vehicle/service environment,
mixed-target breadth, zero-aspect thresholds, unsupported interpretations,
software/transaction attribution and aspect coverage. Multiple questions
could concern one review.
[Historical first-round results](APPLE_ABSA_ANNOTATION_RESULTS.md)

All nineteen decisions are accounted for. Eighteen records contain an
adjustment and one was confirmed with its original values. Adjustments
include evidence or rationale changes as well as label changes, so these
counts do not estimate annotation error rates.

Adjudication checked evidence sufficiency, target specificity, aspect
boundaries, target-specific polarity and zero-aspect reasons against the
frozen rules. The reviewer could confirm a record, modify it under v1 or
pause for a proposed guideline change. All decisions were resolved under
v1. Individual decisions and their source-linked explanations remain
private.

The original eighty-record annotation export is retained as historical
evidence. The sixty-one unflagged records match their original values
field for field. Confirmed labels retain original annotation metadata.
Modified records carry the actual adjudicator and submission time. A
separate decision file links each reviewed result to its original parent
record hash and exact source/version reference.
[Adjudication and freeze procedure](APPLE_ABSA_ADJUDICATION.md)

## Final aggregate results

| Metric | First round | Frozen Gold v1 |
| --- | --- | --- |
| Reviews | 80 | 80 |
| Aspect-bearing reviews | 61 | 64 |
| Aspect entries | 88 | 97 |
| Evidence spans | 90 | 100 |
| Multi-entry reviews | 23 | 23 |

| Final review status | Reviews | Share of 80 |
| --- | --- | --- |
| annotated | 64 | 80.00% |
| no_identifiable_aspect | 9 | 11.25% |
| insufficient_context | 4 | 5.00% |
| language_out_of_scope | 3 | 3.75% |

English is recorded for 77 reviews, Russian for two and Spanish for one.
All three out-of-scope records remain in the frozen eighty-record array.
The English subset contains 64 aspect-bearing records and thirteen
zero-aspect records. Language verification for reviewed records was
inherited from the same reviewer's confirmed first-round records after
checking exact parent identity and unchanged source language.

The following table counts aspect entries. Sentiment percentages use 97
entries as the denominator.

| Sentiment | Entries | Share of 97 |
| --- | --- | --- |
| positive | 49 | 50.52% |
| negative | 44 | 45.36% |
| neutral | 4 | 4.12% |
| mixed | 0 | 0.00% |
| unclear | 0 | 0.00% |

| Aspect | Entries | Positive | Negative | Neutral | Mixed | Unclear |
| --- | --- | --- | --- | --- | --- | --- |
| functionality | 19 | 11 | 4 | 4 | 0 | 0 |
| usability | 12 | 4 | 8 | 0 | 0 | 0 |
| reliability | 9 | 0 | 9 | 0 | 0 | 0 |
| performance | 3 | 0 | 3 | 0 | 0 | 0 |
| pricing | 8 | 3 | 5 | 0 | 0 | 0 |
| customer_support | 3 | 2 | 1 | 0 | 0 | 0 |
| quality | 19 | 13 | 6 | 0 | 0 | 0 |
| fulfillment | 9 | 3 | 6 | 0 | 0 | 0 |
| personnel_service | 14 | 13 | 1 | 0 | 0 | 0 |
| privacy | 1 | 0 | 1 | 0 | 0 | 0 |
| other | 0 | 0 | 0 | 0 | 0 | 0 |
| unclear | 0 | 0 | 0 | 0 | 0 | 0 |
| Total | 97 | 49 | 44 | 4 | 0 | 0 |

The 97 entries form 84 distinct review-category pairs across 64 reviews.
Twenty-three reviews contain multiple entries (28.75% of 80). Sixteen
reviews span multiple distinct aspect categories; other multi-entry
records distinguish targets within the same category.

Each application contributes ten reviews; each analytical category
contributes twenty.

| Application | Aspect-bearing reviews | Entries | Positive | Negative | Neutral |
| --- | --- | --- | --- | --- | --- |
| Todoist | 8 | 17 | 9 | 7 | 1 |
| Microsoft To Do | 10 | 12 | 5 | 7 | 0 |
| Duolingo | 6 | 6 | 6 | 0 | 0 |
| Khan Academy | 6 | 9 | 5 | 3 | 1 |
| Amazon Shopping | 10 | 16 | 2 | 12 | 2 |
| Etsy | 8 | 14 | 7 | 7 | 0 |
| Uber | 7 | 9 | 6 | 3 | 0 |
| Lyft | 9 | 14 | 9 | 5 | 0 |
| Total | 64 | 97 | 49 | 44 | 4 |

| Category | Aspect-bearing reviews | Entries | Positive | Negative | Neutral |
| --- | --- | --- | --- | --- | --- |
| Productivity | 18 | 29 | 14 | 14 | 1 |
| Education | 12 | 15 | 11 | 3 | 1 |
| Shopping | 18 | 30 | 9 | 19 | 2 |
| Transportation | 16 | 23 | 15 | 8 | 0 |
| Total | 64 | 97 | 49 | 44 | 4 |

## Evidence and reproducibility

The freeze manifest binds the dataset, original export, sample, audit,
guidelines, schema and adjudication revision. Each decision records its
original/result record hashes, actual adjudicator, completion time and
reason. Validation checks all eighty parent identities and versions,
completed statuses, allowed enums, zero-aspect reasons and evidence
coordinates against original Unicode code points.
[Schema and semantic requirements](APPLE_ABSA_ANNOTATION_SCHEMA.md)

All one hundred evidence spans match their exact original title or body
slices. A separate post-freeze check recomputed the aggregates, checked all
nineteen decisions and verified the sixty-one unflagged records.

| Private artifact | SHA-256 |
| --- | --- |
| Frozen sample | `ea8a26e27cfe2ee2bce8d331e1c61719784c45f5fa05d91cab1a25c13f8b86e0` |
| Gold annotation array | `4f8f49f121ac01d4ec6e4884cc39597117ee4f0081334f5c56de1ff6e3c1b841` |
| Adjudication decisions | `674597b3140f579df38315a9dbfb6b9c89676f28398c6703002ed4eb0c08bd1c` |
| Final aggregate results | `ef23f479a0c1fcc79efffaca1d3cf5d6f6917ca879827c196cf9f521c73ae81a` |
| Frozen guideline document | `28304b0e367254040a722af57ec97e5095b659f1e34636b0e1aaac2cdfbdbec7` |
| Frozen schema document | `a23ac0bc4160b3389f43d441910a0cf96a83e76c6a8a4e87703fc5701084d8eb` |

An authorized local reproduction starts with these frozen private inputs,
checks the manifest's file hashes, validates the eighty records and their
nineteen decision links, then runs `aggregate(records, sample_rows)` from
`feasibility.apple_ingestion.adjudication_tool`. Compare the parsed result
with the frozen aggregate JSON. The SHA-256 values identify exact file
bytes; JSON reformatting changes those byte-level checksums.

The local annotation/adjudication implementation and synthetic tests
document the executable workflow. Source review text, individual real
labels, evidence spans, private decisions and Gold JSON remain in private
local storage. The public report supports aggregate verification; complete
reproduction requires authorized access to those inputs.

The release regression passed all 800 tests using a disposable PostgreSQL
instance. It included the synthetic annotation and adjudication tests.
No collection request, production database change or model training was
part of the release validation.

## Limits and next modeling step

This dataset was annotated and adjudicated under the direction of a single
human reviewer. No independent inter-reviewer agreement was measured.
Character-accurate evidence checks and schema validation do not establish
semantic accuracy.

Eighty purposively framed reviews provide limited coverage. Privacy has
one entry; several category/polarity combinations have zero observations.
Application quotas and selective retained windows limit population claims.
The 97 entries are correlated within their eighty parent reviews. Any
future splitting, uncertainty estimate or error analysis must respect
that grouping.

The existing sample informed taxonomy development and adjudication.
Exploratory experiments on it therefore carry development-set exposure.
Scores on the same data cannot establish general performance on unseen
users, applications, languages or future review windows. Intended data use
and retention arrangements remain project-level conditions in the
[access record](archive/PHASE_E_ACCESS_RETENTION.md).

Recommended next work is a small baseline experiment after project
confirmation. Predeclare the English scope, target representation and
evaluation procedure. Use a reproducible local baseline and, if appropriate,
an existing pretrained model under the permitted data boundary. Report
aspect identification, per-aspect sentiment and evidence localization
separately, together with abstention behavior and category support counts.
Keep review/version identities available for error tracing.

Further sample expansion should depend on a demonstrated modeling or
evaluation need and a separate project decision. The frozen first-round
dataset provides the initial bounded reference for that discussion.

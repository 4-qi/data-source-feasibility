# Mobile App Reviews versus Steam

**Assessment date: October 27, 2026 PDT.**

## Recommendation

**Recommend Apple App Store reviews as the primary source candidate for a broad consumer-experience ingestion pilot, with Google Play reviews as the backup. Retain Steam as the technical regression baseline.** This is an evidence-based source preference, not production acceptance or a claim that Apple is statistically superior across its population.

Both mobile sources were successfully tested across four app categories. Apple supplied more detailed experience text in the matched eight-product frame. Google provided useful examples across the same domains, with more brief reactions and an undocumented transport. Steam supplies a documented protocol baseline within the narrower gaming domain.

**Production conditions remain open for all three:** an applicable collection/retention/analysis basis and sustained online update validation. No source passed a long-term fresh-arrival, edit or deletion acceptance test in this feasibility study. No production scheduler, training corpus or storage pipeline was deployed.

## Sampling and Execution

The [existing public app manifest](mainstream/app_sample_manifest.json) defines two products per analytical category: Todoist/Microsoft To Do, Duolingo/Khan Academy, Amazon Shopping/Etsy and Uber/Lyft. The same eight app products were sampled from both stores, using the US market for each platform. Account populations and review content are not paired between stores.

- Primary quality sample: the first five returned page-1 reviews per app/store, **40 Apple and 40 Google records**; no star-based selection.
- Apple used JSON except the previously working XML paths for Microsoft To Do and Uber. Duolingo JSON returned entries in this round, superseding its earlier missing-entry observation; the cause of that variation is unknown.
- Four apps per store, one per category, had page-2 and repeat checks. Todoist Apple page 2 also recovered the five previously sampled records; other page-2 checks parsed two records each.
- Repeat reads occurred approximately four minutes later. The repeat check measures short-interval retrieval; day-scale freshness remains unvalidated.
- All **32 requests succeeded: Apple 16/16 and Google 16/16**. The probe used no credentials, redirects or automatic retries, capped response bodies at 2 MB, spaced requests by at least two seconds, and stopped a source on request/schema failure.

[Collection evidence](mobile_quality/collection.json) records the individual attempts and sanitized field statistics. Across every phase there were 71 parsed Apple occurrences representing 51 distinct IDs, and 68 Google occurrences representing 48 distinct IDs. Pagination and repeated records are not added to the primary quality denominator. The [comparison summary](mobile_quality/comparison_summary.json) separates all cohorts and phases.

### Sample Provenance

All 40 earlier Apple fingerprints were recovered from the returned windows, with matching full normalized body hashes. The returned text was then inspected for semantic usefulness. This recovered cohort includes five additional Todoist page-2 reviews and overlaps the new primary Apple sample in 35 records.

The recovered historical cohort and the current primary Apple sample each contain **28 useful reviews out of 40**. The two cohorts share 35 records, with five unique to each cohort. The annotation file therefore contains **85 distinct records**: 45 Apple reviews (40 primary and five additional page-2 records) and 40 Google reviews. Other pagination and repeat supplements remain outside the semantic assessment.

## Content-Review Method

The preserved [Steam content assessment](content_review.json) defines useful content as a concrete product experience, usability problem, contextual preference or experience-linked feeling. Generic reactions, uncontextualized praise and unrelated opinions are separated. The new review used that definition on actual returned bodies: complete short bodies, or the first 500 normalized characters of longer ones. Three primary Apple records were prefix-limited; none of the returned Google bodies exceeded 500 characters.

Ratings were hidden in the inspection display. This is an AI-assisted analyst review, not independent human-labelled ground truth or a validated sentiment classifier. Reasons and multi-label topics in the [new annotations](mobile_quality/content_review.json) summarize visible content without quoting source text. A useful complaint is not automatically a negative training label, and a star score is not guaranteed to match textual sentiment.

Text prefixes were kept temporarily outside the repository for inspection; author fields were not included, and URLs/emails were redacted from the display. Such redaction is not full PII anonymization. Temporary inspection material was excluded from delivery and removed after validation. The repository stores fingerprints, body hashes, lengths, field/timestamp metadata and abstract labels/reasons, not review bodies.

## Direct Comparison

Steam figures below are preserved October 20 evidence; mobile figures are this new experiment. Sources, dates, product counts, sampling queries and rating distributions differ. These are descriptive sample results, not a controlled platform-ranking experiment.

| Dimension | Apple App Store | Google Play | Steam |
| --- | --- | --- | --- |
| Executed breadth | 8 apps, 4 analytical categories | Same 8 apps, same 4 categories | 2 games; gaming domain |
| Request result | 16/16 this round | 16/16 this round | Historical 20/20 including negative supplement |
| Primary semantic sample | 40 | 40 | Historical 27; 4 targeted negatives not semantically assessed |
| Useful concrete experiences | **28/40 (70.0%)** | **17/40 (42.5%)** | **10/27 (37.0%)** |
| Other semantic labels | 12 low-information reactions | 20 low-information reactions, 3 unclear/off-topic | 16 low-information reactions, 1 unclear/off-topic |
| Median body length | 122 characters | 41.5 characters | 30 characters in the fixed baseline |
| Basic length eligibility | 36/40 | 30/40 | 16/27; eligibility is not usefulness |
| Rating coverage | 1, 2, 3 and 5 stars | All 1–5 star levels | Baseline all positive recommendations; 4 negatives added by explicit filter |
| Page-2 checks | 4 apps; no sampled ID overlap | 4 apps; no sampled ID overlap | Historical cursor pagination verified |
| Repeated first pages | 4 apps; same 5 IDs and body hashes per app | 4 apps; same 5 IDs and body hashes per app | Historical repeated baseline returned same 27 IDs |
| Update evidence | Feed `updated` fields; no new visible IDs or edits in short repeat | Web review timestamps; no new visible IDs or edits in short repeat | Official Updated query and separate creation/update fields; no replayed edit or new-arrival test |
| Interface/maintenance | Public RSS paths; format and intermittent entry availability need handling; no current general-purpose review API support guarantee established | Undocumented web RPC and nested response schema; maintenance risk | Official documented API, with quota/caching conditions |
| Production-use basis | Not established for this project's scheduled storage/model use | Not established for this project's scheduled storage/model use | Public API success does not establish all commercial/model uses |

The recommendation combines category breadth, text usefulness and collection behavior. Google's 42.5% versus Steam's 37.0% should be interpreted as sample descriptions rather than a demonstrated platform-wide quality difference. Steam's positive-only baseline, distinct query design and older sample are material confounders.

### Category and Product Variation

Each cell below is useful/inspected records. There are five records per app and ten per category.

| Category | Apps | Apple | Google |
| --- | --- | --- | --- |
| Productivity | Todoist / Microsoft To Do | 9/10 (4/5, 5/5) | 2/10 (0/5, 2/5) |
| Education | Duolingo / Khan Academy | 6/10 (3/5, 3/5) | 4/10 (3/5, 1/5) |
| Shopping | Amazon Shopping / Etsy | 7/10 (5/5, 2/5) | 5/10 (4/5, 1/5) |
| Transportation | Uber / Lyft | 6/10 (3/5, 3/5) | 6/10 (3/5, 3/5) |

Store differences varied by product. Duolingo, Uber and Lyft had equal useful counts, while much of Apple's lead came from productivity reviews. Excluding Duolingo from both primary samples, to match the earlier seven-app frame, yields Apple 25/35 and Google 14/35. These are sensitivity descriptions, not additional independent experiments.

Both stores contained specific learning/workflow complaints and wider service experiences. Some shopping and transport reviews concern delivery, returns, account/payment issues or drivers rather than app implementation. That diversity can help broad consumer-experience analysis, but it must not be mislabelled as an app bug. Amazon Shopping app reviews do not supply ASIN-wide Amazon product reviews.

### Observed Topics

Topic counts are multi-label and restricted to the visible inspected primary bodies; they need not sum to 40. They are not a validated automated topic model.

| Topic | Apple records | Google records |
| --- | --- | --- |
| Functionality/usability | 16 | 8 |
| Reliability/performance | 5 | 3 |
| Service/support experience | 6 | 7 |
| Price/subscription | 4 | 2 |
| Account/payment | 4 | 1 |
| Product/learning/catalog content | 5 | 3 |
| Delivery/fulfillment | 1 | 2 |
| Advertising/content clutter | 3 | 0 |

Generic praise remained common, particularly in several Google app windows. Concrete examples in the useful set include scheduling and synchronization problems, interrupted lessons, search changes, payment workflows and service delays. These are abstract analyst summaries, not source quotations. English UI/storefront selection did not guarantee English-only bodies: Spanish, French and mixed-language text was observed. Word-count eligibility and downstream language filtering need to account for that.

## Online-Update Readiness

Both stores passed bounded current retrieval, four-category pagination and four short repeat checks. All repeat windows contained the same IDs and body hashes, so **zero new visible IDs and zero text changes were observed**. No retained-window disappearance was observed. This does not establish that the source is stale, that nothing changed elsewhere, or that deletion synchronization works.

The newest returned timestamp per sampled app was roughly **27–81 hours old for Apple and 24–51 hours old for Google** at collection time. Apple timestamps are feed `updated` values, not proven original creation times. These ages are not measured ingestion latency: no independent ground-truth arrival stream or cache measurement exists. They support a specific freshness concern to validate, rather than a claim of immediate updates or a numeric SLA.

Further validation should confirm new review arrivals across multiple days, sufficient overlap between collection windows, and reliable handling of updated or deleted records. Apple's finite RSS retrieval window and Google's undocumented pagination behavior also require coverage checks.

## Reproduction

The [bounded probe](../probes/mobile_quality.py) implements the tested request and parsing logic, with CLI options, output protection, and safeguards to keep temporary inspection text outside the repository. It was checked offline after those wrapper changes and was not rerun live.

```sh
python probes/mobile_quality.py --help
# Live, bounded collection; use a fresh output directory:
python probes/mobile_quality.py initial --output results/mobile_quality_new --inspection-output /tmp/mobile-quality-inspection.json
# One planned repeat; the shared experiment budget is 32 requests:
python probes/mobile_quality.py repeat --output results/mobile_quality_new --inspection-output /tmp/mobile-quality-inspection.json
```

The collection script produces metadata; semantic labels come from the separate AI-assisted text inspection recorded in the annotation file. A fresh run may return different reviews and requires its own inspection. The [execution verification](mobile_quality/verification.json) records tests, metric consistency, link checks, historical preservation and temporary-text exclusion for the comparison execution.

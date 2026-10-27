# Feasibility Comparison

**Evidence date: October 20, 2026.**

## Current outcome

**47 of 48 API requests succeeded:** Steam 20/20, GitHub 8/9 and Hacker News 19/19. GitHub's one 403 had `Remaining=0` and stopped the source without retries. A separate Amazon robots metadata request is excluded from these totals.

Steam demonstrated repeatable review retrieval, with pagination and deduplication validated across the tested queries. GitHub delivered useful software feedback with an observed quota constraint; HN required more topic selection. These findings support the completed [Source Recommendation](source_recommendation.md).

## Baseline and repeatability comparison

The table describes the baseline and repeatability executions, **before** the separate two-request Steam negative supplement.

| Dimension | Steam Reviews | GitHub Issues | Hacker News | Amazon |
| --- | --- | --- | --- | --- |
| Operation | Two games: two Recent pages of six and one Updated page of four per game; repeated, then one follow-up execution | Two vscode issue-list pages of ten; exclude PRs; up to two comments on each of the first two issues with comments; repeated | First three Ask stories, up to two direct comments each; reuse selected story IDs on repeat | Historical browser evidence and official-route research; no new review requests |
| Requests | 18/18 HTTP 200 | Initial 8/8 HTTP 200; follow-up 403 with `Remaining=0`; 8/9 total | 19/19 HTTP 200; second run omits index request | Review/API collection `NOT_TESTED` |
| Returned records and deduplication | 32 normalized records per execution; 27 distinct review IDs; five overlaps across Recent/Updated | 20 list items retrieved; 12 pull requests excluded; 8 issues and 3 comments retained (11 distinct records). | Three stories plus six comments, nine distinct IDs per execution | No acquired review sample; unknown coverage is not an empty-corpus result |
| Pagination and relationships | No duplicates between the two Recent pages per game; descending creation/update timestamps within pages | No overlaps between original list pages; all three comments retain issue parent relationships | Six direct comments retain story parent relationships; no nested traversal | Separate review lists and pagination unverified in historical checks |
| Update evidence | Three Portal 2 Updated records had creation times earlier than modification times; not an edit-replay test | Creation/modification fields present; no `since` or deletion replay | Creation time, no universal modification time | Weekly official insights refresh does not establish individual-review updates |
| Repeatability | Same 27 IDs in all three executions; third started 965 seconds after first; same field-name sets | Same 11 IDs and field-name sets in two successful executions | Same nine IDs and field-name sets in two executions | No current automated repeated collection |
| Basic text eligibility | 16/27 eligible; 11 short/low-information | 11/11 eligible; not equivalent to 11 useful sentiment records | 8/9 eligible; one missing body; external links may pass heuristic | Not applicable |
| AI-assisted content review | 10/27 useful experiences/opinions (37.0%); 16 low-information, one unclear/off-topic | 7/11 useful software feedback (63.6%); two project explanations, one support suggestion, one technical resolution notice | 3/9 relevant experiences (33.3%); also questions/quotes, speculation, links and empty text | Strong retail relevance; no currently available broad automated raw-text route |
| Maintenance judgment | Explicit review objects and recommendation flags; short-text filtering and cross-query deduplication needed | Separate PRs, project descriptions, diagnostics and support replies; `User` does not prove consumer status | Topic/context filtering; per-item tree request cost | Access conditions, varying visibility and incompatible data granularities |
| Role | Initial technical pilot | Backup when quota is available | Comparison evidence only | Strategic retail relevance; see acquisition decision |

## Metric definitions and content review

“Returned” means normalized records accepted by the collector. GitHub's 20 raw list items and 12 excluded PRs are counted separately; 11 is not the raw API response count. Deduplication uses source, entity type and record ID, with repository for GitHub and app ID for Steam. Author identity is not the deduplication key.

The basic text eligibility screen requires at least 20 normalized characters and four words; records from explicitly identified Bot accounts are excluded. Content usefulness is evaluated separately. All 11 GitHub authors were typed `User`, including explanatory replies and a resolution notice carrying a bot marker. Neither a marker nor account type establishes authorship or consumer status.

The [Content Review](content_review.json) covers **47 distinct baseline records**: 27 Steam reviews, 11 GitHub records, and 9 Hacker News records. The assessment examined complete short texts or the first 500 normalized characters of longer records. Prefix-only assessment was used for 2 Steam, 7 GitHub, and 5 Hacker News records.

Content usefulness was evaluated through AI-assisted qualitative review. The results reflect the available text within the tested samples rather than representative platform-wide estimates. Steam recommendation flags and GitHub issue characteristics were evaluated separately from textual sentiment.

Steam experiences included cooperative play, performance/price, difficulty/satisfaction, atmosphere and mods, alongside short praise, numeric ratings and jokes. GitHub showed workflow and interface problems but also project/support material. HN included a non-product science link, demonstrating the need for topic selection. Zero language-heuristic flags do not prove language accuracy. Historical language-label problems remain historical risks, not new findings.

## Access and Repeatability

The initial two-round experiment completed 39/39 API requests successfully. A later Steam follow-up completed six additional requests, while GitHub encountered an HTTP 403 after its anonymous quota was exhausted.

Steam was queried again approximately 16 minutes after the initial run, returning the same 27 review IDs with consistent metadata. This supports repeatable collection within the tested interval. GitHub's rate-limit headers confirmed that the anonymous quota had reached zero, and the collector stopped without further requests.

Detailed request logs, execution timestamps, and test provenance are available through [Evidence and Methodology](../research/current_evidence.md) and the [Evidence Index](README.md).

## Separate Steam negative-review validation

All 27 distinct baseline reviews had boolean `voted_up=true`, despite `review_type=0` (All Reviews). Repeated runs did not create 81 distinct records or validate negative labels.

The supplement used official `review_type=2`, requesting one page of two reviews for each original game:

| Check | Observed result |
| --- | --- |
| Requests | Two GETs, both HTTP 200 |
| Returned / distinct reviews | Four / four |
| Duplicate records | Zero |
| Recommendation flags | Four boolean `false`; zero missing or invalid types |
| Overlap with baseline IDs | Zero |

See the [separate execution](negative_validation/steam_negative_20261020T082124904884Z.json) and [coverage summary](negative_validation/coverage_summary.json). Regression tests cover duplicate IDs, unchanged All Reviews defaults and correct preservation of `false`; numeric zero, strings or unexpected positive flags stop negative validation.

Across the baseline and targeted supplement, Steam produced **31 distinct reviews**: 27 baseline reviews and 4 additional negative-recommendation reviews. The targeted supplement is reported separately from the baseline content-quality assessment and does not represent the platform's natural recommendation distribution.

## Selection and Business Assumptions

Steam best combines a defined review target, original experience text, recommendation metadata, validated pagination, and update timestamps for the initial technical pilot. This assumes digital-product and game feedback is acceptable for method validation. GitHub's higher reviewed usefulness ratio does not make issue and support workflows interchangeable with product reviews.

Amazon remains strategically relevant for consumer-retail feedback. The [Amazon Acquisition Options](amazon_acquisition_options.md) and [Amazon Engineering Decision](amazon_decision.md) provide the detailed acquisition assessment and technical conclusions. Hacker News remains a comparison source, while Best Buy and other screened candidates were deprioritized.

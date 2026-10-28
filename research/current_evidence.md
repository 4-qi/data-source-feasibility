# Evidence and Methodology

**Evidence dates: October 20 and October 27, 2026 PDT.** The [Source Recommendation](../results/source_recommendation.md) contains the current decision; the [Evidence Index](../results/README.md) maps each study to its saved artifacts.

## Evidence Labels

| Label | Meaning |
| --- | --- |
| `VERIFIED` | Observed responses or inspected original local files |
| `DOCUMENTED` | Published source documentation; capability not necessarily executed |
| `INFERRED` | Engineering or qualitative analyst judgment |
| `UNVERIFIED` | Insufficient evidence for the stated requirement |
| `NOT_TESTED` | The relevant operation was not executed |

HTTP status, field presence and sampled record identity are observed evidence. Content-usefulness judgments are analyst assessments. Public readability, automated access, business relevance and downstream use rights are evaluated separately. A failed route does not establish that an entire platform is unavailable.

## Study and Artifact Boundaries

| Study | Date | Scope and interpretation |
| --- | --- | --- |
| Original three-source baseline | October 20 | Steam, GitHub Issues and Hacker News; 39/39 initial requests, 45/46 after follow-up, 47/48 after the negative supplement |
| Amazon acquisition assessment | October 20 | Published routes and historical browser observations; one separate robots metadata check, no review scraping |
| Initial mobile/supplier assessment | October 27 | Access screening, then 23 successful Apple RSS diagnostic GETs and a 40-record seven-app sample; supplier capability remained documented rather than authenticated |
| Platform-route recheck | October 27 | Separate HTTP attempts and a Bluesky WebSocket connection; verified Google web pagination and selected social-text routes |
| Focused mobile comparison | October 27 | Same eight app products across four categories; 32/32 requests, with equal 40-record Apple and Google primary samples |

The baseline `collection_summary.json` summarizes the Steam, GitHub, and Hacker News collection phases, including follow-up and negative-review validation. Later mobile and route experiments maintain separate execution records.

Repeated retrieval does not create independent reviews. Steam's baseline repeats returned the same 27 IDs; its targeted negative supplement added four distinct IDs. The failed GitHub follow-up retrieved no content and has a null overlap result, rather than an empty-corpus finding. Amazon metadata requests are separate from review requests.

Earlier route observations remain useful provenance. Apple XML recovered reviews where JSON lacked entries, and Duolingo returned entries during the later comparison. These observations qualify temporary access results without establishing a permanent format rule. Details remain in the [earlier mobile assessment](../results/mainstream_review_assessment.md) and [route reassessment](../results/source_route_reassessment.md).

## Content-Review Method

Useful content describes a concrete product experience, usability problem, contextual preference or experience-linked feeling. Generic reactions, uncontextualized praise, unrelated opinions and non-experience explanations are separated. Usefulness is not a sentiment label or a measure of whether an allegation is true.

The [baseline annotations](../results/content_review.json) cover 47 distinct records: 27 Steam, 11 GitHub and nine Hacker News records. Complete short bodies or the first 500 normalized characters were inspected; prefix-limited counts were two, seven and five respectively. The four targeted negative Steam reviews were outside that semantic review.

The [mobile annotations](../results/mobile_quality/content_review.json) apply the same definition to actual returned text, with ratings hidden in the inspection display. The primary comparison uses five page-1 reviews per app/store over the shared [eight-product manifest](../results/mainstream/app_sample_manifest.json). Three primary Apple bodies were prefix-limited; no returned Google body exceeded 500 characters. Multi-label topics describe the visible text and can overlap.

The earlier 40 Apple records were reacquired with matching full normalized body hashes and actually inspected. They overlap the current primary Apple sample in 35 records and add five Todoist page-2 records. The mobile annotation file therefore contains **85 distinct records**: 40 primary Apple, 40 primary Google and those five additional records. The recovered cohort is not an independent extra 40-record sample. Other pagination and repeat supplements remain outside semantic denominators.

All qualitative labels are AI-assisted judgments, not independent human ground truth. Equal product sampling improves the Apple/Google comparison but does not pair users or contents. The older Steam queries, two-game frame and positive-only quality baseline limit direct platform-level comparisons.

The separate basic text screen uses at least 20 normalized characters and four words, excluding declared `Bot` author types in the original collectors. It is an eligibility heuristic, not opinion detection. Storefront/UI language does not guarantee body language, and word counts require care with multilingual text.

## Collection Controls and Reproduction

The [baseline CLI](../src/feasibility/cli.py) provides bounded probes and a two-round experiment. Its experiment allows at most 40 requests, reuses selected HN story IDs and stops a source after errors or exhausted quota. The [negative validator](../src/feasibility/negative_validation.py) allows two GETs and four records.

The [shared HTTP client](../src/feasibility/http.py) validates HTTPS hosts, caps responses at 2,000,000 bytes, uses connect/read timeouts of 10/25 seconds and normally spaces requests by at least one second. Redirects and automatic retries are disabled. The client uses `trust_env=False` to ignore environment-provided proxy settings and `.netrc` credentials. No application credentials are loaded.

The [mobile comparison probe](../probes/mobile_quality.py) has a shared 32-request budget across initial and repeat phases, two-second spacing and a 2 MB response cap. It uses the observed RSS formats and Google web protocol, retains metadata, and stops a source on request/schema failure. Its CLI wrapper adds output protection and requires the inspection file to be outside the repository. The executed exploratory form and later wrapper validation are distinguished in the [comparison report](../results/mobile_review_comparison.md#reproduction).

Additional access diagnostics are isolated from the baseline CLI. The [RSS diagnostic](../src/feasibility/apple_validation.py), [CFPB diagnostic](../src/feasibility/mainstream_validation.py) and [route probes](../results/source_route_reassessment.md#reproduction-diagnostics) have their own bounded scopes. Offline tests validate parsing and controls; they do not constitute live executions of every final CLI wrapper.

## Data Handling

Published results contain request metadata, field presence, timestamps, quality statistics, fingerprints and abstract annotation reasons. Review bodies, author identifiers and credentials are excluded. Fingerprints support linkage and are pseudonymous, rather than a guarantee of anonymity.

The original `--inspect-text` display limits text to 500 normalized characters and strips links/mentions. The mobile inspection display omitted author fields and redacted URLs/emails. Neither process is full PII anonymization. Temporary mobile prefixes were kept outside the repository for actual inspection and removed after validation. Inspection output must not be redirected into published artifacts.

## Online-Update Interpretation

Stable IDs and body hashes establish repeatability within the tested windows. Recent timestamps, an Updated query or a successful page-2 request do not prove new arrivals, full history, or edit/deletion capture. The approximately four-minute mobile repeats showed no new visible IDs or text changes; this does not establish source staleness.

Timestamp ages in the comparison are descriptive values, not measured ingestion latency. Sustained online-update acceptance requires longer observations and explicit window/change handling. Applicable collection, retention and model-use conditions remain separate production prerequisites.

## References and Historical Inputs

The original four-page Project Brief and earlier research materials informed the project requirements and source assessment. These materials are maintained separately from the repository. The [original plan](execution_plan.md), [historical Amazon access notes](amazon_access.md) and [Amazon metadata decision](amazon_direction_update.md) retain the relevant provenance.

Baseline references were reviewed October 20; mobile/route references were reviewed October 27. Documentation retrieval is excluded from collection request counts.

- [Steam GetAppReviews](https://partner.steamgames.com/doc/webapi/IUserReviewsService) and [API terms](https://steamcommunity.com/dev/apiterms): official query/cursor fields, caching/quota conditions and data-use responsibilities; the collector uses this service rather than legacy `/appreviews`.
- [GitHub Issues](https://docs.github.com/en/rest/issues/issues), [comments](https://docs.github.com/en/rest/issues/comments), [REST limits](https://docs.github.com/en/rest/using-the-rest-api/rate-limits-for-the-rest-api) and [API terms](https://docs.github.com/en/site-policy/github-terms/github-terms-of-service#h-api-terms): PR filtering, parent relationships, pagination and shared quota.
- [Official HN API](https://github.com/HackerNews/API) and [YC terms](https://www.ycombinator.com/legal): item trees, missing/dead/deleted content, timestamps and commercial-use conditions; software licensing does not license all comments.
- [Amazon source index](../results/amazon_acquisition_options.md#source-index): official acquisition routes, supplier claims, use/coverage constraints and incomplete retrievals, including the recorded Rainforest changelog timeout.
- [Mobile acquisition assessment](../results/mainstream_review_assessment.md) and [route reassessment](../results/source_route_reassessment.md): Apple/Google access conditions, supplier documentation, web protocol mappings and social-stream sources. Third-party implementation evidence is distinct from an official API contract or data-use grant.

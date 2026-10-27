# Evidence and Methodology

**Evidence date:** October 20, 2026 PDT. The completed study combines recorded collection experiments, source documentation and engineering analysis. The [Evidence Index](../results/README.md) identifies each execution artifact; the [Feasibility Comparison](../results/feasibility_comparison.md) interprets the results.

## Evidence labels

| Label | Meaning |
| --- | --- |
| `VERIFIED` | Observed responses or inspected original local files |
| `DOCUMENTED` | Published source documentation; not an executed capability |
| `INFERRED` | Engineering or qualitative analyst judgment |
| `UNVERIFIED` | Insufficient evidence for the stated requirement |
| `NOT_TESTED` | No execution of the relevant operation |

Request statuses are observed evidence. API/policy descriptions are documented evidence. Content-usefulness judgments and source-selection recommendations are analysis. Public readability, technical API access and downstream data-use rights are assessed separately.

## Historical inputs

Original project materials, earlier assessments, and historical access evidence are preserved separately from the published repository. Selected internal materials remain available in local archives, while the maintained research documents retain the relevant findings and provenance.

The original four-page Project Brief was reviewed to distinguish stated project requirements from engineering assumptions in the requirements matrix.

Historical browser/API observations are separate from the new collection counts. Amazon's October 16 browser visibility varied between anonymous sessions. The [historical access assessment](amazon_access.md) records that observation; the completed [acquisition matrix](../results/amazon_acquisition_options.md) supersedes its earlier route list. The [execution plan](execution_plan.md) records the bounded validation design.

## Experiment phases

| Phase | Recorded evidence |
| --- | --- |
| Initial experiment | Two rounds across three sources; 39/39 successful requests; timestamped experiment and six run files |
| Follow-up | Six successful Steam requests; one GitHub 403 with `Remaining=0`; cumulative 45/46 successes |
| Negative-review validation | Two Steam requests, four distinct records with boolean `voted_up=false`; cumulative 47/48 successes |
| Amazon assessment | Original Brief and published route/policy documentation; one separate robots metadata check; review collection `NOT_TESTED` |

The original experiment and pre-supplement aggregate are preserved separately from the latest `collection_summary.json`. The latest aggregate includes all collection phases. A new invocation of the experiment writes its own snapshot and refreshes the convenience summary; fixed content annotations remain tied to the original sample.

The follow-up Steam run began 965 seconds after the first. Its same IDs and schema establish repeated retrieval, not independently verified freshness. The failed GitHub request retrieved no content; its overlap comparison is null, not an empty-corpus finding. The [historical Amazon collection record](amazon_direction_update.md) preserves the robots-check limits and synthetic-only parser archive provenance.

## Collection controls and outputs

The [CLI](../src/feasibility/cli.py) implements bounded single-source probes and a two-round experiment. The experiment uses at most 40 requests, repeats selected HN story IDs and skips a source after errors or exhausted quota. The separate [negative validator](../src/feasibility/negative_validation.py) allows two GETs and four records.

The [HTTP client](../src/feasibility/http.py) validates the HTTPS host, applies request budgets and at least one-second intervals in normal CLI use, caps responses at 2,000,000 bytes and uses connect/read timeouts of 10/25 seconds. It disables redirects and automatic retries, stops after access/rate denial, and separates transport errors from source responses. Ambient netrc/proxy settings are disabled with `trust_env=False`; no credentials are loaded. Proxy-only environments require an explicit transport configuration decision.

Responses are processed in memory. Saved files contain request metadata, field presence, quality metrics and record fingerprints rather than raw review bodies, usernames or account IDs. Fingerprints support record linkage and are pseudonymous, not a guarantee of anonymity. Synthetic tests exercise normalization, pagination, deduplication, relationships and error handling separately from live evidence.

`--inspect-text` prints up to 500 normalized characters per distinct inspected record for analyst review, stripping links and mentions from the display. This is not general PII anonymization. Inspection output must not be redirected into repository artifacts. Default execution stores no source prose.

## Content-review methodology

[content_review.json](../results/content_review.json) records AI-assisted qualitative assessments of 47 distinct baseline records: 27 Steam reviews, 11 GitHub records, and 9 Hacker News records. Complete short texts or the first 500 normalized characters of longer texts were reviewed; prefix-limited counts are two Steam, seven GitHub and five HN records. The four targeted negative reviews are outside this semantic review.

Useful content describes a concrete experience, usability problem or contextual preference. The separate basic eligibility screen requires at least 20 normalized characters and four words and excludes declared `Bot` author types. Eligibility is not useful-opinion detection; usefulness is not a sentiment label. These qualitative assessments describe the sampled records and are used for comparative source evaluation. Detailed categories and examples are in the [comparison](../results/feasibility_comparison.md).

## Source references

References were reviewed October 20, 2026. Documentation retrieval is excluded from collection request totals.

- [Steam GetAppReviews](https://partner.steamgames.com/doc/webapi/IUserReviewsService): `input_json`, Recent/Updated queries, cursors, anonymous caching and quota conditions. The implementation uses this interface, not legacy `/appreviews`.
- [Steam API terms](https://steamcommunity.com/dev/apiterms): data-use restrictions and responsibilities. Technical validation does not establish commercial retention or model-training rights.
- [GitHub Issues](https://docs.github.com/en/rest/issues/issues), [comments](https://docs.github.com/en/rest/issues/comments), [REST limits](https://docs.github.com/en/rest/using-the-rest-api/rate-limits-for-the-rest-api) and [API terms](https://docs.github.com/en/site-policy/github-terms/github-terms-of-service#h-api-terms): anonymous reads, PR exclusion, pagination and shared quota.
- [Official HN API](https://github.com/HackerNews/API) and [YC terms](https://www.ycombinator.com/legal): item relationships, missing/dead/deleted content, timestamps and commercial-use restrictions.
- [Amazon acquisition sources](../results/amazon_acquisition_options.md#source-index): Customer Feedback, Data Portability, Creators, suppliers, webpage restrictions and DSA research access. Supplier statements document capabilities, not project-specific rights; the matrix records incomplete policy retrieval and the Rainforest changelog timeout.

The Amazon assessment focuses on technical feasibility, documented access options, and their suitability for the project's data requirements.
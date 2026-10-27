> **Historical assessment.** The complete October 20, 2026 route assessment and current decision are in the [acquisition matrix](../results/amazon_acquisition_options.md) and [Amazon decision](../results/amazon_decision.md). They add Data Portability full text, coverage/purpose limits and supplier due diligence. The earlier route list below is not exhaustive.


# Amazon: actionable access assessment

Reviewed **2026-10-20 PDT**. Labels: VERIFIED = observed response; DOCUMENTED = official description; INFERRED = engineering judgment; NOT_TESTED = no current call. No Amazon product/review requests, credentials, account actions, or review scraping were performed. A later metadata-only robots request is recorded in [direction update](amazon_direction_update.md); it is not a review request.

## What the historical browser check establishes

The preserved October 16 evidence shows real review text and visible title, stars, display name, calendar date, format and purchase verification in one anonymous context. Another clean context showed a sign-in requirement for the same product. The cause is unknown. Long-review expansion, the separate listing, pagination, stable review IDs and repeatable automated retrieval were not established. This is historical browser evidence, not a current automated collection success.

## Routes and their actual data products

| Route | Requirements | Data obtained / missing | Assessment Status |
| --- | --- | --- | --- |
| Customer Feedback SP-API | Selling-partner authorization plus approved developer/application role; seller: Selling Partner Insights; vendor: Brand Analytics | ASIN/category review topics, impacts and trends, selected customer snippets; English, weekly refresh. Not a demonstrated individual full-review corpus with review IDs and timestamps. | DOCUMENTED; no credentials or qualifying company account supplied. Live PoC NOT_TESTED. |
| Company-held written permission / separate content license | The company must supply an agreement covering the target data, automated method, fields, usage and retention | Could allow an agreed raw-review route; none supplied or verified | UNVERIFIED availability; no invented endpoint or scraping implementation |
| Public consumer review pages | Historically variable visibility; collection restrictions already documented | Some visible text is not stable automated access or permission | No authorized scraper route currently demonstrated; no new automated extraction |
| Static sandbox | Official overview lists a static sandbox | Mock/static behavior does not establish access to live customer content | Not used to represent a live PoC |

The official [overview](https://developer-docs.amazon.com/sp-api/docs/customer-feedback-api) separates seller/vendor insights from raw individual reviews. The [ASIN tutorial](https://developer-docs.amazon.com/sp-api/docs/get-feedback-insights-asin) specifies authorization and approved roles, and describes topic/trend operations. The [authorization guide](https://developer-docs.amazon.com/sp-api/docs/authorizing-selling-partner-api-applications) distinguishes public-application OAuth from private-application self-authorization. These are current DOCUMENTED findings, not API executions.

## Access Requirements Identified

1. Integration requires a qualifying seller/vendor account and approved SP-API app/role, or a suitable separate review-content agreement. Credentials remain outside documentation and version control.
2. Weekly aggregate topics/snippets require explicit acceptance as a separate data product; they cannot silently replace a raw-text sentiment pipeline.
3. If individual raw reviews are essential, obtain an explicit available route and confirm fields, target products, retention and analysis/training scope. Neither seller status alone nor a consumer login establishes this permission.
4. Only then implement the matching small collector: pagination, record IDs, deduplication, completeness and repeatability should be measured against the actual authorized data product.

**Historical recommendation:** retain Amazon's consumer-product relevance while using another source for the technical pilot. The completed assessment recommends Steam for that pilot and GitHub Issues as the quota-dependent backup. Best Buy was deprioritized.


## Documented collection boundary

No existing review-collection agreement or authorization was verified or provided. Automated Amazon review scraping was excluded from implementation and execution. The active deliverable contains no Amazon scraper. One robots metadata request returned HTTP 200, with no product/review requests. See the [historical collection boundary](amazon_direction_update.md).

Historical Amazon API documentation and third-party scraping claims were not treated as evidence of a currently available, authorized full-review acquisition route. The completed [Amazon Acquisition Options](../results/amazon_acquisition_options.md) provides the updated assessment of official interfaces and alternative acquisition methods.
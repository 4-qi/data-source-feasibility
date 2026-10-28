# Amazon Engineering Decision

**Assessment date:** October 20, 2026. **Status:** complete.

## Decision

**Do not implement broad Amazon raw-review ingestion under current access conditions.** Amazon retains strategic value for consumer-retail applications, but no currently verified route establishes the required multi-consumer review coverage and permitted use. This is a conclusion about the assessed routes and available evidence, not a claim that future access is impossible.

Steam served as the original technical baseline, with GitHub Issues as the quota-dependent software-feedback backup. The [Source Recommendation](source_recommendation.md) records the current selection following the mobile comparison; the [Amazon Acquisition Options](amazon_acquisition_options.md) provides the detailed retail-route evidence.

## Feasibility constraints

| Route | Decisive constraint | Condition for reconsideration |
| --- | --- | --- |
| Customer Feedback SP-API | Aggregate topics, trends and snippets rather than an established individual full-review feed | Accept aggregate insights as a separate product and satisfy seller/vendor account, role and application requirements |
| Data Portability | Reviews belong to individually authorizing customers; regional/purpose conditions and participant coverage differ from ASIN-wide collection | Adopt an eligible consent-based product with feasible recruitment and acceptable coverage |
| Creators / deprecated PA-API | Affiliate catalog fields and usage conditions do not establish a suitable sentiment corpus | A suitable current data product and explicit use rights would need to be demonstrated; do not build on deprecated PA-API |
| Licensed supply | Origin/content rights, target coverage and update/completeness evidence remain unverified | Pass rights review and authorized technical acceptance |
| Webpages | Historical visibility varied; full lists and pagination were not established; applicable collection authorization is unverified | Establish a suitable permitted route before implementation; consumer login alone is insufficient |

The Project Brief prioritizes access without login or gated APIs. Licensed supply, Data Portability, and SP-API would depart from the Brief's preference for public, ungated access and should be evaluated as explicit trade-offs. Ratings and timestamps are useful examples in the Brief rather than mandatory fields for every source.

## Integration entry criteria

Future supply for **multiple consumers, target ASINs and original full text** must pass the following gates. These are proposed production prerequisites outside the completed study.

| Review Area | Required evidence | Acceptance condition |
| --- | --- | --- |
| Data sourcing | Specific origin, supply rights, markets/ASINs and content coverage; see the [supplier admission package](amazon_acquisition_options.md#6-suppliers-and-dedicated-licensing) | Marketing, paid credentials or public-availability claims alone do not qualify |
| Legal and privacy | Acquisition/delivery basis, retention, analysis, client delivery, training, territory, duration, deletion and dispute responsibilities | An acceptable basis for the intended use before real sample import |
| Engineering validation | Authorized limited-sample checks of text completeness, IDs, pagination, duplicates, updates/deletions and selection bias | Samples meet agreed requirements; missing keys or deletion guarantees require tested alternatives |

A bounded commercial supply assessment is justified by Amazon's retail breadth, but connector development before these gates pass is not. Public documentation establishes neither an approval probability nor a procurement price or schedule. Bright Data is a documented capability lead, not an approved supplier; Rainforest documentation changes require clarification before relying on complete historical coverage.

Portability is not recommended for immediate development toward the broad ASIN corpus objective. Consent management, participant recruitment, regional eligibility and purpose restrictions make it a distinct business model. Its Category-1 review scope must not be assumed eligible for the published Category-2/3 sandbox process.

## Conditional engineering design

The following design is `INFERRED`, not implemented or live-tested:

- **Licensed feed:** Match the product and manifest to the agreement. Use source, market and a stable review ID for idempotency; versions or payload hashes for changes. Preserve ASIN mapping and observation time; handle deletion and license expiry separately.
- **Portability:** Register consent and HTTPS notifications, process asynchronous queries and paginated files, then validate schema and quality. Preserve consent-subject relationships, ASIN, `eventDate` and `versionID`. Without independent review IDs, hashes remove exact payload duplicates only; quarantine identity conflicts rather than assuming one review per customer/product. Stop imports after revocation and apply deletion conditions.
- **SP-API:** Store aggregate snapshots by market, child ASIN, topic and observation period. Snippets are not complete individual-review coverage.

Separate review bodies, author/brand replies, AI summaries and rating-based weak labels; preserve provenance and coverage.

## Reconsideration Criteria

Amazon integration may be reconsidered if a verified data-supply arrangement becomes available, the project adopts aggregate customer-feedback insights, or an appropriate consent-based data model is established.

Each option must satisfy its applicable access, coverage, and usage requirements before implementation.

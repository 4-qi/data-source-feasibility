# Amazon Acquisition Options and Feasibility Matrix

**Research date: October 20, 2026.** This assessment evaluates acquisition options for individual Amazon product reviews from multiple consumers, drawing on the Phase I Project Brief, existing access observations, and official documentation.

Evidence labels: `VERIFIED` = local original files or observed responses; `DOCUMENTED` = published documentation; `INFERRED` = engineering analysis; `UNVERIFIED` = insufficient evidence; `NOT_TESTED` = no execution. Supplier capability claims do not establish verified supply rights.

## 1. Brief requirements and engineering assumptions

The evaluation criteria are based on the original Phase I: Data Ingestion & Infrastructure Project Brief (pp. 1–4), provided internally and not included in this repository. Extraction provenance is recorded in [Evidence and Methodology](../research/current_evidence.md).

| Requirement | Basis and status | Implication for Amazon |
| --- | --- | --- |
| Original user text and semantic relevance | Pages 1–2: open-web text, automated acquisition and structuring for annotation, training and experimentation; core direction | Review bodies and aggregate topics are different data products. Insights cannot substitute for individual source text. |
| Sufficient volume, public access without login or gated APIs | Explicit source criterion on page 2 | Authorized APIs and licensed data sources do not meet the Brief's preference for public, ungated access and should be evaluated as explicit trade-offs. |
| Parseable structure, repeatable collection, cleaning and relational storage | Pages 1–3 | Preserve record relationships and provenance for subsequent integration. |
| Ratings, timestamps and user metadata | Examples of sentiment relevance on page 2; not universally mandatory fields | Valuable when available. Requiring text and a product/subject association for Amazon records is an engineering proposal. |
| ASIN, independent review ID and revision version | Not specific fields mandated by the Brief | Amazon-specific design suggestions. Missing stable IDs need explicit treatment. |
| Continued updates, incrementality and deletion synchronization | Page 1 describes a continuing pipeline; page 3 places scheduling and periodic updates in future development | Require a maintainable repeatable route; this phase need not prove a real-time event stream or complete deletion replay. |
| Commercial analysis and model use | Pages 1 and 3 include analysis, annotation and training goals | Check acquisition, storage, analysis/inference, training/fine-tuning and redistribution separately. No model was trained. |

Full-text fields, coverage of target products across consumers, and permission for the project are separate requirements. Evidence for one does not establish all three.

## 2. Decision matrix

| Route | Data granularity and full text | Multi-consumer coverage by ASIN | Suitability for current ingestion | Investment decision |
| --- | --- | --- | --- | --- |
| Customer Feedback SP-API | Topics, impacts, trends and selected snippets; no established individual full-review stream | Eligible child-ASIN insights, not enumeration of all reviews | Cannot replace raw-review ingestion; access also unavailable | Integrate only if aggregate insights are accepted and account/role requirements are met. Authorization does not create a full-text endpoint. [S1–S3] |
| Data Portability: product reviews | Official mechanism for the authorizing customer's own original reviews; text and other fields are not all required | Only individually authorizing eligible users; ASIN grouping within authorized data does not extend to other authors | Full-text mechanism exists, but does not meet broad, ungated collection requirements | Pursue only for an appropriate consent-based user product or panel, with application approval, individual consent and regional/purpose compatibility. [P1–P8] |
| PA-API / Creators API | Affiliate catalog; no established paginated individual full-review feed | Product discovery does not establish review-body coverage | Not selected for a sentiment corpus | Affiliate terms do not establish general analysis/training rights. PA-API has been superseded by Creators; do not develop the deprecated integration. [C1–C4] |
| Dedicated content license / verified supplier | A contract could specify full text; no existing project contract or validated supply | Depends on agreed products, markets, authors and coverage | Conditional only; admission requirements unmet | Rights, coverage and sample commitments are prerequisites for future integration or purchase. [V1–V6] |
| Direct webpage collection | Some historical review visibility; full lists, expansion and pagination unverified | A target-ASIN page does not establish complete access | Not implemented | Permitted collection, visibility and repeatability have not been established for this project. [W1] |
| EU DSA researcher access | Official research-access framework, not general commercial licensing | Specific EU platform, eligibility and systemic-risk research purposes | Not appropriate for the current project | This commercial sentiment product has not been shown to qualify. [R1] |

### Integration complexity and update evidence

These are `INFERRED` relative estimates, not quotes, schedules or implemented capabilities.

| Route | Complexity | Pagination and update evidence |
| --- | --- | --- |
| SP-API | Moderate: application roles, authorization and aggregate snapshots | Topic/trend operations and weekly refresh; no demonstrated individual-review cursor or edit/deletion replay. |
| Portability | High: individual consent, application admission, notifications/files, renewal and deletion | File-list pagination documented. Re-querying during valid consent does not establish review deltas or deletion events. |
| Creators | Moderate catalog client, but fields and purpose do not fit | Catalog pagination/refresh does not establish review pagination/updates. |
| Licensed supply | Significant rights/procurement review; client depends on the actual feed | Periodic-refresh claims do not establish a complete change feed. IDs, pagination, deltas and deletions need contractual and sample validation. |
| Webpages | High and uncertain: session variation, markup and maintenance | Historical evidence did not establish a separate review list, second page, edits/deletions or sustained access. |

## 3. Customer Feedback SP-API

`DOCUMENTED`: a seller/vendor service with child-ASIN topics sortable by mentions or star-rating impact. The tutorials require Selling Partner Insights or Brand Analytics roles and selling-partner authorization. The overview describes English-language insights, weekly refresh and specified markets. [S1–S3]

- **Data and coverage:** ASIN/category topics, metrics and snippets, not complete review objects with review IDs, authors, original bodies and individual timestamps. Topic/snippet counts are not review counts.
- **Pagination and updates:** Limited positive/negative topic operations are not review cursors. Trend snapshots do not prove review-level deltas or deletion synchronization.
- **Storage, analysis and training:** Applicable AUP/DPP and agreements govern use. Policy indexes and available pages were reviewed, but company contracts, specific analysis scope and snippet-training rights were not established. PII retention rules must not automatically be applied to non-personal insights. [S4]
- **Engineering:** Moderate inferred complexity: authorization and scheduled snapshots keyed by marketplace, child ASIN, topic and observation period. Store as `insight_snapshots`, rather than individual `reviews`.
- **Blockers:** Both application/account eligibility and incompatible data granularity. Resolving authorization alone does not deliver raw reviews.

## 4. Data Portability: an official full-text mechanism

### 4.1 Authorizing subject, fields and regions

`DOCUMENTED`: `portability::product_reviews` is the LWA scope; `portability-product-reviews` is the Category-1 data scope ID. The schema includes `marketplace`, `eventDate`, `asin`, `versionID` and potentially `text`, `title`, `starRating`, media links, `featureRatings` and `status`. **Only the first four fields are required.** Text and ratings cannot be assumed present. The documented Portability schema does not expose a dedicated, stable review ID. [P2]

The data consists of reviews **provided by the authorizing customer**. Multiple consumers can each authorize an application; one customer's consent does not cover other authors. There is no arbitrary-ASIN download route for all consumers' reviews. The overview lists marketplace coverage for BE/FR/DE/IE/IT/NL/PL/ES/SE; eligibility also depends on registration location and applicable rules. A US deployment endpoint does not establish access to arbitrary US consumer data. EU customer eligibility does not by itself establish a same-nationality requirement for developers. [P1, P3]

### 4.2 Integration and repeatability

`DOCUMENTED`: onboarding includes identity/security assessment, LWA configuration, application allowlisting and an HTTPS notification endpoint. Customers select scopes and time ranges and authorize access. The flow is Create Data Query → completion notification → paginated schema/data file links → download and schema-based parsing. [P3–P6]

`nextPageToken` paginates query-result files, not reviews for an arbitrary ASIN. Customers may authorize future access, with a maximum selectable duration of one year; revocation or expiry ends authorization. Re-querying within valid consent does not establish a public review-change stream. The Create interface does not publish `updated_since` or ASIN filters. Versioning, repeated-query contents and deletion semantics were not tested. Response caching, file-link expiry and query-read windows make notification, download and renewal time-sensitive workflows. [P4–P6]

### 4.3 Purpose and use conditions

The dedicated **Portability API Schedule** was identified in the LWA agreement. It distinguishes DMA/Data Act purposes, restricts access and transfers beyond authorization, requires security and deletion mechanisms, and addresses independent-controller responsibilities and cross-border processing. Consent to import does not automatically authorize indefinite retention, delivery of raw text to clients or model training. Nor does the agreement establish a blanket ban on every commercial use; the specific product and training purpose must be assessed. [P7]

### 4.4 Engineering and investment decision

A future eligible consent-based product could use: authorization register (scope/purpose/expiry) → notification jobs → paginated file manifest → schema validation → record quality checks → access-controlled version storage → import suspension and deletion handling. Preserve internal consent-subject relationships, marketplace and ASIN. Treat `eventDate` as documented record-generation time, not an assumed first-publication or modification time. Without stable review IDs, use payload hashes only for exact duplicates, preserve `versionID` and quarantine identity conflicts. Do not assume one review per user/ASIN.

This design is `INFERRED`, **not implemented or tested**. Recruitment, regional/purpose restrictions and consent lifecycle management exceed the complexity of an HTTP client. Portability is a real option for a different business model; it does not justify immediate application development for broad ASIN-based corpus acquisition.

The published sandbox process requires relevant assessments and Category-2/3 scope requests, with up to five owned/controlled accounts. Product reviews are Category-1. Applicability of that process to this review scope was not confirmed; no anonymous sandbox availability is implied. No application or sandbox call was made. [P8]

## 5. Product Advertising / Creators

`DOCUMENTED`: Creators serves affiliate product catalogs and requires Associates/Creators registration, credentials and an applicable Partner Tag. PA-API 5 has been deprecated in favor of Creators. A catalog field named `customerReviews`, or a null example, does not establish a full-review stream. [C1–C2]

The IP License addresses promotional display and restrictions on aggregation, analysis, extraction/reuse and training/fine-tuning without written approval. Non-image content generally requires refresh after 24 hours of caching, with specific ASIN exceptions. These caching conditions must not be applied to Portability or SP-API. [C3–C4]

Catalog pagination/refresh does not prove review pagination or change retrieval. Credentials alone do not resolve field or purpose suitability. Historical Amazon API examples from 2007–2011 are not current capability evidence.

## 6. Suppliers and dedicated licensing

| Supplier / route | Public evidence reviewed | Unverified questions | Decision |
| --- | --- | --- | --- |
| Bright Data Amazon Reviews | Supplier lists text, rating, ASIN, date and periodic refresh; terms require lawful use and retain third-party-rights restrictions. [V1–V2] | No project-specific contract or rights chain establishing permitted supply/reuse; history, deltas and deletion support untested | Due-diligence lead, not an approved supplier. General licenses or compliance slogans do not establish content rights. |
| Rainforest API / Traject Data | Parameter docs describe ASIN reviews; product-update indexes also mention `reviews_v2` deprecation, unavailable `most_recent` and product-page top reviews. [V3] | Current distinction between review routes, markets, full text, updates and project rights | Documentation changes require clarification; not a verified complete feed. No calls made. |
| AWS Data Exchange | Providers must declare publishing rights; subscribers accept a specific Data Subscription Agreement. [V4] | No specific Amazon review listing and rights terms verified | Contracting mechanism; AWS listing does not itself establish Amazon retail-review authorization. |
| Bazaarvoice | Contract/API-key scope and licensed-content syndication mechanisms documented. [V5–V6] | No verified right to supply Amazon-origin reviews; brand-collected or syndicated content is not automatically Amazon-native | Existing owned/licensed content could be assessed separately; not a confirmed Amazon route. |
| Direct dedicated agreement | A possible procurement path for specified data, sources and purposes | No verified publicly available commercial program promising broad Amazon full text | Confirm written availability before investment; agreement availability is not guaranteed. |

Rainforest's published documentation indicates changes to its review-related APIs, but the applicability of these changes to its current standard reviews endpoint has not been fully verified.
Supplier capabilities were assessed based on published documentation. No project-specific data rights, coverage guarantees, pricing, or service commitments have been verified.

**Proposed procurement admission package:**

1. Document the data origin, lawful acquisition and distribution basis, and contractual scope of supply.
2. Separate permissions for retention, internal commercial analysis, client delivery, training/fine-tuning and model-output reuse; specify term, territory, withdrawal/deletion, termination and rights-dispute responsibilities.
3. Markets/ASINs, author/time coverage, selection method, stable IDs, truncation, version/deletion support and update frequency. Define whether “complete” means individual full text or exhaustive review coverage.
4. After rights review passes, conduct authorized small-sample field, deduplication, pagination and update checks. Marketing pages are not acceptance evidence.

Paid or gated data sources depart from the Brief's public-access criterion and should be evaluated as explicit trade-offs. A static dataset alone does not establish sustainable online collection.

## 7. Webpages and other formal routes

Historical browser testing showed that individual reviews were visible without login in one session, while another session required sign-in for the same product. This inconsistency, together with Amazon's restrictions on automated extraction, prevents treating public review pages as an established acquisition route for the project.
Specialized researcher-access programs were also considered but do not provide a general commercial review-ingestion route.

## 8. Decision

**Do not proceed with broad Amazon raw-review ingestion under the current access conditions.**

Customer Feedback SP-API provides aggregated insights rather than individual review records, while Data Portability covers only customers who individually authorize access to their own reviews. No licensed acquisition route with verified coverage and usage rights has been identified.

Amazon remains a strategic candidate for consumer-retail applications. Integration can be reconsidered when an authorized data source meets the project's coverage and usage requirements.

See the [Amazon Engineering Decision](amazon_decision.md) for detailed implementation criteria.

## Source index

Access dates: October 20, 2026 PDT.

- **S1** [Customer Feedback overview](https://developer-docs.amazon.com/sp-api/docs/customer-feedback-api): granularity, markets, refresh and sandbox type.
- **S2** [ASIN insights tutorial](https://developer-docs.amazon.com/sp-api/docs/get-feedback-insights-asin): roles, authorization, topics and trends.
- **S3** [getItemReviewTopics](https://developer-docs.amazon.com/sp-api/reference/getitemreviewtopics): child ASIN, parameters and topic objects.
- **S4** [SP-API policies](https://developer-docs.amazon.com/sp-api/docs/policies-and-agreements): AUP/DPP index; tool limitations restricted follow-up policy retrieval, so project permission is not established.
- **P1** [Portability overview](https://developer.amazon.com/docs/amazon-data-portability/overview): authorization and regional scope.
- **P2** [Available scopes: product reviews](https://developer.amazon.com/docs/amazon-data-portability/available-scopes.html#product-reviews): fields, Category-1 and required set.
- **P3** [Authorization workflow](https://developer.amazon.com/docs/amazon-data-portability/intro-workflow.html): individual LWA consent.
- **P4** [Transfer preferences](https://developer.amazon.com/docs/amazon-data-portability/user-transfer-preferences.html): scope and duration.
- **P5** [API reference](https://developer.amazon.com/docs/amazon-data-portability/api-reference.html): operations, pagination and time limits; its software license is not a review-content copyright grant.
- **P6** [List/download workflow](https://developer.amazon.com/docs/amazon-data-portability/call-list.html), [identity/security](https://developer.amazon.com/docs/amazon-data-portability/identity-and-security.html), [allowlisting](https://developer.amazon.com/docs/amazon-data-portability/portability-allowlist.html): asynchronous files and onboarding.
- **P7** [LWA Services Agreement: Portability API Schedule, sections 1–7](https://developer.amazon.com/support/legal/login-with-amazon): purpose, access, security, deletion and revocation.
- **P8** [Sandbox eligibility](https://developer.amazon.com/docs/amazon-data-portability/sandbox-testing.html): scope categories and account limits.
- **C1** [Creators introduction](https://affiliate-program.amazon.com/creatorsapi/docs/en-us/introduction), [cURL examples](https://affiliate-program.amazon.com/creatorsapi/docs/en-us/get-started/using-curl): catalog and authentication.
- **C2** [PA-API deprecation](https://affiliate-program.amazon.com/creatorsapi/docs/en-us/paapiv5-deprecation).
- **C3** [Creators license pointer](https://affiliate-program.amazon.com/creatorsapi/docs/en-us/license-agreement).
- **C4** [Associates policies: IP License sections 2(e), (h)](https://affiliate-program.amazon.com/help/operating/policies): analysis, models and caching.
- **V1** [Bright Data review product](https://brightdata.com/products/datasets/amazon/reviews).
- **V2** [Bright Data license](https://brightdata.com/license): service terms and third-party rights, not project content-rights proof.
- **V3** [Rainforest parameters](https://docs.trajectdata.com/rainforestapi/product-data-api/parameters/common), [product updates](https://docs.trajectdata.com/rainforestapi/product-updates): current service scope incompletely verified as described above.
- **V4** [AWS Data Exchange FAQ](https://aws.amazon.com/data-exchange/faqs/): provider declarations and subscription agreements.
- **V5** [Bazaarvoice API terms](https://www.bazaarvoice.com/legal/terms-of-use/api/).
- **V6** [Bazaarvoice syndicated content](https://developers.bazaarvoice.com/v1.0-ConversationsAPI/docs/syndicated-content).
- **W1** [Amazon Conditions of Use](https://digprjsurvey.amazon.com/csad/help/node/GLSBYFE9MGKKQXXM): Amazon-hosted help mirror. Historical browser/robots evidence: [direction record](../research/amazon_direction_update.md). Page access was not re-tested.
- **R1** [Amazon EU DSA researcher access](https://trustworthyshopping.aboutamazon.com/digital-services-act-dsa-amazon-eu-store-data-access-for-researchers).

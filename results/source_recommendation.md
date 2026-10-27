# Source Recommendation — Phase I

**Assessment date:** October 20, 2026

## Selection

**Use Steam Reviews for the initial technical pilot, with GitHub Issues as the quota-dependent backup.** Retain Amazon's strategic consumer-retail role, but exclude broad raw-review integration under current access conditions. Hacker News remains a comparison source rather than the selected input.

The assessment and focused collection validation are complete. This recommendation assumes game or digital-product feedback is acceptable for validating the ingestion approach. A physical-retail requirement would require a domain-appropriate source rather than treating Steam as a substitute.

## Technical rationale

| Source | Evidence and practical value | Selection rationale |
| --- | --- | --- |
| Steam Reviews | Structured review targets, recommendation flags, pagination and update timestamps; 20/20 successful requests including the negative supplement | Best fit for a repeatable review-ingestion pilot, with short-text filtering and cross-query deduplication |
| GitHub Issues | Useful software pain points and issue/comment relationships; 8/9 successful requests | Strong backup for software feedback, with PR exclusion, support-content filtering and quota management |
| Hacker News | Public discussions and comment relationships; 19/19 successful requests | Greater topic/context selection effort than a product-review source |
| Amazon | Broad consumer-retail relevance; assessed access routes do not establish the required multi-consumer raw-review stream | Strategic retail relevance without a currently suitable ingestion route |

The experiments recorded **47 successful API requests out of 48**. Steam consistently retrieved 27 distinct baseline reviews across three runs, including a follow-up approximately 16 minutes after the initial test. A separate two-request check retrieved four additional reviews with voted_up=false, validating negative-recommendation retrieval and processing.

Content review identified useful feedback in 10 of 27 Steam reviews, 7 of 11 GitHub records, and 3 of 9 Hacker News records. The review methodology and evaluation criteria are documented in the [Feasibility Comparison](feasibility_comparison.md).

GitHub's higher useful-content ratio does not make issue/support workflows interchangeable with product reviews. Steam combines an explicit product target and structured recommendation metadata with simpler collection and filtering requirements.

## Amazon conclusion

The Amazon feasibility assessment is complete. Customer Feedback SP-API supplies aggregate topics, trends and selected excerpts. Data Portability supplies individually authorizing customers' own review data, not arbitrary ASIN-wide coverage. Affiliate catalog access does not establish a suitable full-review stream; supplier claims do not establish project-specific rights and coverage.

No currently verified route supports broad, repeatable raw-review acquisition for this project. Amazon therefore remains a strategic consumer-retail candidate rather than an immediate ingestion source.

The [Amazon Acquisition Options](amazon_acquisition_options.md) contains the route evidence and references. The [Amazon Engineering Decision](amazon_decision.md) defines the conditions for reconsideration: a verified supply agreement, an accepted aggregate-insights product, or an appropriate consent-based product. Account-based or licensed access would represent a trade-off against the Project Brief's preference for ungated access.

## Implementation Considerations

The Steam pilot provides a foundation for a modular ingestion pipeline built around review retrieval, normalization, quality filtering, and deduplication, with update timestamps supporting future incremental ingestion.

The next engineering stage can extend the validated collectors with persistent storage, scheduled execution, and monitoring. Review IDs and update timestamps provide a basis for record tracking, while text-quality filtering can reduce low-information content.

Production integration will require confirmation of applicable data-use conditions and additional reliability validation. Supporting execution records and test results are available through the [Evidence Index](README.md).

# Source Recommendation — Phase I

**Assessment date: October 27, 2026 PDT.**

## Recommendation

**Recommend Apple App Store reviews as the primary candidate for the next broad-domain ingestion pilot, Google Play reviews as the backup, and Steam as the technical regression baseline.** The intended scope is consumer experiences across app-enabled products and services.

The focused feasibility comparison is complete. This recommendation identifies the preferred source for the next pilot; production integration still requires an applicable data-use basis and sustained online-update validation.

## Supporting Evidence

The [detailed comparison](mobile_review_comparison.md) used the same eight app products on Apple and Google: two each in productivity, education, shopping and transportation. Five first-page reviews per app produced equal 40-record primary samples. All 32 bounded requests succeeded, including four pagination and four short repeat checks per store.

| Dimension | Apple App Store | Google Play | Steam baseline |
| --- | --- | --- | --- |
| Executed coverage | 8 apps / 4 categories | Same 8 apps / 4 categories | 2 games |
| Useful experience content | 28/40 (70.0%) | 17/40 (42.5%) | Historical 10/27 (37.0%) |
| Median body length | 122 characters | 41.5 characters | 30 characters |
| Pagination | Four app checks, no sampled overlap | Four app checks, no sampled overlap | Historical cursor pagination verified |
| Repeatability | Same sampled IDs and body hashes after approximately four minutes | Same sampled IDs and body hashes after approximately four minutes | Historical repeated retrieval verified |
| Main constraint | RSS behavior varies by format and execution | Undocumented web transport and schema | Gaming-specific content |

Content review used the established concrete-experience rubric on actual text, with ratings hidden in the new inspection display. Judgments are AI-assisted and limited to complete short bodies or the first 500 normalized characters. These are descriptive sample results. Steam's older, positive-only quality baseline and different query design prevent a controlled platform-wide ranking; its four targeted negative records were outside semantic review.

## Selection Rationale

Apple combines demonstrated category breadth, structured ratings and review fields, successful bounded collection, and more detailed experience content in the sampled windows. Its advantage was strongest in productivity feedback; several apps had equal useful counts across stores. The recommendation therefore reflects the combined evidence, rather than the 70.0% figure alone.

Google remains a credible backup because the same category frame, pagination and repeated reads succeeded. Its sample contained more generic reactions, and reliance on an undocumented web interface increases maintenance risk. The official developer API's application-owner authorization is separate from this tested web route.

Steam remains valuable for regression and controlled ingestion exercises through its documented interface. Its two-game frame is narrower than the project's intended consumer-experience scope. GitHub Issues retains a quota-dependent role for software-feedback work, distinct from the app-review backup role assigned to Google.

Both app stores contain feedback about delivery, payments, support and drivers as well as app functionality. Downstream labels should preserve that distinction. Amazon Shopping app reviews do not provide ASIN-level Amazon product-review coverage.

## Production Entry Conditions

The short repeats showed no newly visible IDs or body edits. Sustained online ingestion requires day-scale arrival observations, adequate overlap between collection windows, and edit/deletion handling. A static dataset would not meet that requirement.

Scheduled collection, historical data retention, and model-related use require appropriate permissions under the applicable data-use terms. The [acquisition assessment](mainstream_review_assessment.md) documents source conditions and commercial alternatives; successful requests or supplier credentials alone do not establish those rights. Apple RSS has no established general-purpose review API support guarantee, while Google's web interface adds schema risk.

Amazon's completed [engineering assessment](amazon_decision.md) remains unchanged. Earlier retail and social-source findings remain available in the [Evidence Index](README.md).

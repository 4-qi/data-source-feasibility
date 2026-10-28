# Results and Evidence Index

The current recommendation is **Apple App Store as the primary candidate, Google Play as the backup, and Steam as the technical regression baseline**. The focused comparison is complete; production use requires appropriate data-use permissions and further validation of ongoing updates.

## Current Reports

| Report | Description |
| --- | --- |
| [Source Recommendation](source_recommendation.md) | Decision, business assumptions, rationale, and implementation conditions |
| [Mobile App Reviews versus Steam](mobile_review_comparison.md) | Sampling, content quality, category variation, and collection behavior |

## Focused Mobile Comparison — October 27, 2026

| Artifact | Description |
| --- | --- |
| [collection.json](mobile_quality/collection.json) | 32 successful requests: 16 Apple and 16 Google, including pagination and short repeats |
| [comparison_summary.json](mobile_quality/comparison_summary.json) | Recomputed metrics, per-app/category results, repeat checks, and historical Steam comparator |
| [content_review.json](mobile_quality/content_review.json) | 85 distinct AI-assisted text assessments with abstract reasons and topics; no review bodies |
| [verification.json](mobile_quality/verification.json) | Recorded tests, metric checks, link validation, and historical preservation for that execution |
| [App sampling manifest](mainstream/app_sample_manifest.json) | Shared eight-product, four-category frame and verified store identifiers |

The primary content-quality comparison covers **40 Apple and 40 Google records**. The recovered earlier Apple cohort overlaps 35 primary Apple records and contributes five additional Todoist page-2 reviews, resulting in 85 distinct annotated records overall.

Useful counts are Apple 28/40 and Google 17/40. The approximately four-minute repeats returned unchanged IDs and body hashes, establishing short-interval repeatability rather than sustained freshness. The detailed report explains the rubric and sampling limits.

## Earlier Mobile and Route Studies — October 27, 2026

These artifacts preserve earlier executions. Their seven-app Apple frame, single-app Google probe and temporary missing-entry observations do not describe the final comparison.

| Study | Report and evidence |
| --- | --- |
| Initial access screen | [Screening summary](mainstream/assessment_summary.json), [CFPB 403](mainstream/cfpb_access_20261028T003324477168Z.json), and [verification](mainstream/verification.json) |
| Apple RSS and supplier routes | [Mainstream Review Source Assessment](mainstream_review_assessment.md), [vendor matrix](mainstream/vendor_route_matrix.json), [supplier checks](mainstream/vendor_access_checks.json), and [verification](mainstream/mobile_follow_up_verification.json) |
| RSS format and date diagnostics | [JSON sample](mainstream/apple_rss_access.json), [missing-entry schema](mainstream/apple_empty_feed_diagnostic.json), [date/format checks](mainstream/apple_online_readiness.json), and [XML sample](mainstream/apple_xml_review_sample.json) |
| Platform-route reassessment | [Source Route Reassessment](source_route_reassessment.md), [HTTP checks](route_recheck/source_route_recheck.json), and [verification](route_recheck/verification.json) |
| Targeted route evidence | [Walmart redirect](route_recheck/walmart_redirect_check.json), [Google initial HTML](route_recheck/google_play_embedded_recheck.json), [Google web reviews](route_recheck/google_play_review_rpc_recheck.json), and [Bluesky live stream](route_recheck/bluesky_jetstream_recheck.json) |

The earlier RSS study recorded 23 successful diagnostic GETs and 40 distinct parsed records from seven apps. The subsequent route study demonstrated Google web-review pagination, Bluesky live events and Mastodon hashtag pagination. Those request and record counts remain separate from the final 32-request mobile comparison.

## Original Baseline — October 20, 2026

| Artifact | Description |
| --- | --- |
| [Initial Feasibility Comparison](feasibility_comparison.md) | Steam, GitHub Issues, and Hacker News collection and quality findings |
| [collection_summary.json](collection_summary.json) | Original three-source aggregate through the negative supplement: 47/48 successful requests; excludes later mobile/route studies |
| [experiment_20261020T074829Z.json](experiment_20261020T074829Z.json) | Preserved original two-round experiment: 39/39 successful requests |
| [follow_up_summary.json](follow_up_summary.json) | Steam repeat and GitHub quota denial; failed overlap comparison is null |
| [Pre-supplement aggregate](collection_summary_before_negative_validation.json) | Preserved 45/46 result before negative-review validation |
| [Negative execution](negative_validation/steam_negative_20261020T082124904884Z.json) | Two requests and four distinct negative recommendation records |
| [Negative coverage](negative_validation/coverage_summary.json) | Label types, deduplication, and overlap checks |
| [Baseline content review](content_review.json) | Fixed AI-assisted assessment of 47 distinct records, excluding targeted negatives |
| [Initial validation](validation_summary.json), [follow-up validation](validation_follow_up.json), [negative validation](negative_validation/validation_summary.json) | Test provenance for their respective code states |

The `runs/` directory retains individual executions. Steam's three baseline runs contain the same 27 IDs; the negative supplement adds four distinct IDs. Neither repeated retrieval nor deliberate negative filtering estimates the platform's natural sentiment distribution.

## Amazon Assessment

[Amazon Acquisition Options](amazon_acquisition_options.md) and the [Amazon Engineering Decision](amazon_decision.md) contain the completed retail-source assessment. The [robots metadata check](amazon_preflight_20261020T080149Z.json) is separate from collection totals and establishes neither review access nor permission.

## Evidence Conventions

Saved results retain metrics, fingerprints, field presence and abstract annotations rather than source bodies or account identifiers. See [Evidence and Methodology](../research/current_evidence.md) for interpretation and privacy controls.

The offline test suite contains 57 tests. Execution-specific verification results are preserved alongside their corresponding evidence.
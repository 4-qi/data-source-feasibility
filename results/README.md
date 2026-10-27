# Results and Evidence Index

Recorded collection and source-assessment evidence dates to October 20, 2026 PDT.

## Current analysis

The [Source Recommendation](source_recommendation.md) presents the completed selection. The [Feasibility Comparison](feasibility_comparison.md) interprets the experiments; [Amazon Acquisition Options](amazon_acquisition_options.md) and the [Amazon Engineering Decision](amazon_decision.md) document the retail-source assessment.

## Execution evidence

| Artifact | Role and interpretation |
| --- | --- |
| [collection_summary.json](collection_summary.json) | Latest aggregate: original experiment, follow-up attempts and separate negative supplement; 47/48 successful API requests |
| [experiment_20261020T074829Z.json](experiment_20261020T074829Z.json) | Preserved original two-round experiment: 39/39 successful requests |
| [follow_up_summary.json](follow_up_summary.json) | Longer-interval Steam success and GitHub quota denial; failed overlap comparison remains null |
| [collection_summary_before_negative_validation.json](collection_summary_before_negative_validation.json) | Aggregate preserved before the negative supplement: 45/46 successful requests |
| [negative validation execution](negative_validation/steam_negative_20261020T082124904884Z.json) | Two requests, four distinct negative recommendation records |
| [negative coverage summary](negative_validation/coverage_summary.json) | Negative-label types, deduplication and baseline overlap |
| [content_review.json](content_review.json) | Fixed AI-assisted assessment of 47 distinct baseline records; excludes the negative supplement |
| [amazon_preflight_20261020T080149Z.json](amazon_preflight_20261020T080149Z.json) | One robots metadata request; not review collection or permission evidence |

The `runs/` directory retains individual baseline and follow-up execution files. Repeated Steam results contain the same 27 IDs; summing returned records across runs would overstate independent review volume. The four separately filtered negative reviews do not estimate the platform's natural sentiment distribution.

## Recorded validation summaries

[validation_summary.json](validation_summary.json), [validation_follow_up.json](validation_follow_up.json) and [negative validation summary](negative_validation/validation_summary.json) document test results across the initial experiment, follow-up checks, and negative-review validation.

Default result files contain metrics and fingerprints rather than source review bodies or account identifiers. See [Evidence and Methodology](../research/current_evidence.md) for provenance, content-review methods and evidence labels.

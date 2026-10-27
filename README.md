# Data Source Feasibility — Phase I

## Project Overview

This project evaluates data sources for a sentiment analysis pipeline through executable collection proofs of concept, automated tests and recorded API experiments. It implements collectors for Steam Reviews, GitHub Issues and Hacker News, and assesses Amazon acquisition methods against consumer-retail review requirements.

The feasibility study and focused validation are complete. The deliverables establish a source-selection recommendation and reproducible collection methods; production deployment is a separate activity.

## Source Selection

| Source | Selection |
| --- | --- |
| **Steam Reviews** | Recommended initial technical pilot: structured product feedback, recommendation metadata and validated pagination. |
| **GitHub Issues** | Backup for software feedback, subject to API quota constraints. |
| **Amazon** | Preferred strategic source for consumer-retail applications; broad raw-review acquisition is not currently established. |
| **Hacker News** | Evaluated comparison source, not selected because of topic-selection and context requirements. |

The Amazon assessment is complete. Customer Feedback SP-API provides aggregate insights and selected excerpts; Data Portability provides individually authorizing customers' own reviews, not arbitrary ASIN-wide access. No currently verified route meets the broad raw-review requirements, so integration is not recommended under current access conditions. This does not rule out a future suitable acquisition arrangement. Detailed conditions are in the Amazon reports below.

Steam's pilot recommendation assumes game or digital-product feedback is suitable for validating the ingestion approach; it does not replace a consumer-retail requirement.

## Validation Results

| Source / phase | Successful API requests | Distinct records | Result |
| --- | --- | --- | --- |
| Steam baseline and repeats | 18/18 | 27 distinct reviews per run | Consistent IDs and metadata across three runs |
| Steam negative supplement | 2/2 | Four distinct reviews | All four had negative recommendation flags |
| GitHub Issues and comments | 8/9 | 11 records across two successful runs | One quota-related HTTP 403 |
| Hacker News | 19/19 | Nine records across two runs | Three stories and six direct comments |
| **Total** | **47/48** | Deduplicated counts shown above | Amazon robots metadata is counted separately |

Steam collection succeeded across three runs, including a follow-up approximately 16 minutes after the initial test. Pagination and deduplication were validated within the sampled queries.

Content review of 47 distinct baseline records identified useful feedback in 10 of 27 Steam reviews, 7 of 11 GitHub records and 3 of 9 Hacker News records. The [Feasibility Comparison](results/feasibility_comparison.md) describes the review methodology and sampling context.

The automated test suite contains **33 passing tests**.

## Documentation

| Document | Description |
| --- | --- |
| [Source Recommendation](results/source_recommendation.md) | Source selection, technical rationale, and implementation considerations |
| [Feasibility Comparison](results/feasibility_comparison.md) | Collection results, data quality, and technical trade-offs |
| [Amazon Acquisition Options](results/amazon_acquisition_options.md) | Available acquisition methods, requirements, and limitations |
| [Amazon Engineering Decision](results/amazon_decision.md) | Feasibility conclusions, implementation constraints, and decision criteria |
| [Evidence Index](results/README.md) | Execution metrics, validation results, and supporting evidence |
| [Research Guide](research/README.md) | Research methodology, source documentation, and evidence provenance |

## Project Structure

```text
data-source-feasibility/
├── README.md
├── pyproject.toml
├── src/feasibility/          # Collectors, normalization and reporting
├── tests/                   # Automated tests
├── research/                # Methodology, references and provenance
└── results/                 # Reports, metrics and execution evidence
    ├── runs/
    └── negative_validation/
```

## Getting Started

**Requirements:** Python 3.10+

```sh
python -m venv .venv
. .venv/bin/activate
python -m pip install -e '.[test]'
```

On Windows PowerShell, activate with `.venv\Scripts\Activate.ps1`.

Run the automated tests:

```sh
python -m pytest -q
```

The 33 tests cover normalization, pagination, deduplication, parent relationships, API responses, negative recommendation flags and error handling.

## Running the Collectors

Run individual source probes:

```sh
python -m feasibility.cli probe steam --max-records 32 --max-requests 6
python -m feasibility.cli probe github --max-records 24 --max-requests 4
python -m feasibility.cli probe hackernews --max-records 9 --max-requests 10
```

Run the two-round validation experiment:

```sh
python -m feasibility.cli experiment
```

Run the targeted Steam negative-review validation:

```sh
python -m feasibility.negative_validation
```

These commands make live API requests. Collectors use bounded requests, pagination, deduplication and error handling. Collection runs save timestamped execution summaries under 'results/runs/'. The full experiment also updates 'results/collection_summary.json' and preserves a timestamped experiment snapshot. Negative validation writes separately under `results/negative_validation/`.

## Results and Outputs

The `results/` directory contains collection summaries, per-run execution evidence, validation results, data-quality assessments, the source comparison and recommendation, and the Amazon acquisition assessment.

The repository contains code, automated tests, technical documentation and sanitized execution results: metadata, metrics and record fingerprints. Internal project documents, credentials, raw third-party content, account identifiers, local research archives and local manifests remain excluded from Git tracking. See the [Results and Evidence Index](results/README.md) for the artifact list.

# Data Source Feasibility — Phase I

This project evaluates online text sources for a sentiment analysis pipeline through bounded collection experiments, content review and offline tests. The feasibility study and focused source comparison are complete.

**Current recommendation: Apple App Store as the primary source candidate, Google Play as the backup, and Steam as the technical regression baseline.** The intended scope is consumer experiences across app-enabled products and services. Production integration requires suitable data-use conditions and sustained online-update validation.

## Findings

| Source | Executed coverage | Useful experience content | Recommended role |
| --- | --- | --- | --- |
| Apple App Store | 8 apps across 4 categories | 28/40 (70.0%) | Primary candidate; detailed experience text in this sample |
| Google Play | Same 8 apps and 4 categories | 17/40 (42.5%) | Backup; undocumented web transport adds maintenance risk |
| Steam Reviews | Historical sample from 2 games | 10/27 (37.0%) | Documented API baseline with gaming-specific coverage |

Apple and Google each completed 16/16 requests, including four pagination and four short repeat checks. Their quality samples used five first-page reviews per app, with ratings hidden during AI-assisted text inspection. Steam's figures come from an earlier sampling design; these percentages are descriptive sample results, not estimates of platform-wide superiority.

Further validation of ongoing review updates, edit/deletion handling, and data-use permissions is required before production integration. Amazon remains a strategic retail candidate with a completed access assessment; broad raw-review ingestion is not recommended under current access conditions.

## Documentation

Start with the recommendation, then use the detailed comparison and evidence index as needed.

| Document | Description |
| --- | --- |
| [Source Recommendation](results/source_recommendation.md) | Source selection, technical rationale, and implementation conditions |
| [Mobile App Reviews versus Steam](results/mobile_review_comparison.md) | Matched app sampling, content quality, coverage, and collection trade-offs |
| [Evidence Index](results/README.md) | Execution artifacts, metrics, annotations, and validation records |
| [Research Guide](research/README.md) | Methodology, references, and historical context |
| [Initial Feasibility Comparison](results/feasibility_comparison.md) | Preserved Steam, GitHub Issues, and Hacker News baseline |
| [Amazon Acquisition Options](results/amazon_acquisition_options.md) | Acquisition methods, requirements, and limitations |
| [Amazon Engineering Decision](results/amazon_decision.md) | Completed feasibility conclusions and integration criteria |

## Project Structure

```text
data-source-feasibility/
├── src/feasibility/      # Baseline collectors, normalization and reporting
├── probes/              # Bounded access and mobile-comparison diagnostics
├── tests/               # Offline parsing, privacy and collection-control checks
├── research/            # Methodology, references and historical context
└── results/             # Reports and preserved execution evidence
    ├── mobile_quality/  # Current comparison and abstract content annotations
    ├── mainstream/      # Earlier mobile access and supplier assessment
    ├── route_recheck/   # Earlier platform-specific access checks
    ├── runs/            # Original collection runs
    └── negative_validation/
```

## Setup and Offline Tests

Python 3.10+ is required.

```sh
python -m venv .venv
. .venv/bin/activate
python -m pip install -e '.[test]'
python -m pytest -q
```

On Windows PowerShell, activate with `.venv\Scripts\Activate.ps1`.

The maintained suite has **57 passing tests**, covering normalization, pagination, deduplication, response parsing, negative recommendation flags, privacy and request budgets. Offline tests and live collection results are separate forms of evidence.

## Collection Tools

Inspect the CLI without making requests:

```sh
python -m feasibility.cli --help
python probes/mobile_quality.py --help
```

The baseline CLI supports bounded probes for `steam`, `github` and `hackernews`, plus the original two-round experiment. `python -m feasibility.negative_validation` performs the targeted Steam negative-review check. The experiment updates `results/collection_summary.json` and saves a separate timestamped execution snapshot.

The [mobile comparison report](results/mobile_review_comparison.md#reproduction) documents the two-phase Apple/Google probe. Live collection commands contact external services and write evidence. Use a fresh output directory; temporary inspection text must stay outside the repository.

The repository contains code, tests, technical documentation and sanitized execution results. Internal project documents, credentials, raw third-party content, account identifiers, private local manifests and research archives remain excluded from Git tracking.

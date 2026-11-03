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
| [Pre-Live Engineering Baseline](docs/PRE_LIVE_ENGINEERING_BASELINE.md) | Local milestone review, data exclusions, preservation and clean-export validation |
| [Apple Ingestion Design](docs/APPLE_INGESTION_SYSTEM_DESIGN.md) | Approved pilot architecture, seven-table schema and validation protocols |
| [Phase A Delivery](docs/PHASE_A_DELIVERY.md) | Contracts/database scope, execution-session ownership and acceptance status |
| [Implementation through Phase D](docs/APPLE_INGESTION_IMPLEMENTATION_SUMMARY.md) | Phased implementation, measured acceptance, architecture review and limits |
| [Phase C Architecture Review](docs/PHASE_C_ARCHITECTURE_REVIEW.md) | Concrete consistency findings, fixes and regression evidence |
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
├── migrations/          # Apple pilot PostgreSQL schema migrations
├── docs/                # Approved design and phased engineering delivery
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

Python 3.10+ is required; the shared project Conda environment uses Python 3.12.

```sh
conda env create -f environment.yml
conda activate data-source-feasibility
python -m pip install -c requirements/project-test.lock -e '.[test,apple-ingestion]'
python -m pytest -q
```

Reuse this project environment across implementation phases. If it already exists, activate it instead of recreating it. A standard Python venv is an alternative for installations without Conda.

The original feasibility suite recorded **57 passing tests**, covering normalization, pagination, deduplication, response parsing, negative recommendation flags, privacy and request budgets. Phase A adds separate contract and PostgreSQL checks. Offline tests and live collection results are separate forms of evidence.

## Apple Pilot — Phase A

Phase A implements data contracts, seven PostgreSQL tables, Alembic migrations and database integrity tests. It adds no RSS collection path. The existing eight US applications seed disabled targets; parser/reconciliation/controller work belongs to later phases.

In the project Conda environment, install/update the database/test dependencies:

```sh
python -m pip install -c requirements/project-test.lock -e '.[test,apple-ingestion]'
python -m pytest -q
```

The constraints file records the tested dependency set. PostgreSQL tests require an explicitly disposable database and are skipped by ordinary offline runs without it. On Linux with PostgreSQL 16 binaries installed, the isolated test runner creates a temporary cluster with TCP disabled and removes it afterward:

```sh
bash scripts/test_apple_ingestion_postgres.sh -q
```

Set `APPLE_TEST_PG_BIN` if the PostgreSQL binaries are elsewhere, or `APPLE_TEST_PYTHON` to select the environment's Python. See the [database validation record](docs/PHASE_A_DATABASE_VALIDATION.md) for actual test evidence and migration/permission setup. These checks use synthetic records and do not contact Apple.

## Apple Pilot — Phases B through D

The approved seven-table/full-text design now has strict JSON/Atom parsing,
deterministic version reconciliation, bounded request control, comparison
references independent of coverage sufficiency, and session/diagnostic recovery.
Phase D adds safe reports, a synthetic seven-day rehearsal and private human
assessment materials. Actual human assessment remains pending. Live mode remains
closed unless a confirmed, enabled project policy and fresh deployment
preflight both pass. Routine runs reuse that project policy without per-run
approval files or one-use receipts. Phase E preparation is complete; real Apple requests and
Phase F remain unauthorized.

Run the complete suite with a disposable PostgreSQL cluster:

```sh
conda activate data-source-feasibility
bash scripts/test_apple_ingestion_postgres.sh --full-suite -q
```

The tests inject synthetic responses and block Python TCP connections. Read the
[implementation summary](docs/APPLE_INGESTION_IMPLEMENTATION_SUMMARY.md) for phase
results, rehearsal reproduction and A–D architectural limits. See the
[Phase E live-readiness report](docs/PHASE_E_LIVE_READINESS.md) for the controlled
live entry, deployment templates, offline integration results and concrete
blockers. A dedicated persistent WSL PostgreSQL instance has subsequently been deployed
and verified, including explicit long-term retention, actual account permissions
and isolated backup/restore. See the [local deployment report](docs/APPLE_INGESTION_LOCAL_DEPLOYMENT.md)
for operating commands and current blockers. All eight targets remain disabled;
no real Apple request or Phase F collection has occurred. The
[first smoke-test runbook](docs/APPLE_FIRST_LIVE_SMOKE_TEST.md) contains the
selected Todoist target, simplified project policy and unactivated seven-day plan.

## Collection Tools

Inspect the CLI without making requests:

```sh
python -m feasibility.cli --help
python probes/mobile_quality.py --help
```

The baseline CLI supports bounded probes for `steam`, `github` and `hackernews`, plus the original two-round experiment. `python -m feasibility.negative_validation` performs the targeted Steam negative-review check. The experiment updates `results/collection_summary.json` and saves a separate timestamped execution snapshot.

The [mobile comparison report](results/mobile_review_comparison.md#reproduction) documents the two-phase Apple/Google probe. Live collection commands contact external services and write evidence. Use a fresh output directory; temporary inspection text must stay outside the repository.

The repository contains code, tests, technical documentation and sanitized execution results. Internal project documents, credentials, raw third-party content, account identifiers, private local manifests and research archives remain excluded from Git tracking.

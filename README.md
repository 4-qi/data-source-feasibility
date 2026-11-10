# Data Source Feasibility and Apple Review Ingestion

This project evaluates online text sources for consumer-experience analysis and
implements a bounded Apple App Store review-ingestion pilot. The source study,
seven-day live pilot and 80-review human usefulness assessment are complete.

The initial source study identified Apple as the primary source candidate, Google Play
as the backup and Steam as the technical regression baseline. The completed
Apple pilot provides additional evidence about scheduled collection, storage,
coverage and content quality. Intended data use and long-term retention remain
unresolved project-level conditions.

## Final deliverables

Start with the pilot report, then consult the technical and quality reports.

| Document | Purpose |
| --- | --- |
| [Apple ingestion pilot report](docs/APPLE_INGESTION_PILOT_REPORT.md) | Objective, methodology, implementation, results, limitations and conclusion |
| [Technical validation](docs/APPLE_INGESTION_TECHNICAL_VALIDATION.md) | Seven-day per-app evidence, failures, coverage, database integrity and backup/restore proof |
| [Review quality assessment](docs/APPLE_REVIEW_QUALITY_ASSESSMENT.md) | Human U0–U3 results, sampling, validation and sample limitations |
| [Documentation guide](docs/README.md) | Design, implementation, deployment, operations and historical supporting records |

## Completed pilot findings

November 3–9, 2026 produced seven actual daily batches and 56 application runs:
52 successful, one partial and three failed. The pilot recorded 155 requests,
147 committed pages, 7,350 observations and 4,257 first-in-database reviews.
No changed versions were observed. Collection targets and Windows tasks were
disabled after the pilot.

The rating-hidden manual assessment classified **47/80 (58.75%) records as useful**.
The quality sample contains ten reviews per app. Duolingo had
four insufficient-overlap windows, and intermittent Atom responses caused
strict parsing failures. Full coverage and real source-edit behavior remain
unresolved.

## Earlier source-feasibility evidence

| Source | Historical sample | Useful content | Role in the source study |
| --- | --- | --- | --- |
| Apple App Store | 8 apps, 4 categories | 28/40 (70.0%) | Primary candidate |
| Google Play | Same app/category frame | 17/40 (42.5%) | Backup; undocumented transport |
| Steam Reviews | 2 games | 10/27 (37.0%) | Documented API baseline |

The initial source study used AI-assisted inspection; the pilot used manual
U0–U3 assessment. Their percentages are reported separately because the
samples and assessment methods differ. Source and project
decisions are documented in the
[source recommendation](results/source_recommendation.md),
[mobile comparison](results/mobile_review_comparison.md) and
[evidence index](results/README.md). The [research guide](research/README.md)
preserves the study's methodology and historical context. Amazon's separate
[access assessment](results/amazon_acquisition_options.md) and
[engineering decision](results/amazon_decision.md) remain available.

## Design and operation

The [system design](docs/APPLE_INGESTION_SYSTEM_DESIGN.md) defines seven core
tables, complete review versions and the approved reconciliation rules.
The [implementation summary](docs/APPLE_INGESTION_IMPLEMENTATION_SUMMARY.md)
preserves engineering delivery and historical test results.

The [deployment documentation](docs/APPLE_INGESTION_DEPLOYMENT.md)
describes PostgreSQL, private storage, roles and recovery.
The [operations documentation](docs/APPLE_INGESTION_OPERATIONS.md) describes
the completed pilot's Windows/WSL execution and disabled state. Final
retirement evidence is recorded in the
[technical validation](docs/APPLE_INGESTION_TECHNICAL_VALIDATION.md).
Access and retention questions remain in the
[project review memo](docs/archive/PHASE_E_ACCESS_RETENTION.md).
Historical Phase and daily reports are linked as audit records in the
[documentation guide](docs/README.md).

## Project structure

```text
data-source-feasibility/
├── src/feasibility/      # Collection, normalization and reporting
├── probes/              # Bounded feasibility diagnostics
├── migrations/          # Apple PostgreSQL schema migrations
├── docs/                # Final reports, design, operations and engineering history
├── tests/               # Offline and isolated PostgreSQL checks
├── research/            # Methodology and historical context
└── results/             # Preserved feasibility evidence and annotations
```

## Setup and offline validation

Python 3.10+ is required; the project Conda environment uses Python 3.12.

```sh
conda env create -f environment.yml
conda activate data-source-feasibility
python -m pip install -c requirements/project-test.lock -e '.[test,apple-ingestion]'
python -m pytest -q
```

Activate an existing project environment instead of recreating it. A Python
venv is an alternative. Ordinary tests skip database cases without an explicit
disposable PostgreSQL configuration. The Linux PostgreSQL 16 runner creates
and removes a temporary cluster with TCP disabled.

```sh
conda activate data-source-feasibility
bash scripts/test_apple_ingestion_postgres.sh --full-suite -q
```

Set APPLE_TEST_PG_BIN or APPLE_TEST_PYTHON to select local binaries.
The last complete diagnostics regression recorded **676 passing tests** before
commit 022c70b. This documentation cleanup does not claim a new test run.
See the [database validation record](docs/archive/PHASE_A_DATABASE_VALIDATION.md) and
[implementation summary](docs/APPLE_INGESTION_IMPLEMENTATION_SUMMARY.md)
for earlier checkpoints.

## Historical collection tools

Inspect command help without making requests.

```sh
python -m feasibility.cli --help
python probes/mobile_quality.py --help
```

The baseline CLI supports steam, github and hackernews probes and the original
two-round experiment. The
[mobile comparison reproduction record](results/mobile_review_comparison.md#reproduction)
describes its bounded Apple/Google study. Executing collection commands contacts
external services and writes evidence.

Repository reports contain sanitized execution metadata and aggregate results.
Private credentials, PostgreSQL contents, raw review text and human response
files stay outside tracked delivery files.

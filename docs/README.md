# Documentation guide

## Main documentation

| Document | Scope |
| --- | --- |
| [System design](APPLE_INGESTION_SYSTEM_DESIGN.md) | Seven-table architecture, full-text history and ingestion semantics |
| [Implementation summary](APPLE_INGESTION_IMPLEMENTATION_SUMMARY.md) | Components, engineering validation and implementation record |
| [Deployment](APPLE_INGESTION_DEPLOYMENT.md) | Persistent PostgreSQL, roles, storage and recovery |
| [Operations](APPLE_INGESTION_OPERATIONS.md) | Collection controls, execution environment and completed pilot state |
| [Pilot report](APPLE_INGESTION_PILOT_REPORT.md) | Objective, methodology, implementation, results and conclusion |
| [Technical validation](APPLE_INGESTION_TECHNICAL_VALIDATION.md) | Per-application results, anomalies, coverage, integrity and backup proof |
| [Review quality assessment](APPLE_REVIEW_QUALITY_ASSESSMENT.md) | Manual assessment method, results and sample limitations |

## Supporting records

The [archive index](archive/README.md) groups historical development records,
deployment and scheduler preparation, daily execution reports and aggregate
audit metadata. Their original filenames are preserved. Historical setup-time
states are distinct from the completed pilot state in the main documentation.

Full daily evidence, review-level human responses and PostgreSQL backups
remain in private project storage.

## Earlier research

- [Source-feasibility evidence index](../results/README.md)
- [Research guide](../research/README.md)
- [Mobile source comparison](../results/mobile_review_comparison.md)

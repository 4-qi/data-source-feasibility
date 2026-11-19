# Apple Review Retrieval Contract

The Python retrieval interface returns one current version per review from PostgreSQL. It also provides version history and a private CSV export with collection provenance.

## Storage and interface boundaries

PostgreSQL remains the source of truth. The retrieval layer projects stored fields and supplies collection provenance. Downstream processing consumes those records or a private exported dataset. A transformation can add fields such as `clean_body`, `language_code`, or a feature vector. It keeps the review and version keys, records its method and version, and leaves the original text and rating intact.

The interface uses SQLAlchemy and psycopg for local batch analysis and Pandas workflows.

## Existing schema and query capabilities

| Relation | Retrieval role |
| --- | --- |
| `application` | Resolve the app by `(source, source_application_id)`. |
| `review` | Stable identity within an app, current version pointer, first and last observation times. |
| `review_version` | Stored title, body, rating, app version, nullable source update time, version sequence, fingerprints and detecting run. |
| `review_observation` | One row per run and review, including accepted observed version, first page and position, occurrence and conflict counts. |
| `collection_run` | Run, batch, target and execution status for provenance. |
| `collection_target` | Storefront and sort order for the detecting run. |
| `fetch_attempt` | Request-level audit detail, available through the existing run reporting path. |

Existing run and batch reports expose aggregate evidence. Assessment queries serve a separate cutoff-bound sampling contract. The retrieval queries use the existing keys for app resolution, review and version lookup, and observation history.

## Python API

```python
iter_current_reviews(
    connection,
    *,
    source_application_id: str,
    time_field: Literal["first_observed_at", "source_updated_at"] = "first_observed_at",
    start: datetime | None = None,
    end: datetime | None = None,
    ratings: Collection[int] | None = None,
    batch_size: int = 1000,
) -> Iterator[CurrentReview]

list_review_versions(
    connection, *, source_application_id: str, source_review_id: str
) -> list[ReviewVersionRecord]
```

Import these functions from `feasibility.apple_ingestion.retrieval`. The caller supplies one explicit database connection using the reporting role. Source is fixed to `apple_app_store` in v1. App IDs are required strings matched exactly. The API raises an explicit application-not-found error for an unknown app and yields zero rows when a known app has no matches. One call queries one database. The original pilot and Duolingo experiment are distinct datasets with potentially overlapping source IDs and independently assigned internal IDs.

`ratings=None` includes every rating. Otherwise pass a nonempty set or collection of integers 1–5 and match any listed value. Reject booleans and out-of-range values. `batch_size` is a positive fetch-buffer size, with no implicit row limit. Results are ordered by internal review ID ascending. Consume the iterator within its open transaction. Read-only REPEATABLE READ is the recommended transaction for exports and for related queries that must see one snapshot. The caller owns transaction lifetime.

Select the version using `review.current_version_id` with review and app ownership guards. Apply rating and version-time filters to that selected version. A matching older rating cannot admit a review whose current rating fails the filter. Observations never select the current version. History is an explicit query ordered by version number ascending, with the same stored fields and detection provenance plus `is_current` derived from the pointer. An absent review yields an empty history for a known app. The current row contains no embedded history.

## Timestamp rules

| Field | Meaning | Filtering |
| --- | --- | --- |
| `first_observed_at` | First system observation of this review in the queried database. | Default time axis. |
| `source_updated_at` | Source-reported update timestamp on the selected version, when captured. | Explicit alternative. Nulls are excluded only when a bound is supplied for this field. |
| `source_created_at` | Source publication or creation time. | Missing from the current schema and ingestion contract. Reject this axis and omit it from the v1 dataset. |
| `last_observed_at` | Latest observation of the review identity in the queried database. | Returned for provenance. |
| `version_first_observed_at` | Time the selected version was first recorded by the system. | Returned for provenance. |

Filters combine with AND. Bounds are timezone-aware instants normalized to UTC. A lower bound is inclusive and an upper bound is exclusive. Each bound can be omitted, and omitting both returns all times. Reject naive datetimes and empty or reversed ranges. A time filter selects the current snapshot by the chosen field. Historical point-in-time reconstruction is outside this API. Group results by first observation time to analyze when reviews entered the dataset. Publication trends require a verified source creation timestamp.

## Dataset row and provenance

The row key is `review_id` within the explicitly selected dataset. The stable source key is `(source, source_application_id, source_review_id)`. The exporter verifies the database name and records a caller-supplied dataset label in the manifest.

| Object | Fields |
| --- | --- |
| Identity | `source`, `source_application_id`, `source_review_id`, `review_id` |
| Stored current version | `version_id`, `version_number`, `title` (nullable), `body`, `rating`, `application_version` (nullable), `source_updated_at` (nullable) |
| Provenance | `first_observed_at`, `last_observed_at`, `version_first_observed_at`, `detecting_run_id`, `detecting_batch_id`, `detecting_run_status`, `storefront`, `sort_by`, `observation_count`, `conflict_occurrence_count` |

The detecting run is the run that created the selected version. It can differ from the run that most recently observed the review. Include committed rows according to the pointer even when the detecting run later ended partial or interrupted. Its status remains visible. Observation counts cover the review's full history in the database regardless of query bounds. Count observation rows once per run, and sum stored conflict occurrences separately. Repeated entries within a run do not increase the observation-row count. Additional page and request provenance can be inspected with the detecting run identifier.

### Example query

This SQLAlchemy-style template illustrates the default first-observed filter. Build only the predicates requested by the caller, bind all values, and select the time column from the two supported names. The lateral aggregate contributes exactly one result per selected review.

```sql
SELECT a.source, a.source_application_id, r.source_review_id, r.id AS review_id,
       v.id AS version_id, v.version_number, v.title, v.body, v.rating,
       v.application_version, v.source_updated_at,
       r.first_observed_at, r.last_observed_at,
       v.first_observed_at AS version_first_observed_at,
       cr.id AS detecting_run_id, cr.batch_id AS detecting_batch_id,
       cr.execution_status AS detecting_run_status, ct.storefront, ct.sort_by,
       obs.observation_count, obs.conflict_occurrence_count
FROM application AS a
JOIN review AS r ON r.application_id = a.id
JOIN review_version AS v
  ON v.id = r.current_version_id AND v.review_id = r.id
 AND v.application_id = a.id
JOIN collection_run AS cr ON cr.id = v.detecting_run_id AND cr.application_id = a.id
JOIN collection_target AS ct ON ct.id = cr.target_id AND ct.application_id = a.id
CROSS JOIN LATERAL (
    SELECT count(*) AS observation_count,
           coalesce(sum(o.conflict_count), 0) AS conflict_occurrence_count
    FROM review_observation AS o
    WHERE o.review_id = r.id AND o.application_id = a.id
) AS obs
WHERE a.source = 'apple_app_store'
  AND a.source_application_id = :app_id
  AND r.first_observed_at >= :start
  AND r.first_observed_at < :end
  AND v.rating = :rating
ORDER BY r.id;
```

## Export and downstream processing

CSV is the supported export format. Use UTF-8, a stable header and flattened provenance columns with the names above. Preserve source IDs as strings, timestamps as UTC ISO 8601, UUIDs as strings and numeric fields as integers. Define CSV nulls as the reserved literal `\N`, escaping any non-null string beginning with a backslash by adding one backslash. CSV readers reverse that rule after standard CSV unquoting, which preserves the distinction between null and empty text. Quote embedded commas, quotes and newlines using standard CSV rules.

Parquet is outside the current implementation. The CSV exporter writes a sidecar manifest with contract version, dataset label, normalized filters, export time and row count. Treat a directory as complete only when its manifest exists. Write only to an explicit private destination. Logs and the manifest carry no review text or connection secrets. Processing outputs retain source keys and the exact version reference used.

## Acceptance criteria

1. Compare the ordered API result to a reference SELECT in a single read-only snapshot. Check counts, IDs, full stored fields and provenance. Test multiple observations and within-run duplicate occurrences.
2. Exercise application isolation, unknown app versus zero matches, timezone offsets, inclusive/exclusive endpoints, null source times and invalid inputs.
3. Seed a rating-only version change, add later observations, and prove the current query returns one row with the pointed-to version and rating. A filter matching only the old rating must exclude it. History must return both versions with correct detecting-run links. Verify the same contract against both recorded Duolingo rating changes using the isolated experiment database and emit private-data-free validation results. [Experiment results](APPLE_COVERAGE_EXPERIMENT_RESULTS.md)
4. Verify that an observation from a partially completed run can contribute provenance for a committed review, and that observation conflict counts are reported independently from review-row uniqueness.
5. Compare exported and in-memory rows. Round-trip nulls, empty strings, leading backslashes, multiline Unicode, textual IDs and UTC timestamps. If Parquet is delivered, verify equality across both formats after decoding.
6. Verify query execution under the SELECT-only role, stable results across fetch batch sizes and detached processing that leaves source rows untouched. Collect representative query plans before deciding whether any additional index is needed.

## Select a database and retrieve reviews

Set the reporting URL in the environment variable named by the deployment
configuration. Use a private environment loader and choose one database per
connection. The retained pilot is `apple_ingestion`. The completed Duolingo
series is `apple_coverage_main_20261113_2100`. Both can contain the same app ID.
Use the report login for the selected database and avoid configuring multiple
dataset URLs in the same execution environment.

```python
from datetime import datetime, timezone
from os import environ

from sqlalchemy import text

from feasibility.apple_ingestion.deployment import deployment_engine, load_config
from feasibility.apple_ingestion.retrieval import iter_current_reviews, list_review_versions

expected = "apple_coverage_main_20261113_2100"
engine = deployment_engine(load_config(environ["PRIVATE_DEPLOYMENT_FILE"]), "report")
with engine.connect() as connection, connection.begin():
    connection.exec_driver_sql("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
    if connection.scalar(text("SELECT current_database()")) != expected:
        raise ValueError("Unexpected database")

    rows = list(iter_current_reviews(connection, source_application_id="570060128"))
    selected = list(iter_current_reviews(
        connection,
        source_application_id="570060128",
        time_field="first_observed_at",
        start=datetime(2026, 11, 14, tzinfo=timezone.utc),
        end=datetime(2026, 11, 18, tzinfo=timezone.utc),
        ratings=[4, 5],
    ))
    if selected:
        row = selected[0]
        history = list_review_versions(
            connection,
            source_application_id=row.source_application_id,
            source_review_id=row.source_review_id,
        )
        current = next(version for version in history if version.is_current)
        assert current.version_id == row.version_id
        assert current.detecting_run_id == row.detecting_run_id
engine.dispose()
```

## Export and load a private CSV

The command verifies the connected database before reading reviews. Choose a
fresh absolute directory outside any Git checkout, under a trusted parent on a
filesystem that supports Unix permissions. The exporter creates the directory
with mode 0700 and writes files with permissions no broader than 0600. It
checks database identity, resolves the app and streams all rows within one
read-only REPEATABLE READ transaction.

```sh
python -m feasibility.apple_ingestion.retrieval_export \
  --deployment "$PRIVATE_DEPLOYMENT_FILE" \
  --expected-database apple_coverage_main_20261113_2100 \
  --dataset-label duolingo-coverage \
  --app-id 570060128 \
  --output-dir "$PRIVATE_EXPORT_ROOT/duolingo-current"
```

The loading example uses Pandas 2.0 or later. Load the CSV as strings with automatic missing-value
inference disabled, then decode and cast only the typed columns. Identity
strings must retain leading zeros.

```python
from os import environ
from pathlib import Path

import pandas as pd

from feasibility.apple_ingestion.retrieval_export import decode_csv_cell

csv_path = Path(environ["PRIVATE_EXPORT_ROOT"]) / "duolingo-current" / "reviews.csv"
frame = pd.read_csv(csv_path, dtype=str, keep_default_na=False, na_filter=False)
for column in frame.columns:
    frame[column] = pd.Series(
        [decode_csv_cell(value) for value in frame[column]], index=frame.index, dtype=object
    )

for column in (
    "review_id", "version_id", "version_number", "rating",
    "observation_count", "conflict_occurrence_count",
):
    frame[column] = frame[column].astype("Int64")

for column in (
    "source_updated_at", "first_observed_at", "last_observed_at",
    "version_first_observed_at",
):
    frame[column] = pd.to_datetime(frame[column], format="ISO8601", utc=True)
```

## Validation results

The retained Duolingo database produced 1,247 distinct current records under the
report role. Every returned field matched an independent SQL query that grouped
observations by review. Both rating-only changes returned version 2 as current
and version 1 in history. All five rating filters matched the current ratings.
The regression suite passed all 750 tests at publication, including 13 focused retrieval cases.

Disposable PostgreSQL tests cover current and historical version selection,
duplicate observations, conflict counts, partial-run provenance, app isolation,
time and rating filters, batch independence, SELECT-only role access, CSV
round trips, and a concurrent write during a single export snapshot.

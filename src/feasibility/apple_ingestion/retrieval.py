"""Faithful review projections from a caller-owned PostgreSQL connection."""

from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import text


class RetrievalError(ValueError):
    """Invalid retrieval input or unknown identity."""


@dataclass(frozen=True)
class CurrentReview:
    source: str
    source_application_id: str
    source_review_id: str
    review_id: int
    version_id: int
    version_number: int
    title: str | None
    body: str
    rating: int
    application_version: str | None
    source_updated_at: datetime | None
    first_observed_at: datetime
    last_observed_at: datetime
    version_first_observed_at: datetime
    detecting_run_id: UUID
    detecting_batch_id: UUID
    detecting_run_status: str
    storefront: str
    sort_by: str
    observation_count: int
    conflict_occurrence_count: int


@dataclass(frozen=True)
class ReviewVersionRecord(CurrentReview):
    is_current: bool


_TIME_COLUMNS = {
    "first_observed_at": "r.first_observed_at",
    "source_updated_at": "v.source_updated_at",
}
_PROJECTION = """
SELECT a.source, a.source_application_id, r.source_review_id, r.id AS review_id,
       v.id AS version_id, v.version_number, v.title, v.body, v.rating,
       v.application_version, v.source_updated_at,
       r.first_observed_at, r.last_observed_at,
       v.first_observed_at AS version_first_observed_at,
       cr.id AS detecting_run_id, cr.batch_id AS detecting_batch_id,
       cr.execution_status AS detecting_run_status, ct.storefront, ct.sort_by,
       obs.observation_count, obs.conflict_occurrence_count
"""
_FROM = """
FROM application a
JOIN review r ON r.application_id = a.id
JOIN review_version v ON v.review_id = r.id AND v.application_id = a.id
JOIN collection_run cr ON cr.id = v.detecting_run_id AND cr.application_id = a.id
JOIN collection_target ct ON ct.id = cr.target_id AND ct.application_id = a.id
CROSS JOIN LATERAL (
    SELECT count(*) AS observation_count,
           coalesce(sum(o.conflict_count), 0) AS conflict_occurrence_count
    FROM review_observation o
    WHERE o.review_id = r.id AND o.application_id = a.id
) obs
WHERE a.id = :app
"""


def _identity(value):
    if not isinstance(value, str) or not value.strip() or "\0" in value:
        raise RetrievalError("Expected a nonempty source ID")
    return value


def _app_id(connection, source_application_id):
    app = connection.scalar(text("""
        SELECT id FROM application
        WHERE source = 'apple_app_store' AND source_application_id = :source_id
    """), {"source_id": _identity(source_application_id)})
    if app is None:
        raise RetrievalError("Application not found")
    return app


def _utc(value):
    if value is None:
        return None
    if not isinstance(value, datetime) or value.utcoffset() is None:
        raise RetrievalError("Expected a timezone-aware datetime")
    return value.astimezone(timezone.utc)


def normalize_filters(source_application_id, time_field, start, end, ratings, batch_size):
    _identity(source_application_id)
    if not isinstance(time_field, str) or time_field not in _TIME_COLUMNS:
        raise RetrievalError("Unsupported time field")
    start, end = _utc(start), _utc(end)
    if start is not None and end is not None and start >= end:
        raise RetrievalError("Start must precede end")
    if ratings is not None:
        from collections.abc import Collection

        if (not isinstance(ratings, Collection) or isinstance(ratings, (str, bytes, bytearray))
                or not ratings or any(type(r) is not int or not 1 <= r <= 5 for r in ratings)):
            raise RetrievalError("Ratings must be a nonempty collection of integers from 1 to 5")
        ratings = sorted(set(ratings))
    if type(batch_size) is not int or batch_size <= 0:
        raise RetrievalError("Batch size must be a positive integer")
    return dict(source_application_id=source_application_id, time_field=time_field,
                start=start, end=end, ratings=ratings)


def iter_current_reviews(connection, *, source_application_id, time_field="first_observed_at",
                         start=None, end=None, ratings=None, batch_size=1000):
    """Yield current rows in review ID order using a bounded PostgreSQL cursor."""
    filters = normalize_filters(source_application_id, time_field, start, end, ratings, batch_size)
    params = {"app": _app_id(connection, source_application_id)}
    predicates = ["v.id = r.current_version_id"]
    column = _TIME_COLUMNS[time_field]
    for name, operator in (("start", ">="), ("end", "<")):
        if filters[name] is not None:
            predicates.append(f"{column} {operator} :{name}")
            params[name] = filters[name]
    if filters["ratings"] is not None:
        predicates.append("v.rating = ANY(:ratings)")
        params["ratings"] = filters["ratings"]
    query = text(_PROJECTION + _FROM + " AND " + " AND ".join(predicates) + " ORDER BY r.id")
    with connection.execute(query.execution_options(yield_per=batch_size), params) as result:
        for row in result.mappings():
            yield CurrentReview(**row)


def list_review_versions(connection, *, source_application_id, source_review_id):
    """Return the stored version sequence, or an empty list for an absent review."""
    source_review_id = _identity(source_review_id)
    app = _app_id(connection, source_application_id)
    query = text(_PROJECTION + ", (v.id = r.current_version_id) AS is_current\n" + _FROM
                 + " AND r.source_review_id = :review ORDER BY v.version_number")
    return [ReviewVersionRecord(**row) for row in
            connection.execute(query, {"app": app, "review": source_review_id}).mappings()]

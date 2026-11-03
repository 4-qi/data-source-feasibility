"""PostgreSQL mappings for the seven-table Apple ingestion design.

No relationship autoflush is used to resolve the owned circular foreign key.
Writers reserve a review_version ID, insert the review, then insert its version
within a transaction. The owned current pointer is checked at commit.
"""
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import (
    BigInteger, Boolean, CheckConstraint, DateTime, ForeignKey,
    ForeignKeyConstraint, Identity, Index, Integer, LargeBinary, Numeric,
    SmallInteger, Text, UniqueConstraint, text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


def identity():
    return mapped_column(BigInteger, Identity(), primary_key=True)


def timestamp(*, nullable=False):
    return mapped_column(DateTime(timezone=True), nullable=nullable)


class Application(Base):
    __tablename__ = "application"
    id: Mapped[int] = identity()
    source: Mapped[str] = mapped_column(Text)
    source_application_id: Mapped[str] = mapped_column(Text)
    name: Mapped[str] = mapped_column(Text)
    analytical_category: Mapped[str] = mapped_column(Text)
    __table_args__ = (
        CheckConstraint("source = 'apple_app_store'", name="application_source"),
        CheckConstraint("length(source_application_id) > 0", name="application_source_id_nonempty"),
        CheckConstraint("length(name) > 0", name="application_name_nonempty"),
        CheckConstraint("analytical_category IN ('productivity', 'education', 'shopping', 'transportation')", name="application_category"),
        UniqueConstraint("source", "source_application_id", name="application_source_identity"),
    )


class CollectionTarget(Base):
    __tablename__ = "collection_target"
    id: Mapped[int] = identity()
    application_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("application.id"))
    storefront: Mapped[str] = mapped_column(Text)
    sort_by: Mapped[str] = mapped_column(Text)
    enabled: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    interval_hours: Mapped[int] = mapped_column(Integer, server_default=text("24"))
    min_pages: Mapped[int] = mapped_column(Integer, server_default=text("2"))
    max_pages: Mapped[int] = mapped_column(Integer, server_default=text("5"))
    min_overlap_count: Mapped[int] = mapped_column(Integer, server_default=text("20"))
    min_overlap_ratio: Mapped[Decimal] = mapped_column(Numeric(6, 5), server_default=text("0.20"))
    max_http_requests: Mapped[int] = mapped_column(Integer, server_default=text("10"))
    reference_max_age_hours: Mapped[int] = mapped_column(Integer, server_default=text("72"))
    __table_args__ = (
        CheckConstraint("storefront = 'us'", name="target_storefront"),
        CheckConstraint("sort_by = 'mostrecent'", name="target_sort"),
        CheckConstraint("interval_hours > 0", name="target_interval"),
        CheckConstraint("min_pages >= 1", name="target_min_pages"),
        CheckConstraint("max_pages >= min_pages", name="target_max_pages"),
        CheckConstraint("min_overlap_count >= 0", name="target_overlap_count"),
        CheckConstraint("min_overlap_ratio BETWEEN 0 AND 1", name="target_overlap_ratio"),
        CheckConstraint("max_http_requests > 0", name="target_request_budget"),
        CheckConstraint("reference_max_age_hours > 0", name="target_reference_age"),
        UniqueConstraint("application_id", "storefront", "sort_by", name="target_identity"),
        UniqueConstraint("id", "application_id", name="target_owned_id"),
    )


class CollectionRun(Base):
    __tablename__ = "collection_run"
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    target_id: Mapped[int] = mapped_column(BigInteger)
    application_id: Mapped[int] = mapped_column(BigInteger)
    batch_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True))
    started_at: Mapped[datetime] = timestamp()
    finished_at: Mapped[datetime | None] = timestamp(nullable=True)
    execution_status: Mapped[str] = mapped_column(Text)
    coverage_status: Mapped[str] = mapped_column(Text)
    reference_run_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    stop_reason: Mapped[str | None] = mapped_column(Text)
    config_snapshot: Mapped[dict] = mapped_column(JSONB)
    anomalies: Mapped[list] = mapped_column(JSONB, server_default=text("'[]'::jsonb"))
    __table_args__ = (
        ForeignKeyConstraint(["target_id", "application_id"], ["collection_target.id", "collection_target.application_id"], name="run_target_ownership"),
        UniqueConstraint("id", "application_id", name="run_owned_id"),
        UniqueConstraint("id", "target_id", "application_id", name="run_target_owned_id"),
        ForeignKeyConstraint(["reference_run_id", "target_id", "application_id"], ["collection_run.id", "collection_run.target_id", "collection_run.application_id"], name="run_reference_ownership"),
        CheckConstraint("execution_status IN ('running', 'succeeded', 'partial', 'failed', 'interrupted')", name="run_execution_status"),
        CheckConstraint("coverage_status IN ('pending', 'baseline', 'overlap_sufficient', 'overlap_insufficient', 'no_reference', 'empty_window', 'indeterminate')", name="run_coverage_status"),
        CheckConstraint("jsonb_typeof(config_snapshot) = 'object'", name="run_snapshot_object"),
        CheckConstraint("jsonb_typeof(anomalies) = 'array'", name="run_anomalies_array"),
        CheckConstraint("reference_run_id IS NULL OR reference_run_id <> id", name="run_no_self_reference"),
        CheckConstraint("finished_at IS NULL OR finished_at >= started_at", name="run_time_order"),
        CheckConstraint("(execution_status = 'running' AND finished_at IS NULL AND stop_reason IS NULL) OR (execution_status <> 'running' AND finished_at IS NOT NULL AND stop_reason IS NOT NULL)", name="run_lifecycle"),
        CheckConstraint("execution_status <> 'running' OR coverage_status = 'pending'", name="run_pending_coverage"),
        Index("one_running_run_per_target", "target_id", unique=True, postgresql_where=text("execution_status = 'running'")),
        Index("collection_run_reference_lookup", "target_id", started_at.desc()),
        Index("collection_run_batch_lookup", "batch_id"),
    )


class FetchAttempt(Base):
    __tablename__ = "fetch_attempt"
    id: Mapped[int] = identity()
    run_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("collection_run.id"))
    request_number: Mapped[int] = mapped_column(Integer)
    page_number: Mapped[int] = mapped_column(Integer)
    format: Mapped[str] = mapped_column(Text)
    attempt_number: Mapped[int] = mapped_column(Integer)
    started_at: Mapped[datetime] = timestamp()
    finished_at: Mapped[datetime | None] = timestamp(nullable=True)
    http_status: Mapped[int | None] = mapped_column(SmallInteger)
    parsing_status: Mapped[str] = mapped_column(Text)
    persistence_status: Mapped[str] = mapped_column(Text)
    entry_count: Mapped[int | None] = mapped_column(Integer)
    response_bytes: Mapped[int | None] = mapped_column(Integer)
    error_codes: Mapped[list] = mapped_column(JSONB, server_default=text("'[]'::jsonb"))
    anomalies: Mapped[list] = mapped_column(JSONB, server_default=text("'[]'::jsonb"))
    __table_args__ = (
        CheckConstraint("request_number > 0", name="attempt_request_number"),
        CheckConstraint("page_number > 0", name="attempt_page_number"),
        CheckConstraint("format IN ('json', 'xml')", name="attempt_format"),
        CheckConstraint("attempt_number > 0", name="attempt_number_positive"),
        CheckConstraint("http_status BETWEEN 100 AND 599", name="attempt_http_status"),
        CheckConstraint("parsing_status IN ('pending', 'not_attempted', 'succeeded', 'failed')", name="attempt_parsing_status"),
        CheckConstraint("persistence_status IN ('pending', 'not_applicable', 'committed', 'rolled_back', 'unknown')", name="attempt_persistence_status"),
        CheckConstraint("entry_count >= 0", name="attempt_entry_count"),
        CheckConstraint("response_bytes >= 0", name="attempt_response_bytes"),
        CheckConstraint("jsonb_typeof(error_codes) = 'array'", name="attempt_error_codes_array"),
        CheckConstraint("jsonb_typeof(anomalies) = 'array'", name="attempt_anomalies_array"),
        UniqueConstraint("run_id", "request_number", name="attempt_request_identity"),
        UniqueConstraint("run_id", "page_number", "format", "attempt_number", name="attempt_format_identity"),
        CheckConstraint("finished_at IS NULL OR finished_at >= started_at", name="attempt_time_order"),
        CheckConstraint("parsing_status <> 'succeeded' OR entry_count IS NOT NULL", name="attempt_success_count"),
        CheckConstraint("persistence_status <> 'committed' OR parsing_status = 'succeeded'", name="attempt_commit_parse"),
        Index("one_committed_response_per_page", "run_id", "page_number", unique=True, postgresql_where=text("persistence_status = 'committed'")),
    )


class Review(Base):
    __tablename__ = "review"
    id: Mapped[int] = identity()
    application_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("application.id"))
    source_review_id: Mapped[str] = mapped_column(Text)
    current_version_id: Mapped[int] = mapped_column(BigInteger)
    first_observed_at: Mapped[datetime] = timestamp()
    last_observed_at: Mapped[datetime] = timestamp()
    __table_args__ = (
        CheckConstraint("length(source_review_id) > 0", name="review_source_id_nonempty"),
        UniqueConstraint("application_id", "source_review_id", name="review_source_identity"),
        UniqueConstraint("id", "application_id", name="review_owned_id"),
        CheckConstraint("last_observed_at >= first_observed_at", name="review_time_order"),
        ForeignKeyConstraint(["id", "current_version_id"], ["review_version.review_id", "review_version.id"], name="current_version_belongs_to_review", deferrable=True, initially="DEFERRED", use_alter=True),
    )


class ReviewVersion(Base):
    __tablename__ = "review_version"
    id: Mapped[int] = identity()
    review_id: Mapped[int] = mapped_column(BigInteger)
    application_id: Mapped[int] = mapped_column(BigInteger)
    version_number: Mapped[int] = mapped_column(Integer)
    title: Mapped[str | None] = mapped_column(Text)
    body: Mapped[str] = mapped_column(Text)
    rating: Mapped[int] = mapped_column(SmallInteger)
    application_version: Mapped[str | None] = mapped_column(Text)
    source_updated_at: Mapped[datetime | None] = timestamp(nullable=True)
    content_hash: Mapped[bytes] = mapped_column(LargeBinary)
    metadata_hash: Mapped[bytes] = mapped_column(LargeBinary)
    first_observed_at: Mapped[datetime] = timestamp()
    detecting_run_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True))
    __table_args__ = (
        CheckConstraint("version_number > 0", name="version_number_positive"),
        CheckConstraint("rating BETWEEN 1 AND 5", name="version_rating"),
        CheckConstraint("octet_length(content_hash) = 32", name="version_content_hash_length"),
        CheckConstraint("octet_length(metadata_hash) = 32", name="version_metadata_hash_length"),
        ForeignKeyConstraint(["review_id", "application_id"], ["review.id", "review.application_id"], name="version_review_ownership"),
        ForeignKeyConstraint(["detecting_run_id", "application_id"], ["collection_run.id", "collection_run.application_id"], name="version_run_ownership"),
        UniqueConstraint("review_id", "version_number", name="version_sequence_identity"),
        UniqueConstraint("review_id", "id", name="version_owned_id"),
    )


class ReviewObservation(Base):
    __tablename__ = "review_observation"
    run_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    review_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    application_id: Mapped[int] = mapped_column(BigInteger)
    observed_version_id: Mapped[int] = mapped_column(BigInteger)
    first_observed_at: Mapped[datetime] = timestamp()
    first_observed_page: Mapped[int] = mapped_column(Integer)
    first_observed_position: Mapped[int] = mapped_column(Integer)
    occurrence_count: Mapped[int] = mapped_column(Integer, server_default=text("1"))
    conflict_count: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    first_action: Mapped[str] = mapped_column(Text)
    __table_args__ = (
        CheckConstraint("first_observed_page > 0", name="observation_page_positive"),
        CheckConstraint("first_observed_position > 0", name="observation_position_positive"),
        CheckConstraint("occurrence_count >= 1", name="observation_occurrence_count"),
        CheckConstraint("conflict_count >= 0", name="observation_conflict_count"),
        CheckConstraint("first_action IN ('new', 'unchanged', 'changed')", name="observation_first_action"),
        ForeignKeyConstraint(["run_id", "application_id"], ["collection_run.id", "collection_run.application_id"], name="observation_run_ownership"),
        ForeignKeyConstraint(["review_id", "application_id"], ["review.id", "review.application_id"], name="observation_review_ownership"),
        ForeignKeyConstraint(["review_id", "observed_version_id"], ["review_version.review_id", "review_version.id"], name="observation_version_ownership"),
        CheckConstraint("conflict_count < occurrence_count", name="observation_conflict_bound"),
        Index("review_observation_review_history", "review_id", "run_id"),
    )


__all__ = ["Base", "Application", "CollectionTarget", "CollectionRun", "FetchAttempt", "Review", "ReviewVersion", "ReviewObservation"]

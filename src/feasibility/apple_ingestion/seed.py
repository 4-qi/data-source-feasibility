"""Explicit manifest loading and transactional maintenance-role seeding.

No files, database engines, connections or transactions are opened at import.
The caller supplies the historical manifest path and an already transactional
SQLAlchemy Connection. Existing application/target rows are never overwritten.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import json
from pathlib import Path
from typing import TYPE_CHECKING

from .contracts import ContractError, IngestionConfig, _text

if TYPE_CHECKING:
    from sqlalchemy.engine import Connection


@dataclass(frozen=True)
class SeedApplication:
    source_application_id: str
    name: str
    analytical_category: str
    storefront: str = "us"
    source: str = "apple_app_store"

    def __post_init__(self) -> None:
        for name in ("source_application_id", "name", "analytical_category"):
            _text(name, getattr(self, name))
        if self.analytical_category not in {"productivity", "education", "shopping", "transportation"}:
            raise ContractError("unsupported analytical_category")
        if type(self.storefront) is not str or self.storefront != "us":
            raise ContractError("seed storefront must be us")
        if type(self.source) is not str or self.source != "apple_app_store":
            raise ContractError("seed source must be apple_app_store")


def load_seed_manifest(manifest_path: str | Path) -> tuple[SeedApplication, ...]:
    """Read exactly eight US identities from the caller-selected sampling frame.

    Historical counters and unrelated catalog/probe metadata are not ingested.
    This reads the manifest; it does not update or reinterpret its evidence.
    """
    with Path(manifest_path).open(encoding="utf-8") as handle:
        manifest = json.load(handle)
    if not isinstance(manifest, dict) or type(manifest.get("expected_apps")) is not int or manifest["expected_apps"] != 8:
        raise ContractError("manifest expected_apps must be 8")
    apps = manifest.get("apps")
    if type(apps) is not list or len(apps) != 8:
        raise ContractError("manifest must contain eight apps")
    records = []
    for item in apps:
        if not isinstance(item, dict):
            raise ContractError("manifest apps must be objects")
        try:
            record = SeedApplication(
                source_application_id=item["app_store_id"], name=item["name"],
                analytical_category=item["analysis_stratum"], storefront=item["storefront"])
        except KeyError as exc:
            raise ContractError("manifest app is missing an identity field") from exc
        records.append(record)
    if len({record.source_application_id for record in records}) != 8:
        raise ContractError("manifest app identities must be unique")
    if Counter(record.analytical_category for record in records) != {
            "productivity": 2, "education": 2, "shopping": 2, "transportation": 2}:
        raise ContractError("manifest must contain two apps per analytical category")
    return tuple(records)


@dataclass(frozen=True)
class SeedResult:
    application_ids: tuple[int, ...]
    target_ids: tuple[int, ...]


def seed_defaults(connection: Connection, manifest_path: str | Path) -> SeedResult:
    """Idempotently seed eight disabled targets; caller commits or rolls back.

    Uses PostgreSQL Core tables, not model constructors. PostgreSQL conflict
    handling preserves existing settings, including intentionally enabled targets.
    This function does not grant live access or check access-policy eligibility.
    """
    records = load_seed_manifest(manifest_path)
    if not connection.in_transaction():
        raise ContractError("seed_defaults requires a caller-owned transaction")
    if connection.dialect.name != "postgresql":
        raise ContractError("seed_defaults requires a PostgreSQL connection")
    from sqlalchemy import select
    from sqlalchemy.dialects.postgresql import insert
    from .models import Base

    application = Base.metadata.tables["application"]
    target = Base.metadata.tables["collection_target"]
    config = IngestionConfig()
    application_ids, target_ids = [], []
    for record in records:
        identity = {"source": record.source, "source_application_id": record.source_application_id}
        connection.execute(insert(application).values(
            **identity, name=record.name, analytical_category=record.analytical_category
        ).on_conflict_do_nothing(index_elements=["source", "source_application_id"]))
        app_id = connection.execute(select(application.c.id).where(
            application.c.source == record.source,
            application.c.source_application_id == record.source_application_id
        )).scalar_one()
        target_identity = {"application_id": app_id, "storefront": record.storefront,
                           "sort_by": "mostrecent"}
        connection.execute(insert(target).values(
            **target_identity, enabled=False, interval_hours=config.interval_hours,
            min_pages=config.min_pages, max_pages=config.max_pages,
            min_overlap_count=config.min_overlap_count, min_overlap_ratio=config.min_overlap_ratio,
            max_http_requests=config.max_http_requests,
            reference_max_age_hours=config.reference_max_age_hours
        ).on_conflict_do_nothing(index_elements=["application_id", "storefront", "sort_by"]))
        target_id = connection.execute(select(target.c.id).where(
            target.c.application_id == app_id, target.c.storefront == record.storefront,
            target.c.sort_by == "mostrecent"
        )).scalar_one()
        application_ids.append(app_id)
        target_ids.append(target_id)
    return SeedResult(tuple(application_ids), tuple(target_ids))

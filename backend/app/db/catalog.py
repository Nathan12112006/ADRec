"""Offline catalog export from one PostgreSQL statement snapshot."""

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.records import Ad, Advertiser, CatalogRevision
from app.retrieval.snapshots import IndexEntry
from app.retrieval.vectors import ad_vector


@dataclass(frozen=True)
class IndexCatalog:
    dataset_id: UUID
    version: str
    entries: tuple[IndexEntry, ...]


def catalog_version(session: Session, dataset_id: UUID, *, lock: bool = False) -> str:
    statement = select(CatalogRevision.revision).where(CatalogRevision.dataset_id == dataset_id)
    if lock:
        statement = statement.with_for_update(read=True)
    revision = session.scalar(statement)
    if revision is None:
        raise ValueError("unknown dataset or missing catalog revision")
    return f"catalog-v2:{dataset_id}:{revision}"


def read_catalog(session: Session, dataset_id: UUID) -> IndexCatalog:
    """Export eligible vectors while holding the database-maintained revision stable.

    A shared revision-row lock prevents catalog writers from committing until the
    caller ends its transaction. Dataset provenance remains immutable. Run this offline.
    """
    version = catalog_version(session, dataset_id, lock=True)
    statement = (
        select(
            Ad.id,
            Ad.dataset_id,
            Ad.advertiser_id,
            Ad.title,
            Ad.description,
            Ad.target_url,
            Ad.category,
            Ad.interests,
            Ad.bid,
            Ad.active,
            Advertiser.active.label("advertiser_active"),
        )
        .join(Advertiser, Ad.advertiser_id == Advertiser.id)
        .where(Ad.dataset_id == dataset_id)
        .order_by(Ad.id)
        .execution_options(yield_per=1000)
    )
    entries = []
    with session.execute(statement) as rows:
        for row in rows.mappings():
            if row["active"] and row["advertiser_active"]:
                entries.append(
                    IndexEntry(
                        ad_id=row["id"],
                        vector=ad_vector(row["interests"], category=row["category"]),
                    )
                )
    return IndexCatalog(dataset_id, version, tuple(entries))

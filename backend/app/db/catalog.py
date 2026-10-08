"""Offline catalog export from one PostgreSQL statement snapshot."""

import hashlib
import json
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.records import Ad, Advertiser, Dataset
from app.retrieval.snapshots import IndexEntry
from app.retrieval.vectors import ad_vector


@dataclass(frozen=True)
class IndexCatalog:
    dataset_id: UUID
    version: str
    entries: tuple[IndexEntry, ...]


def read_catalog(session: Session, dataset_id: UUID) -> IndexCatalog:
    """Fingerprint all dataset ad metadata; export only currently eligible vectors.

    The ordered join is one MVCC statement snapshot, so concurrent edits cannot pair
    the version of one catalog with vectors from another. Caller owns the transaction.
    This full offline scan is not a request-time freshness check.
    """
    if session.get(Dataset, dataset_id) is None:
        raise ValueError("unknown dataset")
    digest = hashlib.sha256(f"catalog-v1/{dataset_id}".encode())
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
            digest.update(
                b"\n"
                + json.dumps(dict(row), default=str, sort_keys=True, separators=(",", ":")).encode()
            )
            if row["active"] and row["advertiser_active"]:
                entries.append(
                    IndexEntry(
                        ad_id=row["id"],
                        vector=ad_vector(row["interests"], category=row["category"]),
                    )
                )
    return IndexCatalog(dataset_id, "catalog-v1:" + digest.hexdigest(), tuple(entries))

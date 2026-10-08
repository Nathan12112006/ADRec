"""Read-only, repeatable-read entity export; releases PostgreSQL before generation."""

from uuid import UUID

from sqlalchemy import select, text

from app.db.session import Database
from app.history.artifacts import HistorySource
from app.models.records import Ad, Advertiser, Dataset, User


def export_source(database: Database, dataset_id: UUID) -> HistorySource:
    with database.session() as session:
        session.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY"))
        dataset = session.get(Dataset, dataset_id)
        if dataset is None:
            raise ValueError("unknown history dataset")
        users = tuple(
            {**dict(row), "dataset_id": str(dataset_id)}
            for row in session.execute(
                select(*User.__table__.columns)
                .where(User.dataset_id == dataset_id)
                .order_by(User.id)
                .execution_options(yield_per=1000)
            ).mappings()
        )
        ads = tuple(
            {**dict(row), "dataset_id": str(dataset_id), "bid": str(row["bid"])}
            for row in session.execute(
                select(*Ad.__table__.columns, Advertiser.active.label("advertiser_active"))
                .join(Advertiser)
                .where(Ad.dataset_id == dataset_id, Ad.active, Advertiser.active)
                .order_by(Ad.id)
                .execution_options(yield_per=1000)
            ).mappings()
        )
        return HistorySource(
            dataset_id=dataset_id,
            users=users,
            ads=ads,
            entity_manifest={
                "seed": dataset.seed,
                "generator_version": dataset.generator_version,
                "configuration": dataset.configuration,
            },
        )

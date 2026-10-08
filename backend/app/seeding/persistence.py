"""Insert one dataset atomically; never replace or repair existing records."""

from dataclasses import dataclass
from itertools import groupby, islice
from typing import Literal
from uuid import UUID

from sqlalchemy import insert, select, text

from app.db.session import Database
from app.models.records import Ad, Advertiser, Dataset, User
from app.seeding.generation import GENERATOR_VERSION, SeedConfig, generate_entities


class SeedConflict(ValueError):
    """A different dataset already exists; explicit append or a fresh database is required."""


@dataclass(frozen=True)
class SeedResult:
    dataset_id: UUID
    status: Literal["created", "already_exists"]
    users: int
    advertisers: int
    ads: int


def seed_database(
    database: Database, config: SeedConfig, *, append: bool = False, batch_size: int = 1000
) -> SeedResult:
    if not 1 <= batch_size <= 10000:
        raise ValueError("batch_size must be between 1 and 10000")
    dataset_id = config.dataset_id
    status: Literal["created", "already_exists"] = "created"
    with database.transaction() as session:
        # Serializes cooperating seeders, including different configurations. Lock wait is bounded.
        session.execute(text("SELECT pg_advisory_xact_lock(2026100703)"))
        existing = session.get(Dataset, dataset_id)
        if existing is not None:
            if (
                existing.seed != config.seed
                or existing.generator_version != GENERATOR_VERSION
                or existing.configuration != config.manifest()
            ):
                raise SeedConflict("Dataset identity conflicts with existing provenance")
            status = "already_exists"
        else:
            if not append and session.scalar(select(Dataset.id).limit(1)) is not None:
                raise SeedConflict("A dataset exists; use a fresh database or explicitly --append")
            session.add(
                Dataset(
                    id=dataset_id,
                    seed=config.seed,
                    generator_version=GENERATOR_VERSION,
                    configuration=config.manifest(),
                )
            )
            session.flush()
            tables = {"users": User, "advertisers": Advertiser, "ads": Ad}
            for kind, entities in groupby(generate_entities(config), key=lambda item: item[0]):
                while batch := [row for _, row in islice(entities, batch_size)]:
                    session.execute(insert(tables[kind]), batch)
    return SeedResult(dataset_id, status, config.users, config.advertisers, config.ads)

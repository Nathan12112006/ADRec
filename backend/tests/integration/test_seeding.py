from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from uuid import uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.db.session import Database
from app.models.records import Ad, Advertiser, Dataset, Event, Recommendation, RequestOutcome, User
from app.seeding import SeedConfig, SeedConflict, generate_entities, seed_database


def test_seed_is_atomic_repeatable_and_preserves_existing_history(database: Database) -> None:
    config = SeedConfig(seed=uuid4().int % 2**62, users=7, advertisers=3, ads=15)
    first = seed_database(database, config, append=True, batch_size=4)
    assert first.status == "created"
    with database.transaction() as session:
        for model, column, expected in [
            (User, User.dataset_id, 7),
            (Advertiser, Advertiser.dataset_id, 3),
            (Ad, Ad.dataset_id, 15),
        ]:
            assert (
                session.scalar(
                    select(func.count()).select_from(model).where(column == config.dataset_id)
                )
                == expected
            )
        dataset = session.get(Dataset, config.dataset_id)
        assert dataset is not None and dataset.configuration == config.manifest()
        models = {"users": User, "advertisers": Advertiser, "ads": Ad}
        for kind, expected_row in generate_entities(config):
            saved = session.get(models[kind], expected_row["id"])
            assert saved is not None
            for field, expected_value in expected_row.items():
                assert getattr(saved, field) == expected_value
        user = session.scalars(select(User).where(User.dataset_id == config.dataset_id)).first()
        assert user is not None
        key = str(uuid4())
        ad = session.scalars(select(Ad).where(Ad.dataset_id == config.dataset_id)).first()
        assert ad is not None
        recommendation = Recommendation(
            dataset_id=config.dataset_id,
            user_id=user.id,
            ad_id=ad.id,
            bid=ad.bid,
            selected_ad={"title": ad.title},
        )
        session.add(recommendation)
        session.flush()
        session.add(
            RequestOutcome(request_key=key, user_id=user.id, recommendation_id=recommendation.id)
        )
        session.add_all(
            [
                Event(recommendation_id=recommendation.id, event_type="impression"),
                Event(
                    recommendation_id=recommendation.id,
                    event_type="click",
                    simulated_revenue=ad.bid,
                ),
            ]
        )
        session.flush()
        before = [
            session.scalar(select(func.count()).select_from(model))
            for model in (Recommendation, Event, RequestOutcome)
        ]
    repeated = seed_database(database, config, batch_size=2)
    assert repeated.status == "already_exists"
    assert replace(first, status="already_exists") == repeated
    with database.transaction() as session:
        assert session.get(RequestOutcome, key) is not None
        assert before == [
            session.scalar(select(func.count()).select_from(model))
            for model in (Recommendation, Event, RequestOutcome)
        ]
    different = SeedConfig(seed=config.seed + 1, users=3, advertisers=2, ads=5)
    with pytest.raises(SeedConflict):
        seed_database(database, different)
    assert seed_database(database, different, append=True).status == "created"
    with database.transaction() as session:
        assert session.get(RequestOutcome, key) is not None
        assert before == [
            session.scalar(select(func.count()).select_from(model))
            for model in (Recommendation, Event, RequestOutcome)
        ]


def test_entity_id_conflict_rolls_back_entire_seed(database: Database) -> None:
    config = SeedConfig(seed=uuid4().int % 2**62, users=2, advertisers=1, ads=2)
    users = [row for kind, row in generate_entities(config) if kind == "users"]
    with database.transaction() as session:
        other = Dataset(seed=0, generator_version="collision-test", configuration={})
        session.add(other)
        session.flush()
        session.add(User(**{**users[1], "dataset_id": other.id}))
    with pytest.raises(IntegrityError):
        seed_database(database, config, append=True, batch_size=1)
    with database.transaction() as session:
        assert session.get(Dataset, config.dataset_id) is None
        assert session.get(User, users[0]["id"]) is None


def test_concurrent_identical_seeders_create_one_dataset(database: Database) -> None:
    config = SeedConfig(seed=uuid4().int % 2**62, users=2, advertisers=1, ads=4)
    with ThreadPoolExecutor(max_workers=2) as workers:
        futures = [workers.submit(seed_database, database, config, append=True) for _ in range(2)]
        assert sorted(future.result().status for future in futures) == ["already_exists", "created"]

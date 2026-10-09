from collections.abc import Callable, Iterator
from dataclasses import dataclass
from decimal import Decimal
from typing import Any
from uuid import uuid4

import numpy as np
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import get_ctr_model, get_session
from app.core.config import Settings
from app.core.errors import WorkflowError
from app.ctr.serving import CTRModel
from app.db.session import Database
from app.main import create_app
from app.models.records import Ad, Advertiser, User
from app.ranking.strategies import ExpectedValue
from app.seeding import SeedConfig, seed_database
from app.services.events import record_event
from app.services.recommendations import recommend


@dataclass(frozen=True)
class Inventory:
    user_id: int
    music_id: int
    cars_id: int


@pytest.fixture
def inventory(database: Database) -> Inventory:
    config = SeedConfig(seed=uuid4().int % 2**62, users=1, advertisers=1, ads=2)
    seed_database(database, config, append=True)
    with database.transaction() as session:
        user = session.scalar(select(User).where(User.dataset_id == config.dataset_id))
        assert user is not None
        user.interests = ["music"]
        user.device = "mobile"
        user.age_group = "25-34"
        advertiser = session.scalar(
            select(Advertiser).where(Advertiser.dataset_id == config.dataset_id)
        )
        assert advertiser is not None
        advertiser.active = True
        ads = list(
            session.scalars(select(Ad).where(Ad.dataset_id == config.dataset_id).order_by(Ad.id))
        )
        for ad, category, bid in zip(ads, ("music", "cars"), ("1", "3"), strict=True):
            ad.active = True
            ad.interests = ["music"]
            ad.category = category
            ad.bid = Decimal(bid)
        return Inventory(user.id, ads[0].id, ads[1].id)


class Estimator:
    """Controllable external estimator behind the actual CTR adapter."""

    classes_ = np.asarray([0, 1])

    def __init__(self) -> None:
        self.batches: list[Any] = []
        self.on_first_batch: Callable[[], None] | None = None
        self.on_batch: Callable[[], None] | None = None
        self.failure: str | None = None

    def predict_proba(self, matrix: Any) -> Any:
        self.batches.append(matrix.tolist())
        if len(self.batches) == 1 and self.on_first_batch is not None:
            self.on_first_batch()
        if self.on_batch is not None:
            self.on_batch()
        if self.failure == "exception":
            raise RuntimeError("private estimator details")
        if self.failure == "count":
            return np.asarray([[0.9, 0.1]])
        if self.failure == "nan":
            return np.asarray([[0.9, np.nan] for _ in matrix])
        return np.asarray([[0.9, 0.1] if row[2] == "music" else [0.98, 0.02] for row in matrix])


def test_expected_value_selection_saves_lower_bid_winner_with_one_model_batch(
    database: Database, inventory: Inventory
) -> None:
    estimator = Estimator()
    with database.session() as session:
        result = recommend(
            session,
            inventory.user_id,
            str(uuid4()),
            strategy=ExpectedValue(CTRModel(estimator, "fixture-model")),
        )
    assert result.selection is not None
    assert result.selection.id == inventory.music_id
    assert result.selection.bid == Decimal("1")
    assert result.selection.score == Decimal("0.1")
    assert result.selection.predicted_ctr == 0.1
    assert result.selection.strategy == "expected-value"
    assert result.selection.score_meaning == "expected_simulated_dollars_per_impression"
    assert result.selection.model_id == "fixture-model"
    assert result.selection.model_version == "ctr-logistic-v1"
    assert result.selection.feature_version == "ctr-features-v1"
    assert result.selection.shared_interest_count == 1
    assert result.selection.retrieval is not None
    assert result.selection.retrieval.returned_count == 2
    assert len(estimator.batches) == 1


def test_repeated_bid_changes_fail_after_three_attempts_without_saving_a_stale_decision(
    database: Database, inventory: Inventory
) -> None:
    estimator = Estimator()

    def edit() -> None:
        with database.transaction() as session:
            for ad_id in (inventory.music_id, inventory.cars_id):
                ad = session.get(Ad, ad_id)
                assert ad is not None
                ad.bid += Decimal("1")

    estimator.on_batch = edit
    strategy = ExpectedValue(CTRModel(estimator, "fixture"))
    key = str(uuid4())
    with database.session() as session:
        with pytest.raises(WorkflowError) as failure:
            recommend(session, inventory.user_id, key, strategy=strategy)
    assert failure.value.code == "inventory_changing" and failure.value.status_code == 503
    assert len(estimator.batches) == 3
    estimator.on_batch = None
    with database.session() as session:
        retry = recommend(session, inventory.user_id, key, strategy=strategy)
    assert retry.selection is not None
    assert retry.selection.id == inventory.music_id
    assert retry.selection.bid == Decimal("4")
    assert retry.selection.score == Decimal("0.4")


@pytest.mark.parametrize("failure", ["unavailable", "nan", "count", "exception"])
def test_http_ctr_failure_is_503_and_retry_can_use_baseline_without_invented_ctr(
    database: Database, database_settings: Settings, inventory: Inventory, failure: str
) -> None:
    estimator = Estimator()
    estimator.failure = failure
    model = CTRModel.unavailable() if failure == "unavailable" else CTRModel(estimator, "fixture")
    app = create_app(database_settings.model_copy(update={"ranking_strategy": "expected-value"}))

    def session_dependency() -> Iterator[Session]:
        with database.session() as session:
            yield session

    app.dependency_overrides[get_session] = session_dependency
    app.dependency_overrides[get_ctr_model] = lambda: model
    with TestClient(app) as client:
        key = str(uuid4())
        response = client.post(
            "/api/v1/recommendations",
            json={"user_id": inventory.user_id},
            headers={"Idempotency-Key": key},
        )
        assert response.status_code == 503
        assert response.json() == {
            "error": {"code": "ctr_unavailable", "message": "CTR model is unavailable"}
        }
        app.state.settings = database_settings
        baseline = client.post(
            "/api/v1/recommendations",
            json={"user_id": inventory.user_id},
            headers={"Idempotency-Key": key},
        )
        assert baseline.status_code == 200
        selected = baseline.json()["selection"]
        assert selected["id"] == inventory.cars_id
        assert selected["strategy"] == "interest-overlap"
        assert selected["predicted_ctr"] is None
        assert (
            selected["model_id"] is None
            and selected["model_version"] is None
            and selected["feature_version"] is None
        )
        app.state.settings = database_settings.model_copy(
            update={"ranking_strategy": "expected-value"}
        )
        assert (
            client.post(
                "/api/v1/recommendations",
                json={"user_id": inventory.user_id},
                headers={"Idempotency-Key": key},
            ).json()
            == baseline.json()
        )
    assert len(estimator.batches) == (0 if failure == "unavailable" else 1)


def test_http_empty_v2_inventory_is_replayable_no_ad_without_an_available_model(
    database: Database, database_settings: Settings, inventory: Inventory
) -> None:
    with database.transaction() as session:
        for ad_id in (inventory.music_id, inventory.cars_id):
            ad = session.get(Ad, ad_id)
            assert ad is not None
            ad.active = False
    app = create_app(database_settings.model_copy(update={"ranking_strategy": "expected-value"}))

    def session_dependency() -> Iterator[Session]:
        with database.session() as session:
            yield session

    app.dependency_overrides[get_session] = session_dependency
    with TestClient(app) as client:
        key = str(uuid4())
        response = client.post(
            "/api/v1/recommendations",
            json={"user_id": inventory.user_id},
            headers={"Idempotency-Key": key},
        )
        assert response.status_code == 204 and response.content == b""
        with database.transaction() as session:
            ad = session.get(Ad, inventory.music_id)
            assert ad is not None
            ad.active = True
        replay = client.post(
            "/api/v1/recommendations",
            json={"user_id": inventory.user_id},
            headers={"Idempotency-Key": key},
        )
        assert replay.status_code == 204 and replay.content == b""
        new_opportunity = client.post(
            "/api/v1/recommendations",
            json={"user_id": inventory.user_id},
            headers={"Idempotency-Key": str(uuid4())},
        )
        assert new_opportunity.status_code == 503


def test_http_zero_value_selection_replays_identical_decimal_score_and_model_context(
    database: Database, database_settings: Settings, inventory: Inventory
) -> None:
    with database.transaction() as session:
        for ad_id in (inventory.music_id, inventory.cars_id):
            ad = session.get(Ad, ad_id)
            assert ad is not None
            ad.bid = Decimal("0")
    model = CTRModel(Estimator(), "zero-model")
    app = create_app(database_settings.model_copy(update={"ranking_strategy": "expected-value"}))

    def session_dependency() -> Iterator[Session]:
        with database.session() as session:
            yield session

    app.dependency_overrides[get_session] = session_dependency
    app.dependency_overrides[get_ctr_model] = lambda: model
    with TestClient(app) as client:
        key = str(uuid4())
        first = client.post(
            "/api/v1/recommendations",
            json={"user_id": inventory.user_id},
            headers={"Idempotency-Key": key},
        )
        assert first.status_code == 200
        assert first.json()["selection"]["score"] == "0.00000"
        assert first.json()["selection"]["bid"] == "0.0000"
        model = CTRModel.unavailable()
        replay = client.post(
            "/api/v1/recommendations",
            json={"user_id": inventory.user_id},
            headers={"Idempotency-Key": key},
        )
        assert replay.json() == first.json()


@pytest.mark.parametrize(
    "change", ["bid", "interests", "category", "ad_active", "advertiser_active"]
)
def test_v2_retries_changed_winner_metadata_and_recomputes_a_coherent_selection(
    database: Database, inventory: Inventory, change: str
) -> None:
    estimator = Estimator()

    def edit() -> None:
        with database.transaction() as session:
            ad = session.get(Ad, inventory.music_id)
            assert ad is not None
            if change == "bid":
                ad.bid = Decimal("0")
            elif change == "interests":
                ad.interests = []
            elif change == "category":
                ad.category = "cars"
            elif change == "ad_active":
                ad.active = False
            else:
                advertiser = session.get(Advertiser, ad.advertiser_id)
                assert advertiser is not None
                advertiser.active = False

    estimator.on_first_batch = edit
    with database.session() as session:
        result = recommend(
            session,
            inventory.user_id,
            str(uuid4()),
            strategy=ExpectedValue(CTRModel(estimator, "fixture-model")),
        )
    if change == "advertiser_active":
        assert result.selection is None
        assert len(estimator.batches) == 1
    else:
        assert result.selection is not None
        if change == "interests":
            assert result.selection.id == inventory.music_id
            assert result.selection.shared_interest_count == 0
            assert result.selection.score == Decimal("0.1")
        else:
            assert result.selection.id == inventory.cars_id
            assert result.selection.bid == Decimal("3")
            assert result.selection.predicted_ctr == 0.02
            assert result.selection.score == Decimal("0.06")
        assert len(estimator.batches) == 2


def test_replay_keeps_saved_v2_context_after_bid_model_and_strategy_change_and_click_credits_bid(
    database: Database, inventory: Inventory
) -> None:
    estimator = Estimator()
    key = str(uuid4())
    with database.session() as session:
        saved = recommend(
            session,
            inventory.user_id,
            key,
            strategy=ExpectedValue(CTRModel(estimator, "original-model")),
        )
    assert saved.selection is not None and saved.recommendation_id is not None
    with database.transaction() as session:
        ad = session.get(Ad, saved.selection.id)
        assert ad is not None
        ad.bid = Decimal("99")
        ad.active = False
        ad.category = "cars"
    for strategy in (None, ExpectedValue(CTRModel.unavailable())):
        with database.session() as session:
            replay = recommend(session, inventory.user_id, key, strategy=strategy)
        assert replay == saved
    with database.session() as session:
        record_event(session, saved.recommendation_id, "impression")
        clicked = record_event(session, saved.recommendation_id, "click")
        duplicate = record_event(session, saved.recommendation_id, "click")
    assert clicked == duplicate
    assert clicked.simulated_revenue == Decimal("1")
    assert clicked.simulated_revenue != saved.selection.score
    assert len(estimator.batches) == 1


def test_http_selects_configured_v2_and_returns_explicit_saved_context(
    database: Database, database_settings: Settings, inventory: Inventory
) -> None:
    estimator = Estimator()
    model = CTRModel(estimator, "fixture-model")
    app = create_app(database_settings.model_copy(update={"ranking_strategy": "expected-value"}))

    def session_dependency() -> Iterator[Session]:
        with database.session() as session:
            yield session

    app.dependency_overrides[get_session] = session_dependency
    app.dependency_overrides[get_ctr_model] = lambda: model
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/recommendations",
            json={"user_id": inventory.user_id},
            headers={"Idempotency-Key": str(uuid4())},
        )
    assert response.status_code == 200
    selected = response.json()["selection"]
    assert selected["id"] == inventory.music_id
    assert selected["score"] == "0.10000"
    assert selected["bid"] == "1.0000"
    assert selected["predicted_ctr"] == 0.1
    assert selected["strategy"] == "expected-value"
    assert selected["strategy_version"] == "expected-value-v1"
    assert selected["score_meaning"] == "expected_simulated_dollars_per_impression"
    assert selected["model_id"] == "fixture-model"
    assert selected["model_version"] == "ctr-logistic-v1"
    assert selected["feature_version"] == "ctr-features-v1"
    assert selected["retrieval"]["requested_count"] == 500
    assert len(estimator.batches) == 1

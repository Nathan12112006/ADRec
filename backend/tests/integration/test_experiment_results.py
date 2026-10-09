from collections.abc import Iterator
from datetime import datetime, timedelta
from decimal import Decimal
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.dependencies import get_clock, get_session
from app.core.clock import utc_now
from app.core.config import Settings
from app.db.session import Database
from app.main import create_app
from app.models.records import Event, Experiment, Recommendation, RequestOutcome
from app.seeding import SeedConfig, generate_entities, seed_database


def test_results_use_recommendation_cohorts_late_events_and_nullable_ratios(
    database: Database, database_settings: Settings
) -> None:
    config = SeedConfig(seed=uuid4().int % 2**62, users=2, advertisers=1, ads=2)
    seed_database(database, config, append=True)
    entities = list(generate_entities(config))
    users = [int(row["id"]) for kind, row in entities if kind == "users"]
    ads = [int(row["id"]) for kind, row in entities if kind == "ads"]
    control_user, treatment_user = users
    now = utc_now()
    recommendation_time = now - timedelta(hours=26)
    experiment_id = uuid4()
    control_recommendation = uuid4()
    treatment_recommendation = uuid4()
    with database.transaction() as session:
        experiment = Experiment(
            id=experiment_id,
            name="Cohort results",
            model_id="d" * 64,
            created_at=recommendation_time - timedelta(minutes=2),
        )
        session.add(experiment)
        session.flush()
        experiment.status = "running"
        experiment.started_at = recommendation_time - timedelta(minutes=1)
        session.flush()
        experiment.status = "stopped"
        experiment.stopped_at = now - timedelta(hours=1)
        session.add_all(
            [
                Recommendation(
                    id=control_recommendation,
                    dataset_id=config.dataset_id,
                    user_id=control_user,
                    ad_id=ads[0],
                    bid=Decimal("0.50"),
                    selected_ad={"retrieval": {"mode": "exact", "fallback_reason": None}},
                    experiment_id=experiment_id,
                    experiment_variant="control",
                    created_at=recommendation_time,
                ),
                Recommendation(
                    id=treatment_recommendation,
                    dataset_id=config.dataset_id,
                    user_id=treatment_user,
                    ad_id=ads[1],
                    bid=Decimal("1.25"),
                    selected_ad={
                        "retrieval": {
                            "mode": "exact_fallback",
                            "fallback_reason": "missing_index",
                        }
                    },
                    experiment_id=experiment_id,
                    experiment_variant="treatment",
                    created_at=recommendation_time + timedelta(seconds=30),
                ),
            ]
        )
        session.flush()
        session.add_all(
            [
                RequestOutcome(
                    request_key=f"control-selected-{uuid4()}",
                    user_id=control_user,
                    recommendation_id=control_recommendation,
                    experiment_id=experiment_id,
                    experiment_variant="control",
                    created_at=recommendation_time,
                ),
                RequestOutcome(
                    request_key=f"control-no-ad-{uuid4()}",
                    user_id=control_user,
                    recommendation_id=None,
                    experiment_id=experiment_id,
                    experiment_variant="control",
                    created_at=recommendation_time + timedelta(minutes=1),
                ),
                RequestOutcome(
                    request_key=f"treatment-selected-{uuid4()}",
                    user_id=treatment_user,
                    recommendation_id=treatment_recommendation,
                    experiment_id=experiment_id,
                    experiment_variant="treatment",
                    created_at=recommendation_time + timedelta(seconds=30),
                ),
            ]
        )
        session.add_all(
            [
                Event(
                    recommendation_id=treatment_recommendation,
                    event_type="impression",
                    created_at=recommendation_time + timedelta(hours=23),
                    simulated_revenue=Decimal("0"),
                ),
                Event(
                    recommendation_id=treatment_recommendation,
                    event_type="click",
                    created_at=recommendation_time + timedelta(hours=23, minutes=30),
                    simulated_revenue=Decimal("1.25"),
                ),
            ]
        )

    app = create_app(database_settings)

    def session_dependency() -> Iterator[Session]:
        with database.session() as session:
            yield session

    app.dependency_overrides[get_session] = session_dependency
    app.dependency_overrides[get_clock] = lambda: lambda: now
    cohort_start = recommendation_time - timedelta(minutes=1)
    cohort_end = recommendation_time + timedelta(minutes=3)
    with TestClient(app) as client:
        event_body = {"recommendation_id": str(treatment_recommendation)}
        assert client.post("/api/v1/events/impression", json=event_body).status_code == 200
        assert client.post("/api/v1/events/click", json=event_body).status_code == 200
        app.dependency_overrides[get_clock] = lambda: lambda: now - timedelta(hours=24)
        before_events = client.get(
            f"/api/v1/experiments/{experiment_id}/results",
            params={"start_at": cohort_start.isoformat(), "end_at": cohort_end.isoformat()},
        )
        assert before_events.status_code == 200
        assert before_events.json()["variants"]["treatment"]["impressions"] == 0
        assert before_events.json()["variants"]["treatment"]["clicks"] == 0
        app.dependency_overrides[get_clock] = lambda: lambda: now
        response = client.get(
            f"/api/v1/experiments/{experiment_id}/results",
            params={"start_at": cohort_start.isoformat(), "end_at": cohort_end.isoformat()},
        )
        assert response.status_code == 200, response.text
        result = response.json()
        control = result["variants"]["control"]
        treatment = result["variants"]["treatment"]
        assert result["synthetic"] is True
        assert result["provisional"] is False
        assert (
            datetime.fromisoformat(result["cohort_end_exclusive"].replace("Z", "+00:00"))
            == cohort_end
        )
        assert control["attempts"] == 2 and control["no_ad_outcomes"] == 1
        assert control["attempted_users"] == 1
        assert control["recommendations"] == 1
        assert control["impressions"] == control["clicks"] == 0
        assert control["ctr"] is None and control["revenue_per_exposed_user"] is None
        assert treatment["recommendations"] == 1
        assert treatment["exposed_users"] == treatment["impressions"] == 1
        assert treatment["clicks"] == 1
        assert Decimal(treatment["simulated_revenue"]) == Decimal("1.25")
        assert Decimal(treatment["ctr"]) == Decimal("1")
        assert treatment["fallbacks"] == [
            {"mode": "exact_fallback", "reason": "missing_index", "count": 1}
        ]
        assert result["comparison"]["ctr"]["relative_lift_percent"] is None
        assert result["comparison"]["simulated_revenue"]["relative_lift_percent"] is None
        assert result["telemetry"]["coverage_complete"] is False
        assert client.get(f"/api/v1/experiments/{uuid4()}/results").status_code == 404


def test_empty_running_experiment_results_are_provisional_with_null_ratios(
    database: Database, database_settings: Settings
) -> None:
    identity = uuid4()
    with database.transaction() as session:
        experiment = Experiment(id=identity, name="Empty running", model_id="e" * 64)
        session.add(experiment)
        session.flush()
        experiment.status = "running"
        experiment.started_at = experiment.created_at

    app = create_app(database_settings)

    def session_dependency() -> Iterator[Session]:
        with database.session() as session:
            yield session

    app.dependency_overrides[get_session] = session_dependency
    with TestClient(app) as client:
        response = client.get(f"/api/v1/experiments/{identity}/results")
    assert response.status_code == 200
    result = response.json()
    assert result["provisional"] is True
    for variant in ("control", "treatment"):
        metrics = result["variants"][variant]
        assert metrics["recommendations"] == 0
        assert metrics["impressions"] == metrics["clicks"] == 0
        assert metrics["ctr"] is None
        assert metrics["revenue_per_exposed_user"] is None
    with database.transaction() as session:
        saved_experiment = session.get(Experiment, identity)
        assert saved_experiment is not None
        saved_experiment.status = "stopped"
        saved_experiment.stopped_at = utc_now()

"""Save actual ASGI HTTP responses with real PostgreSQL/startup dependencies."""

import json
import platform
import sys
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

from alembic import command
from alembic.config import Config
from app.core.config import load_settings
from app.db.session import Database
from app.main import create_app
from app.models.records import Ad, Advertiser, User
from app.seeding import SeedConfig, seed_database
from fastapi.testclient import TestClient
from sqlalchemy import select

settings = load_settings(env_file=None)
assert settings.database_url.get_secret_value().endswith("/adflow_ticket26_examples")
config = Config(
    str(Path(__import__("app").__file__).resolve().parents[1] / "alembic.ini")
)
config.attributes["settings"] = settings
command.upgrade(config, "head")
database = Database(settings)
seed = SeedConfig(seed=uuid4().int % 2**62, users=1, advertisers=1, ads=2)
seed_database(database, seed, append=True)
with database.transaction() as session:
    user = session.scalar(select(User).where(User.dataset_id == seed.dataset_id))
    advertiser = session.scalar(
        select(Advertiser).where(Advertiser.dataset_id == seed.dataset_id)
    )
    assert user is not None and advertiser is not None
    user.interests, user.device, user.age_group = ["music"], "mobile", "25-34"
    user_id = user.id
    advertiser.active = True
    ads = list(
        session.scalars(
            select(Ad).where(Ad.dataset_id == seed.dataset_id).order_by(Ad.id)
        )
    )
    for ad, category, bid in zip(ads, ("music", "cars"), ("0", "100"), strict=True):
        ad.active, ad.interests, ad.category, ad.bid = (
            True,
            [category],
            category,
            Decimal(bid),
        )
    ad_ids = [ad.id for ad in ads]
examples = {}
keys = {}
for strategy in ("interest-overlap", "expected-value"):
    keys[strategy] = str(uuid4())
    app_settings = settings.model_copy(
        update={
            "ranking_strategy": strategy,
            "ctr_model_path": Path(sys.argv[1]).resolve()
            if strategy == "expected-value"
            else None,
            "retrieval_index_path": None,
        }
    )
    with TestClient(create_app(app_settings)) as client:
        response = client.post(
            "/api/v1/recommendations",
            json={"user_id": user_id},
            headers={"Idempotency-Key": keys[strategy]},
        )
        assert response.status_code == 200
        first = response.json()
        selected = first["selection"]
        assert selected["retrieval"]["returned_count"] == 2
        assert selected["strategy"] == strategy
        if strategy == "interest-overlap":
            assert selected["id"] == ad_ids[0] and selected["score"] == 1
            assert selected["predicted_ctr"] is None and selected["model_id"] is None
        else:
            assert selected["id"] == ad_ids[1] and Decimal(selected["score"]) > 0
            assert selected["model_id"] and selected["predicted_ctr"] > 0
        examples[strategy] = {"status": response.status_code, "first": first}
with database.transaction() as session:
    for ad_id in ad_ids:
        ad = session.get(Ad, ad_id)
        assert ad is not None
        ad.bid, ad.active = Decimal(999), False
unavailable = settings.model_copy(
    update={
        "ranking_strategy": "expected-value",
        "ctr_model_path": None,
        "retrieval_index_path": None,
    }
)
with TestClient(create_app(unavailable)) as client:
    for strategy, example in examples.items():
        replay = client.post(
            "/api/v1/recommendations",
            json={"user_id": user_id},
            headers={"Idempotency-Key": keys[strategy]},
        )
        assert replay.status_code == 200 and replay.json() == example["first"]
        body = {"recommendation_id": example["first"]["recommendation_id"]}
        assert client.post("/api/v1/events/impression", json=body).status_code == 200
        click = client.post("/api/v1/events/click", json=body)
        duplicate = client.post("/api/v1/events/click", json=body)
        assert (
            click.status_code == duplicate.status_code == 200
            and click.json() == duplicate.json()
        )
        assert Decimal(click.json()["simulated_revenue"]) == Decimal(
            example["first"]["selection"]["bid"]
        )
        example.update(
            {"replay_equal": True, "duplicate_click_equal": True, "click": click.json()}
        )
database.dispose()
report = {
    "passed": True,
    "python": platform.python_version(),
    "dataset_id": str(seed.dataset_id),
    "examples": examples,
    "scope": "In-process TestClient HTTP/ASGI requests; real startup, model and PostgreSQL, no dependency overrides. Not a socket/latency benchmark.",
}
with Path(sys.argv[2]).open("x", encoding="utf-8") as stream:
    json.dump(report, stream, indent=2, sort_keys=True)
print(json.dumps({"passed": True, "strategies": list(examples)}))

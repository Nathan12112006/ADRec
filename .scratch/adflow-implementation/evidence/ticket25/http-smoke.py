"""Run actual HTTP selection/replay/accounting against an explicitly isolated database."""

import json
import os
import platform
import socket
import subprocess
import sys
import time
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from uuid import UUID, uuid4

from alembic import command
from alembic.config import Config
from app.core.config import load_settings
from app.ctr.artifacts import package_model
from app.ctr.dataset import write_feature_splits
from app.ctr.evaluation import evaluate
from app.ctr.training import TrainingConfig, train
from app.db.session import Database
from app.history.artifacts import HistoryConfig, HistorySource, write_history
from app.models.records import Ad, Advertiser, User
from app.seeding import SeedConfig, seed_database
from sqlalchemy import select


def prepare_bundle(root: Path) -> Path:
    source = HistorySource(
        dataset_id=UUID(int=25),
        entity_manifest={"generator_version": "fixture"},
        users=(
            {
                "id": 1,
                "interests": ["music"],
                "category_preferences": ["music"],
                "device": "mobile",
                "age_group": "25-34",
            },
        ),
        ads=tuple(
            {
                "id": index,
                "interests": [category],
                "category": category,
                "bid": "1",
                "active": True,
                "advertiser_active": True,
            }
            for index, category in enumerate(("music", "cars"), 1)
        ),
    )
    write_history(source, root / "history", HistoryConfig(impressions=10000))
    write_feature_splits(root / "history", root / "features")
    train(root / "features", root / "model", TrainingConfig())
    evaluate(root / "features", root / "model", root / "evaluation")
    package_model(root / "model", root / "evaluation", root / "bundle")
    return root / "bundle"


settings = load_settings(env_file=None)
assert settings.database_url.get_secret_value().endswith("/adflow_ticket25_test")
database = Database(settings)
for attempt in range(30):
    try:
        with database.engine.connect():
            break
    except Exception:
        if attempt == 29:
            raise
        time.sleep(1)
config = Config(
    str(Path(__import__("app").__file__).resolve().parents[1] / "alembic.ini")
)
config.attributes["settings"] = settings
command.upgrade(config, "head")
seed = SeedConfig(seed=uuid4().int % 2**62, users=1, advertisers=1, ads=2)
seed_database(database, seed, append=True)
with database.transaction() as session:
    user = session.scalar(select(User).where(User.dataset_id == seed.dataset_id))
    assert user is not None
    user.interests, user.device, user.age_group = ["music"], "mobile", "25-34"
    user_id = user.id
    advertiser = session.scalar(
        select(Advertiser).where(Advertiser.dataset_id == seed.dataset_id)
    )
    assert advertiser is not None
    advertiser.active = True
    ads = list(
        session.scalars(
            select(Ad).where(Ad.dataset_id == seed.dataset_id).order_by(Ad.id)
        )
    )
    for ad, category, bid in zip(ads, ("music", "cars"), ("1", "2"), strict=True):
        ad.active, ad.interests, ad.category, ad.bid = (
            True,
            [category],
            category,
            Decimal(bid),
        )
    music_id = ads[0].id

with TemporaryDirectory() as directory:
    root = Path(directory)
    bundle = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else prepare_bundle(root)
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    environment = {
        **os.environ,
        "ADFLOW_CTR_MODEL_PATH": str(bundle),
        "ADFLOW_RANKING_STRATEGY": "expected-value",
    }
    with (root / "server.log").open("w+") as server_log:
        server = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "app.main:create_app",
                "--factory",
                "--host",
                "127.0.0.1",
                "--port",
                str(port),
            ],
            env=environment,
            stdout=server_log,
            stderr=subprocess.STDOUT,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        try:
            for attempt in range(100):
                try:
                    with urlopen(f"http://127.0.0.1:{port}/health/live", timeout=1):
                        break
                except (URLError, TimeoutError):
                    if server.poll() is not None or attempt == 99:
                        raise
                    time.sleep(0.1)

            def post(path: str, body: dict, key: str | None = None) -> dict:
                headers = {"Content-Type": "application/json"}
                if key:
                    headers["Idempotency-Key"] = key
                request = Request(
                    f"http://127.0.0.1:{port}/api/v1/{path}",
                    data=json.dumps(body).encode(),
                    headers=headers,
                )
                try:
                    response = urlopen(request, timeout=10)
                except HTTPError as error:
                    response = error
                with response:
                    assert response.status == 200
                    return json.load(response)

            key = str(uuid4())
            first = post("recommendations", {"user_id": user_id}, key)
            selected = first["selection"]
            assert (
                selected["id"] == music_id and selected["strategy"] == "expected-value"
            )
            assert (
                selected["model_id"]
                and selected["feature_version"] == "ctr-features-v1"
            )
            with database.transaction() as session:
                ad = session.get(Ad, selected["id"])
                assert ad is not None
                ad.bid, ad.active = Decimal(99), False
            replay = post("recommendations", {"user_id": user_id}, key)
            assert replay == first
            event_body = {"recommendation_id": first["recommendation_id"]}
            post("events/impression", event_body)
            clicked = post("events/click", event_body)
            assert post("events/click", event_body) == clicked
            assert Decimal(clicked["simulated_revenue"]) == Decimal(1)
            assert Decimal(selected["score"]) != Decimal(clicked["simulated_revenue"])
            result = {
                "passed": True,
                "python": platform.python_version(),
                "dataset_id": str(seed.dataset_id),
                "first": first,
                "replay_equal": True,
                "click": clicked,
                "duplicate_click_equal": True,
                "limitation": "Isolated HTTP correctness smoke; no performance or observed CTR/revenue lift claim",
            }
        finally:
            if os.name == "nt":
                subprocess.run(
                    ["taskkill", "/PID", str(server.pid), "/T", "/F"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.STDOUT,
                    check=True,
                )
            else:
                server.terminate()
            try:
                server.wait(timeout=10)
            except subprocess.TimeoutExpired:
                server.kill()
                server.wait(timeout=5)
        server_log.seek(0)
        assert "Logging error" not in server_log.read()
database.dispose()
print(json.dumps(result, sort_keys=True))

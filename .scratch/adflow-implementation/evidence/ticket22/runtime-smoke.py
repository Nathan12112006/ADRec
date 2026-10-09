"""Train/evaluate/package through offline CLIs, then check resident app/adapter predictions."""

import asyncio
import hashlib
import json
import platform
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import UUID

import numpy as np
from app.core.config import Settings
from app.ctr.dataset import write_feature_splits
from app.ctr.serving import CTRModel, CTRUnavailable
from app.history.artifacts import HistoryConfig, HistorySource, write_history
from app.main import create_app


def command(module: str, *arguments: str) -> dict:
    result = subprocess.run(
        [sys.executable, "-m", module, *arguments],
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(result.stdout)


async def application_check(bundle: Path) -> None:
    app = create_app(
        Settings(
            database_url="postgresql+psycopg://demo:demo@localhost/adflow",
            test_database_url="postgresql+psycopg://demo:demo@localhost/adflow_test",
            ctr_model_path=bundle,
        )
    )
    async with app.router.lifespan_context(app):
        expected = app.state.ctr_model.predict_one({}, {"id": 1})
        for path in bundle.iterdir():
            path.unlink()
        assert app.state.ctr_model.predict_one({}, {"id": 1}) == expected
    async with app.router.lifespan_context(app):
        try:
            app.state.ctr_model.predict_one({}, {"id": 1})
        except CTRUnavailable as error:
            assert error.status_code == 503
        else:
            raise AssertionError("A new startup must revalidate its missing artifact")


source = HistorySource(
    dataset_id=UUID(int=22),
    entity_manifest={"generator_version": "fixture"},
    users=(
        {
            "id": 1,
            "interests": ["music"],
            "category_preferences": [],
            "device": "mobile",
            "age_group": "25-34",
        },
    ),
    ads=(
        {
            "id": 2,
            "interests": ["music"],
            "category": "music",
            "bid": "1",
            "active": True,
            "advertiser_active": True,
        },
    ),
)
with TemporaryDirectory() as directory:
    root = Path(directory)
    write_history(source, root / "history", HistoryConfig(impressions=1000))
    write_feature_splits(root / "history", root / "features")
    trained = command(
        "app.ctr.training",
        "--features",
        str(root / "features"),
        "--output",
        str(root / "model"),
    )
    command(
        "app.ctr.evaluation",
        "--features",
        str(root / "features"),
        "--model",
        str(root / "model"),
        "--output",
        str(root / "evaluation"),
    )
    manifests = [
        command(
            "app.ctr.artifacts",
            "--model",
            str(root / "model"),
            "--evaluation",
            str(root / "evaluation"),
            "--output",
            str(root / name),
        )
        for name in ("first", "repeat")
    ]
    assert manifests[0] == manifests[1]
    assert (
        hashlib.sha256((root / "first/pipeline.joblib").read_bytes()).hexdigest()
        == trained["artifact"]["sha256"]
    )
    model = CTRModel.load(root / "first")
    ads = [
        {"id": 3, "category": "unseen"},
        {"id": 1, "interests": ["music"], "category": "music"},
    ]
    batch = model.predict_batch({}, ads)
    assert batch.ad_ids == (3, 1)
    assert np.isfinite(batch.probabilities).all()
    assert all(0 <= probability <= 1 for probability in batch.probabilities)
    np.testing.assert_allclose(
        np.asarray(batch.probabilities),
        np.asarray([model.predict_one({}, ad) for ad in ads]),
        rtol=0,
        atol=1e-12,
    )
    assert CTRModel.unavailable().predict_batch({}, []).probabilities == ()
    asyncio.run(application_check(root / "first"))
    foreign_rejected = None
    if len(sys.argv) > 1:
        try:
            CTRModel.load(Path(sys.argv[1]))
        except CTRUnavailable:
            foreign_rejected = True
        else:
            raise AssertionError("Foreign Python runtime artifact should be rejected")
    print(
        json.dumps(
            {
                "passed": True,
                "python": platform.python_version(),
                "repeat_equal": True,
                "startup_resident": True,
                "foreign_runtime_rejected": foreign_rejected,
                "bundle_id": manifests[0]["bundle_id"],
                "model_id": trained["model_id"],
                "probabilities": batch.probabilities,
            },
            sort_keys=True,
        )
    )

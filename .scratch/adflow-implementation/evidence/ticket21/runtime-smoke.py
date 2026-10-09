"""Exercise public frozen evaluation twice; no assertions depend on predictive lift."""

import hashlib
import json
import platform
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import UUID

from app.ctr.dataset import write_feature_splits
from app.ctr.training import TrainingConfig, train
from app.history.artifacts import HistoryConfig, HistorySource, write_history

source = HistorySource(
    dataset_id=UUID(int=21),
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
    manifest = train(root / "features", root / "model", TrainingConfig())
    paths = list((root / "features").iterdir()) + list((root / "model").iterdir())
    before = {
        str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in paths
    }
    reports = []
    for name in ("first", "repeat"):
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "app.ctr.evaluation",
                "--features",
                str(root / "features"),
                "--model",
                str(root / "model"),
                "--output",
                str(root / name),
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        report = json.loads(result.stdout)
        assert report["status"] == "complete"
        assert report["baseline"]["probability"] == manifest["training_base_rate"]
        for cohort in report["splits"].values():
            assert cohort["model"]["count"] == cohort["baseline"]["count"] == 150
            assert cohort["model"]["clicks"] == cohort["baseline"]["clicks"]
            for predictor in ("model", "baseline"):
                assert (
                    sum(row["count"] for row in cohort[predictor]["reliability"]) == 150
                )
        reports.append(report)
    assert reports[0] == reports[1]
    assert before == {
        str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in paths
    }
    print(
        json.dumps(
            {
                "passed": True,
                "python": platform.python_version(),
                "repeat_equal": True,
                "inputs_unchanged": True,
                "report": reports[0],
            },
            sort_keys=True,
        )
    )

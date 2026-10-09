import json
import platform
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import UUID

import joblib
import numpy as np
from app.ctr.dataset import write_feature_splits
from app.ctr.features import build_features
from app.ctr.inputs import feature_matrix
from app.history.artifacts import HistoryConfig, HistorySource, write_history

source = HistorySource(
    dataset_id=UUID(int=20),
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
            "bid": "99",
            "active": True,
            "advertiser_active": True,
        },
    ),
)
with TemporaryDirectory() as directory:
    root = Path(directory)
    write_history(source, root / "history", HistoryConfig(impressions=1000))
    write_feature_splits(root / "history", root / "features")
    manifests = []
    for name in ("first", "repeat"):
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "app.ctr.training",
                "--features",
                str(root / "features"),
                "--output",
                str(root / name),
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        manifests.append(json.loads(result.stdout))
    assert manifests[0] == manifests[1]
    pipeline = joblib.load(root / "first/pipeline.joblib")
    probabilities = pipeline.predict_proba(feature_matrix([build_features({}, {})]))
    assert probabilities.shape == (1, 2)
    assert np.isfinite(probabilities).all()
    assert ((0 <= probabilities) & (probabilities <= 1)).all()
    print(
        json.dumps(
            {
                "passed": True,
                "python": platform.python_version(),
                "repeat_equal": True,
                "manifest": manifests[0],
            },
            sort_keys=True,
        )
    )

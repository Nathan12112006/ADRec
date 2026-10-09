import hashlib
import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import joblib  # type: ignore[import-untyped]
import numpy as np
import pytest

from app.ctr.dataset import FEATURE_SCHEMA, SPLIT_VERSION
from app.ctr.features import FEATURE_VERSION, build_features
from app.ctr.inputs import feature_matrix
from app.ctr.training import TrainingConfig, train


def dataset(path: Path) -> None:
    path.mkdir()
    files = {}
    splits = {}
    start = 0
    for name, count in (("train", 70), ("validation", 15), ("test", 15)):
        rows: list[dict[str, Any]] = []
        for index in range(start, start + count):
            rows.append(
                {
                    "impression_id": index,
                    "impressed_at": (
                        datetime(2026, 1, 1, tzinfo=timezone.utc) + timedelta(seconds=index)
                    ).isoformat(),
                    "features": {
                        "shared_interest_count": index % 3,
                        "category_match": index % 2 == 0,
                        "ad_category": "music",
                        "device_type": "mobile",
                        "age_group": "25-34",
                    },
                    "label": int(index % 5 == 0),
                }
            )
        data = "".join(json.dumps(row) + "\n" for row in rows).encode()
        (path / f"{name}.jsonl").write_bytes(data)
        files[f"{name}.jsonl"] = hashlib.sha256(data).hexdigest()
        splits[name] = {
            "count": count,
            "clicks": sum(row["label"] for row in rows),
            "start_inclusive": start,
            "end_exclusive": start + count,
            "first": {key: rows[0][key] for key in ("impression_id", "impressed_at")},
            "last": {key: rows[-1][key] for key in ("impression_id", "impressed_at")},
        }
        start += count
    manifest = {
        "status": "complete",
        "feature_version": FEATURE_VERSION,
        "split_version": SPLIT_VERSION,
        "feature_schema": FEATURE_SCHEMA,
        "source": {"history_id": "fixture", "dataset_id": "fixture"},
        "files": files,
        "splits": splits,
    }
    (path / "manifest.json").write_text(json.dumps(manifest))


def test_training_exports_whole_fitted_pipeline_with_reproducible_provenance(
    tmp_path: Path,
) -> None:
    dataset(tmp_path / "data")
    first = train(tmp_path / "data", tmp_path / "model", TrainingConfig())
    repeat = train(tmp_path / "data", tmp_path / "repeat", TrainingConfig())
    assert first == repeat
    assert first["class_counts"]["train"] == {"0": 56, "1": 14}
    assert first["selection"]["metric"] == "validation_log_loss"
    assert [row["C"] for row in first["selection"]["candidates"]] == [0.1, 1.0, 10.0]
    assert first["feature_version"] == FEATURE_VERSION
    assert first["dependencies"]["scikit-learn"] == "1.7.2"
    pipeline = joblib.load(tmp_path / "model/pipeline.joblib")
    fixture = np.array(
        [[0, False, "music", "mobile", "25-34"], [0, False, "unseen", "unseen", "__missing__"]],
        dtype=object,
    )
    probabilities = pipeline.predict_proba(fixture)
    assert probabilities.shape == (2, 2)
    assert np.isfinite(probabilities).all()
    np.testing.assert_allclose(probabilities.sum(axis=1), [1.0, 1.0], atol=1e-12)
    np.testing.assert_allclose(
        probabilities,
        joblib.load(tmp_path / "repeat/pipeline.joblib").predict_proba(fixture),
        rtol=0,
        atol=1e-12,
    )


def test_incomplete_feature_manifest_is_actionably_rejected(tmp_path: Path) -> None:
    dataset(tmp_path / "data")
    path = tmp_path / "data/manifest.json"
    manifest = json.loads(path.read_text())
    manifest["splits"] = {}
    path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="splits"):
        train(tmp_path / "data", tmp_path / "bad", TrainingConfig())
    assert not (tmp_path / "bad/manifest.json").exists()


def rewrite_split(path: Path, name: str, records: list[dict[str, Any]]) -> None:
    data = "".join(json.dumps(row) + "\n" for row in records).encode()
    (path / f"{name}.jsonl").write_bytes(data)
    manifest_path = path / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["files"][f"{name}.jsonl"] = hashlib.sha256(data).hexdigest()
    manifest["splits"][name]["clicks"] = sum(row["label"] for row in records)
    manifest_path.write_text(json.dumps(manifest))


def records(path: Path, split: str) -> list[dict[str, Any]]:
    return [json.loads(line) for line in (path / f"{split}.jsonl").read_text().splitlines()]


def test_validation_never_fits_preprocessing_or_estimator(tmp_path: Path) -> None:
    path = tmp_path / "data"
    dataset(path)
    config = TrainingConfig(regularization=(1.0,))
    train(path, tmp_path / "first", config)
    changed = records(path, "validation")
    for row in changed:
        row["features"].update(
            shared_interest_count=10000,
            ad_category="validation-only",
            age_group="validation-only",
            device_type="validation-only",
        )
        row["label"] = 1
    rewrite_split(path, "validation", changed)
    manifest = train(path, tmp_path / "changed", config)
    assert manifest["class_counts"]["validation"] == {"0": 0, "1": 15}
    assert (tmp_path / "first/pipeline.joblib").read_bytes() == (
        tmp_path / "changed/pipeline.joblib"
    ).read_bytes()


def test_final_test_file_is_not_read_for_training_or_selection(tmp_path: Path) -> None:
    path = tmp_path / "data"
    dataset(path)
    first = train(path, tmp_path / "first", TrainingConfig())
    (path / "test.jsonl").write_text("this is deliberately not JSON or valid held-out data")
    second = train(path, tmp_path / "second", TrainingConfig())
    assert first == second


def test_training_requires_both_classes_with_counts_and_actionable_error(tmp_path: Path) -> None:
    path = tmp_path / "data"
    dataset(path)
    changed = records(path, "train")
    for row in changed:
        row["label"] = 0
    rewrite_split(path, "train", changed)
    with pytest.raises(ValueError, match="both labels.*class_counts=.*generate more history"):
        train(path, tmp_path / "bad", TrainingConfig())
    assert not (tmp_path / "bad/manifest.json").exists()


def test_real_convergence_failure_cannot_export_complete_pipeline(tmp_path: Path) -> None:
    dataset(tmp_path / "data")
    with pytest.raises(ValueError, match="did not converge.*increase max_iter.*class_counts"):
        train(tmp_path / "data", tmp_path / "bad", TrainingConfig(max_iter=1))
    status = json.loads((tmp_path / "bad/status.json").read_text())
    assert status["status"] == "failed"
    assert "C=0.1" in status["reason"]
    assert not (tmp_path / "bad/manifest.json").exists()


@pytest.mark.parametrize(
    "change",
    [
        {"label": 2},
        {"label": True},
        {"label": None},
        {"impression_id": 0},
        {"impressed_at": "2026-01-01T00:00:00"},
        {"features": {"bid": 5.0}},
    ],
)
def test_invalid_labels_features_and_cross_split_identity_are_rejected(
    tmp_path: Path, change: dict[str, Any]
) -> None:
    path = tmp_path / "data"
    dataset(path)
    changed = records(path, "validation")
    changed[0].update(change)
    # Invalid/nonbinary labels must be rejected before checking the original click count.
    (path / "validation.jsonl").write_text("".join(json.dumps(row) + "\n" for row in changed))
    with pytest.raises(ValueError):
        train(path, tmp_path / "bad", TrainingConfig())
    assert not (tmp_path / "bad/manifest.json").exists()


@pytest.mark.parametrize(
    "settings",
    [
        {"regularization": ()},
        {"regularization": (0.0,)},
        {"regularization": (float("nan"),)},
        {"regularization": (1.0, 0.1)},
        {"regularization": (1.0, 1.0)},
        {"max_iter": 0},
        {"seed": -1},
        {"tolerance": 0},
    ],
)
def test_invalid_training_configuration_is_rejected(settings: dict[str, Any]) -> None:
    with pytest.raises(ValueError):
        TrainingConfig(**settings)


def test_exported_pipeline_accepts_shared_builder_features_and_prediction_fixture(
    tmp_path: Path,
) -> None:
    dataset(tmp_path / "data")
    manifest = train(tmp_path / "data", tmp_path / "model", TrainingConfig())
    pipeline = joblib.load(tmp_path / "model/pipeline.joblib")
    inputs = feature_matrix(
        [
            build_features({"interests": []}, {}),
            build_features(
                {"interests": ["music"], "device": "mobile", "age_group": "25-34"},
                {"interests": ["music"], "category": "music"},
            ),
        ]
    )
    probabilities = pipeline.predict_proba(inputs)
    assert probabilities.shape == (2, 2)
    assert np.isfinite(probabilities).all()
    assert ((0 <= probabilities) & (probabilities <= 1)).all()
    fixture = manifest["prediction_fixture"]
    np.testing.assert_allclose(
        pipeline.predict_proba(np.asarray(fixture["rows"], dtype=object)),
        fixture["probabilities"],
        rtol=0,
        atol=1e-12,
    )


def test_offline_cli_records_config_and_preserves_existing_artifact(tmp_path: Path) -> None:
    dataset(tmp_path / "data")
    config = tmp_path / "config.json"
    config.write_text(json.dumps({"regularization": [1.0], "seed": 42}))
    command = [
        sys.executable,
        "-m",
        "app.ctr.training",
        "--features",
        str(tmp_path / "data"),
        "--output",
        str(tmp_path / "model"),
        "--config",
        str(config),
    ]
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr
    manifest = json.loads(result.stdout)
    assert manifest["configuration"]["seed"] == 42
    assert manifest["parameters"]["C"] == 1.0
    before = (tmp_path / "model/pipeline.joblib").read_bytes()
    repeated = subprocess.run(command, capture_output=True, text=True, check=False)
    assert repeated.returncode == 2
    assert "output already exists" in repeated.stderr
    assert (tmp_path / "model/pipeline.joblib").read_bytes() == before


@pytest.mark.parametrize("split", ["train", "validation"])
def test_changed_split_checksum_is_rejected(tmp_path: Path, split: str) -> None:
    path = tmp_path / "data"
    dataset(path)
    changed = records(path, split)
    changed[0]["features"]["shared_interest_count"] = 999
    (path / f"{split}.jsonl").write_text("".join(json.dumps(row) + "\n" for row in changed))
    with pytest.raises(ValueError, match="checksum"):
        train(path, tmp_path / "bad", TrainingConfig())


def test_exported_artifact_has_content_identity(tmp_path: Path) -> None:
    dataset(tmp_path / "data")
    manifest = train(tmp_path / "data", tmp_path / "model", TrainingConfig())
    assert (
        manifest["artifact"]["sha256"]
        == hashlib.sha256((tmp_path / "model/pipeline.joblib").read_bytes()).hexdigest()
    )
    assert len(manifest["model_id"]) == 64

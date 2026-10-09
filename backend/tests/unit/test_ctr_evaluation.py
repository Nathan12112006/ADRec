import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any
from uuid import UUID

import pytest

from app.ctr.dataset import write_feature_splits
from app.ctr.evaluation import evaluate, probability_metrics
from app.ctr.training import TrainingConfig, train
from app.history.artifacts import HistoryConfig, HistorySource, write_history


@pytest.mark.parametrize("label, probability", [(0, 0.25), (1, 0.75)])
def test_single_class_evaluation_retains_binary_log_loss_and_unavailable_auc(
    label: int, probability: float
) -> None:
    result = probability_metrics([label, label], [probability, probability])
    assert result["count"] == 2
    assert result["clicks"] == label * 2
    assert result["observed_ctr"] == label
    assert result["log_loss"] == pytest.approx(0.2876820724517809)
    assert result["brier_loss"] == pytest.approx(0.0625)
    assert result["roc_auc"] is None
    assert "single-class" in result["auc_unavailable_reason"]


def test_reliability_counts_include_empty_bins_and_probability_endpoints() -> None:
    result = probability_metrics([0, 0, 1, 1], [0.0, 0.25, 0.5, 1.0], bins=4)
    assert result["roc_auc"] == 1.0
    assert result["brier_loss"] == pytest.approx(0.078125)
    assert result["auc_unavailable_reason"] is None
    assert [row["count"] for row in result["reliability"]] == [1, 1, 1, 1]
    assert [row["mean_prediction"] for row in result["reliability"]] == [0.0, 0.25, 0.5, 1.0]
    constant = probability_metrics([0, 1], [0.25, 0.25], bins=4)
    assert [row["count"] for row in constant["reliability"]] == [0, 2, 0, 0]
    assert constant["reliability"][0]["observed_ctr"] is None
    assert constant["reliability"][1]["observed_ctr"] == 0.5
    assert constant["roc_auc"] == 0.5


@pytest.mark.parametrize(
    "labels, probabilities, bins",
    [
        ([], [], 10),
        ([0], [0.2, 0.3], 10),
        ([2], [0.5], 10),
        ([True], [0.5], 10),
        ([0.5], [0.5], 10),
        ([0], [float("nan")], 10),
        ([1], [1.1], 10),
        ([0], [-0.1], 10),
        ([0], [0.5], 0),
        ([0], [0.5], True),
        ([[0]], [[0.5]], 10),
    ],
)
def test_invalid_metric_inputs_are_rejected(
    labels: object, probabilities: object, bins: int
) -> None:
    with pytest.raises(ValueError):
        probability_metrics(labels, probabilities, bins=bins)  # type: ignore[arg-type]


def trained_fixture(root: Path, *, evaluation_label: int | None = None) -> dict[str, Any]:
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
    write_history(source, root / "history", HistoryConfig(impressions=1000))
    write_feature_splits(root / "history", root / "features")
    if evaluation_label is not None:
        manifest_path = root / "features/manifest.json"
        manifest = json.loads(manifest_path.read_text())
        for name in ("validation", "test"):
            path = root / "features" / f"{name}.jsonl"
            rows = [json.loads(line) for line in path.read_text().splitlines()]
            for row in rows:
                row["label"] = evaluation_label
            data = "".join(json.dumps(row) + "\n" for row in rows).encode()
            path.write_bytes(data)
            manifest["files"][path.name] = hashlib.sha256(data).hexdigest()
            manifest["splits"][name]["clicks"] = evaluation_label * len(rows)
        manifest_path.write_text(json.dumps(manifest))
    return train(root / "features", root / "model", TrainingConfig())


def test_offline_report_scores_identical_rows_against_frozen_training_base_rate(
    tmp_path: Path,
) -> None:
    trained_fixture(tmp_path)
    before = (tmp_path / "model/pipeline.joblib").read_bytes()
    (tmp_path / "features/train.jsonl").unlink()
    report = evaluate(tmp_path / "features", tmp_path / "model", tmp_path / "report")
    assert report["status"] == "complete"
    assert report["baseline"]["probability"] == pytest.approx(29 / 700)
    for name in ("validation", "test"):
        cohort = report["splits"][name]
        assert cohort["model"]["count"] == cohort["baseline"]["count"] == 150
        assert cohort["model"]["clicks"] == cohort["baseline"]["clicks"]
        assert sum(row["count"] for row in cohort["model"]["reliability"]) == 150
        assert (tmp_path / "report" / f"reliability-{name}.png").read_bytes().startswith(b"\x89PNG")
    assert (tmp_path / "model/pipeline.joblib").read_bytes() == before
    assert json.loads((tmp_path / "report/report.json").read_text()) == report
    text = (tmp_path / "report/report.md").read_text()
    assert "discrimination" in text and "calibration" in text and "synthetic" in text
    assert text.index("| test | baseline |") < text.index("![validation")


@pytest.mark.parametrize("label", [0, 1])
def test_report_preserves_single_class_limits_and_training_only_baseline(
    tmp_path: Path, label: int
) -> None:
    trained_fixture(tmp_path, evaluation_label=label)
    report = evaluate(tmp_path / "features", tmp_path / "model", tmp_path / "report")
    for cohort in report["splits"].values():
        assert cohort["model"]["roc_auc"] is None
        assert cohort["baseline"]["roc_auc"] is None
        assert cohort["baseline"]["brier_loss"] == pytest.approx((label - 29 / 700) ** 2)
    assert report["baseline"]["probability"] == pytest.approx(29 / 700)
    assert "unavailable (single-class)" in (tmp_path / "report/report.md").read_text()


@pytest.mark.parametrize("target", ["test", "validation", "model", "manifest"])
def test_corrupt_or_changed_input_cannot_publish_complete_report(
    tmp_path: Path, target: str
) -> None:
    trained_fixture(tmp_path)
    path = tmp_path / "features" / f"{target}.jsonl"
    if target == "model":
        path = tmp_path / "model/pipeline.joblib"
    if target == "manifest":
        path = tmp_path / "model/manifest.json"
    path.write_bytes(path.read_bytes() + b"corruption")
    with pytest.raises(ValueError):
        evaluate(tmp_path / "features", tmp_path / "model", tmp_path / "report")
    assert not (tmp_path / "report/report.json").exists()


def test_cli_emits_report_and_refuses_overwrite(tmp_path: Path) -> None:
    trained_fixture(tmp_path)
    command = [
        sys.executable,
        "-m",
        "app.ctr.evaluation",
        "--features",
        str(tmp_path / "features"),
        "--model",
        str(tmp_path / "model"),
        "--output",
        str(tmp_path / "report"),
        "--bins",
        "10",
    ]
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert report["reliability"]["bins"] == 10
    before = (tmp_path / "report/report.json").read_bytes()
    repeat = subprocess.run(command, capture_output=True, text=True, check=False)
    assert repeat.returncode == 2
    assert "already exists" in repeat.stderr
    assert (tmp_path / "report/report.json").read_bytes() == before

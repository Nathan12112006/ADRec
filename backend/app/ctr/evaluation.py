"""Offline probability evaluation of a frozen training pipeline."""

import argparse
import hashlib
import json
import platform
import sys
from collections.abc import Sequence
from importlib.metadata import version
from pathlib import Path
from typing import Any

import joblib  # type: ignore[import-untyped]
import numpy as np
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure
from sklearn.metrics import (  # type: ignore[import-untyped]
    brier_score_loss,
    log_loss,
    roc_auc_score,
)
from threadpoolctl import threadpool_limits  # type: ignore[import-untyped]

from app.ctr.dataset import FEATURE_SCHEMA
from app.ctr.features import FEATURE_VERSION
from app.ctr.inputs import FEATURE_COLUMNS
from app.ctr.training import DEPENDENCIES, MODEL_VERSION, _FeatureManifest, _load_split

EVALUATION_VERSION = "ctr-evaluation-v1"
LIMITATIONS = (
    "Log loss (primary) and Brier loss score probabilities; lower is better. "
    "ROC-AUC measures discrimination; higher is better, and a constant baseline has AUC 0.5 "
    "when both classes are present. Reliability diagrams assess calibration with bin counts; "
    "lower log loss alone does not prove better calibration. Validation was used for model "
    "selection; final test is a later chronological synthetic cohort. These results do not "
    "establish real-user effectiveness or generalization to entirely unseen users/ads. "
    "No minimum score or lift is required. Do not retune the generator, refit preprocessing "
    "or select models after inspecting final-test results."
)


def probability_metrics(
    labels: Sequence[int], probabilities: Sequence[float], *, bins: int = 10
) -> dict[str, Any]:
    """Score binary click probabilities; single-class AUC is unavailable."""
    y = np.asarray(labels)
    p = np.asarray(probabilities, dtype=np.float64)
    if (
        type(bins) is not int
        or not 1 <= bins <= 100
        or y.ndim != 1
        or p.ndim != 1
        or y.size == 0
        or y.shape != p.shape
        or y.dtype.kind not in "iu"
        or not np.isin(y, [0, 1]).all()
        or not np.isfinite(p).all()
        or ((p < 0) | (p > 1)).any()
    ):
        raise ValueError(
            "requires nonempty binary integer labels, matching finite probabilities in "
            "[0,1], and 1–100 bins"
        )
    single_class = np.unique(y).size < 2
    bin_ids = np.minimum((p * bins).astype(int), bins - 1)
    reliability = []
    for index in range(bins):
        selected = bin_ids == index
        count = int(selected.sum())
        reliability.append(
            {
                "lower": index / bins,
                "upper": (index + 1) / bins,
                "count": count,
                "mean_prediction": float(p[selected].mean()) if count else None,
                "observed_ctr": float(y[selected].mean()) if count else None,
            }
        )
    return {
        "count": int(y.size),
        "clicks": int(y.sum()),
        "observed_ctr": float(y.mean()),
        "log_loss": float(log_loss(y, p, labels=[0, 1])),
        "brier_loss": float(brier_score_loss(y, p, pos_label=1)),
        "roc_auc": None if single_class else float(roc_auc_score(y, p)),
        "auc_unavailable_reason": "single-class evaluation subset" if single_class else None,
        "reliability": reliability,
    }


def _json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _load_frozen(model: Path, source_bytes: bytes) -> tuple[Any, dict[str, Any]]:
    manifest = json.loads((model / "manifest.json").read_bytes())
    identity = {key: value for key, value in manifest.items() if key != "model_id"}
    if hashlib.sha256(_json(identity).encode()).hexdigest() != manifest.get("model_id"):
        raise ValueError("model manifest identity mismatch")
    if (
        manifest.get("status") != "complete"
        or manifest.get("model_version") != MODEL_VERSION
        or manifest.get("feature_version") != FEATURE_VERSION
        or manifest.get("feature_schema") != FEATURE_SCHEMA
        or manifest.get("feature_columns") != list(FEATURE_COLUMNS)
        or manifest.get("source", {}).get("manifest_sha256")
        != hashlib.sha256(source_bytes).hexdigest()
    ):
        raise ValueError("requires a compatible frozen model and its original feature splits")
    if manifest.get("dependencies") != {name: version(name) for name in DEPENDENCIES} or (
        manifest.get("runtime")
        != {"python": platform.python_version(), "implementation": platform.python_implementation()}
    ):
        raise ValueError(
            "model runtime/dependencies mismatch; use the original training environment"
        )
    artifact = manifest["artifact"]
    if (
        artifact["filename"] != "pipeline.joblib"
        or hashlib.sha256((model / "pipeline.joblib").read_bytes()).hexdigest()
        != artifact["sha256"]
    ):
        raise ValueError("model artifact checksum mismatch")
    try:
        pipeline = joblib.load(model / "pipeline.joblib")
        if pipeline.classes_.tolist() != [0, 1]:
            raise ValueError("requires binary classifier classes [0,1]")
        fixture = manifest["prediction_fixture"]
        np.testing.assert_allclose(
            pipeline.predict_proba(np.asarray(fixture["rows"], dtype=object)),
            fixture["probabilities"],
            rtol=0,
            atol=1e-12,
        )
    except Exception as error:
        raise ValueError(f"frozen pipeline/fixture rejected: {error}") from error
    return pipeline, manifest


def _plot(cohort: dict[str, Any], path: Path, name: str) -> None:
    figure = Figure(figsize=(11, 5.5), layout="constrained")
    FigureCanvasAgg(figure)
    calibration, counts = figure.subplots(1, 2)
    extent = max(
        max(row["upper"], row["observed_ctr"])
        for label in ("model", "baseline")
        for row in cohort[label]["reliability"]
        if row["count"]
    )
    extent = min(1.0, max(0.1, extent * 1.25))
    calibration.plot([0, 1], [0, 1], "--", color="gray", label="Perfect calibration")
    for label, color in (("model", "#2563eb"), ("baseline", "#c2410c")):
        rows = cohort[label]["reliability"]
        populated = [row for row in rows if row["count"]]
        calibration.plot(
            [row["mean_prediction"] for row in populated],
            [row["observed_ctr"] for row in populated],
            "o-",
            color=color,
            label=label,
        )
        counts.plot(
            [(row["lower"] + row["upper"]) / 2 for row in rows],
            [row["count"] for row in rows],
            "o-",
            color=color,
            label=label,
        )
        for index, row in enumerate(populated):
            calibration.annotate(
                f"n={row['count']:,}",
                (row["mean_prediction"], row["observed_ctr"]),
                xytext=(5, 9 if label == "model" and index % 2 == 0 else -16),
                textcoords="offset points",
                fontsize=8,
                color=color,
            )
    calibration.set(
        xlabel="Mean predicted CTR in bin",
        ylabel="Observed CTR in bin",
        xlim=(0, extent),
        ylim=(0, extent),
        title="Reliability (populated probability range)",
    )
    counts.set_ylim(bottom=0)
    counts.set(
        xlabel="Probability bin midpoint",
        ylabel="Impression count",
        xlim=(0, 1),
        yscale="symlog",
        title="Bin sample counts (symlog scale)",
    )
    for axis in (calibration, counts):
        axis.legend()
        axis.grid(alpha=0.2)
    figure.suptitle(f"Synthetic CTR — {name} — {cohort['model']['count']:,} impressions")
    figure.supxlabel(
        "Calibration and discrimination differ; "
        "synthetic results do not establish real-user effectiveness.",
        fontsize=9,
    )
    figure.savefig(path, dpi=130, bbox_inches="tight")


def _markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Frozen CTR probability evaluation",
        "",
        LIMITATIONS,
        "",
        f"Model: `{report['model']['model_id']}`. Training-only base rate: "
        f"{report['baseline']['probability']:.8f}.",
        "",
        "| Split | Predictor | Count | Clicks | Observed CTR | Log loss | ROC-AUC | Brier loss |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for name, cohort in report["splits"].items():
        for label in ("model", "baseline"):
            row = cohort[label]
            auc = (
                "unavailable (single-class)" if row["roc_auc"] is None else f"{row['roc_auc']:.8f}"
            )
            lines.append(
                f"| {name} | {label} | {row['count']} | {row['clicks']} | "
                f"{row['observed_ctr']:.8f} | {row['log_loss']:.8f} | {auc} | "
                f"{row['brier_loss']:.8f} |"
            )
    for name in report["splits"]:
        lines.extend(["", f"![{name} reliability and bin counts](reliability-{name}.png)", ""])
    lines.extend(
        [
            "All model/baseline rows are identical within each split. JSON retains full "
            "provenance, model settings, split boundaries and empty-bin counts.",
            "",
        ]
    )
    return "\n".join(lines)


def evaluate(features: Path, model: Path, output: Path, *, bins: int = 20) -> dict[str, Any]:
    """Load a trusted project artifact once, score validation/test, never fit or mutate inputs."""
    if output.exists():
        raise FileExistsError("output already exists; select a new directory")
    if type(bins) is not int or not 1 <= bins <= 100:
        raise ValueError("requires 1–100 reliability bins")
    source_bytes = (features / "manifest.json").read_bytes()
    source = json.loads(source_bytes)
    _FeatureManifest.model_validate(source)
    with threadpool_limits(limits=1):
        pipeline, model_manifest = _load_frozen(model, source_bytes)
        training = source["splits"]["train"]
        rate = model_manifest["training_base_rate"]
        if (
            training["count"] < 1
            or not 0 < rate < 1
            or rate != training["clicks"] / training["count"]
        ):
            raise ValueError("baseline requires the original training-only class counts/base rate")
        output.mkdir(parents=True, exist_ok=False)
        try:
            previous = _FeatureManifest.model_validate(source).splits["train"].last
            assert previous is not None
            key = (previous.impressed_at, previous.impression_id)
            seen: set[int] = set()
            cohorts = {}
            for name in ("validation", "test"):
                matrix, labels, key = _load_split(features, name, source, seen, key)
                probabilities = np.asarray(pipeline.predict_proba(matrix), dtype=np.float64)
                if probabilities.shape != (len(labels), 2):
                    raise ValueError("pipeline must return two probabilities for every impression")
                if not np.isfinite(probabilities).all() or not np.allclose(
                    probabilities.sum(axis=1), 1.0, rtol=0, atol=1e-12
                ):
                    raise ValueError("pipeline probabilities must be finite and sum to one")
                cohorts[name] = {
                    "boundaries": source["splits"][name],
                    "model": probability_metrics(
                        labels.tolist(), probabilities[:, 1].tolist(), bins=bins
                    ),
                    "baseline": probability_metrics(
                        labels.tolist(), [rate] * len(labels), bins=bins
                    ),
                }
                _plot(cohorts[name], output / f"reliability-{name}.png", name)
            report = {
                "status": "complete",
                "evaluation_version": EVALUATION_VERSION,
                "primary_metric": "log_loss",
                "model": model_manifest,
                "baseline": {"probability": rate, "fit_split": "train", "counts": training},
                "reliability": {
                    "bins": bins,
                    "policy": "equal width [lower,upper); last includes 1; empty bins retained",
                },
                "splits": cohorts,
                "limitations": LIMITATIONS,
                "evaluation_dependencies": {"matplotlib": version("matplotlib")},
                "files": {
                    f"reliability-{name}.png": hashlib.sha256(
                        (output / f"reliability-{name}.png").read_bytes()
                    ).hexdigest()
                    for name in cohorts
                },
            }
            (output / "report.md").write_text(_markdown(report), encoding="utf-8")
            (output / "report.json").write_text(_json(report) + "\n", encoding="utf-8")
            return report
        except BaseException as error:
            (output / "status.json").write_text(
                _json({"status": "failed", "reason": str(error)}) + "\n", encoding="utf-8"
            )
            raise


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate a frozen CTR pipeline offline")
    parser.add_argument("--features", type=Path, required=True)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--bins", type=int, default=20)
    args = parser.parse_args()
    try:
        print(_json(evaluate(args.features, args.model, args.output, bins=args.bins)))
        return 0
    except (ValueError, FileExistsError, KeyError, TypeError) as error:
        print(f"CTR evaluation rejected: {error}", file=sys.stderr)
        return 2
    except OSError as error:
        print(f"CTR evaluation failed: {error}", file=sys.stderr)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())

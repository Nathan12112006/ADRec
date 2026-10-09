"""Validate trusted offline CTR artifacts and package evaluation evidence for serving."""

import argparse
import hashlib
import json
import platform
import sys
from importlib.metadata import version
from pathlib import Path
from typing import Any

import joblib  # type: ignore[import-untyped]
import numpy as np

from app.ctr.dataset import FEATURE_SCHEMA
from app.ctr.features import FEATURE_VERSION
from app.ctr.inputs import FEATURE_COLUMNS
from app.ctr.training import DEPENDENCIES, MODEL_VERSION, _FeatureManifest

BUNDLE_VERSION = "ctr-serving-bundle-v1"


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def content_id(value: dict[str, Any], field: str) -> str:
    return hashlib.sha256(
        canonical_json({k: v for k, v in value.items() if k != field}).encode()
    ).hexdigest()


def load_pipeline(path: Path, manifest: dict[str, Any]) -> Any:
    """Validate before unpickling; callers must supply only trusted project artifacts."""
    if content_id(manifest, "model_id") != manifest.get("model_id"):
        raise ValueError("model manifest identity mismatch")
    if (
        manifest.get("status") != "complete"
        or manifest.get("model_version") != MODEL_VERSION
        or manifest.get("feature_version") != FEATURE_VERSION
        or manifest.get("feature_schema") != FEATURE_SCHEMA
        or manifest.get("feature_columns") != list(FEATURE_COLUMNS)
    ):
        raise ValueError("incompatible model/feature schema")
    source = manifest["source"]["feature_dataset"]
    _FeatureManifest.model_validate(source)
    if manifest.get("dependencies") != {name: version(name) for name in DEPENDENCIES} or (
        manifest.get("runtime")
        != {"python": platform.python_version(), "implementation": platform.python_implementation()}
    ):
        raise ValueError(
            "model runtime/dependencies mismatch; use the original training environment"
        )
    if (
        manifest["artifact"]["filename"] != "pipeline.joblib"
        or hashlib.sha256(path.read_bytes()).hexdigest() != manifest["artifact"]["sha256"]
    ):
        raise ValueError("model artifact checksum mismatch")
    pipeline = joblib.load(path)
    classes = np.asarray(pipeline.classes_)
    if classes.shape != (2,) or classes.dtype.kind not in "iu" or set(classes.tolist()) != {0, 1}:
        raise ValueError("requires binary classifier classes 0 and 1")
    fixture = manifest["prediction_fixture"]
    if classes.tolist() != fixture["classes"]:
        raise ValueError("prediction fixture class order mismatch")
    probabilities = np.asarray(
        pipeline.predict_proba(np.asarray(fixture["rows"], dtype=object)), dtype=np.float64
    )
    validate_probabilities(probabilities, len(fixture["rows"]))
    np.testing.assert_allclose(probabilities, fixture["probabilities"], rtol=0, atol=1e-12)
    return pipeline


def validate_probabilities(probabilities: Any, count: int) -> None:
    if (
        probabilities.shape != (count, 2)
        or not np.isfinite(probabilities).all()
        or ((probabilities < 0) | (probabilities > 1)).any()
        or not np.allclose(probabilities.sum(axis=1), 1.0, rtol=0, atol=1e-12)
    ):
        raise ValueError("requires two finite probabilities in [0,1] per row summing to one")


def _validate_evaluation(report: dict[str, Any], model: dict[str, Any]) -> None:
    if (
        report.get("status") != "complete"
        or report.get("evaluation_version") != "ctr-evaluation-v1"
        or report.get("model") != model
        or set(report.get("splits", {})) != {"validation", "test"}
    ):
        raise ValueError("requires complete evaluation of this exact frozen model")
    source = model["source"]["feature_dataset"]
    training = source["splits"]["train"]
    rate = model["training_base_rate"]
    if not 0 < rate < 1 or rate != training["clicks"] / training["count"]:
        raise ValueError("invalid training-only base rate")
    if report["baseline"] != {"probability": rate, "fit_split": "train", "counts": training}:
        raise ValueError("evaluation baseline mismatch")
    for name, cohort in report["splits"].items():
        info = source["splits"][name]
        if cohort["boundaries"] != info:
            raise ValueError("evaluation split boundaries mismatch")
        for predictor in ("model", "baseline"):
            metrics = cohort[predictor]
            if metrics["count"] != info["count"] or metrics["clicks"] != info["clicks"]:
                raise ValueError("evaluation split counts mismatch")
            if not all(
                np.isfinite(metrics[key]) and metrics[key] >= 0
                for key in ("log_loss", "brier_loss")
            ):
                raise ValueError("invalid evaluation metrics")
            auc = metrics["roc_auc"]
            if auc is not None and (not np.isfinite(auc) or not 0 <= auc <= 1):
                raise ValueError("invalid evaluation AUC")


def package_model(model: Path, evaluation: Path, output: Path) -> dict[str, Any]:
    """Explicitly combine a frozen pipeline and its exact evaluation; never fit."""
    if output.exists():
        raise FileExistsError("output already exists; select a new directory")
    manifest = json.loads((model / "manifest.json").read_bytes())
    load_pipeline(model / "pipeline.joblib", manifest)
    report = json.loads((evaluation / "report.json").read_bytes())
    _validate_evaluation(report, manifest)
    bundle = {
        "status": "complete",
        "bundle_version": BUNDLE_VERSION,
        "model": manifest,
        "evaluation": report,
    }
    bundle["bundle_id"] = content_id(bundle, "bundle_id")
    output.mkdir(parents=True, exist_ok=False)
    (output / "pipeline.joblib").write_bytes((model / "pipeline.joblib").read_bytes())
    (output / "manifest.json").write_text(canonical_json(bundle) + "\n", encoding="utf-8")
    return bundle


def load_bundle(path: Path) -> tuple[Any, dict[str, Any]]:
    bundle = json.loads((path / "manifest.json").read_bytes())
    if (
        bundle.get("status") != "complete"
        or bundle.get("bundle_version") != BUNDLE_VERSION
        or content_id(bundle, "bundle_id") != bundle.get("bundle_id")
    ):
        raise ValueError("serving bundle identity/version mismatch")
    _validate_evaluation(bundle["evaluation"], bundle["model"])
    return load_pipeline(path / "pipeline.joblib", bundle["model"]), bundle


def main() -> int:
    parser = argparse.ArgumentParser(description="Package a frozen CTR model with its evaluation")
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--evaluation", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        print(canonical_json(package_model(args.model, args.evaluation, args.output)))
        return 0
    except (ValueError, KeyError, TypeError, FileExistsError) as error:
        print(f"CTR packaging rejected: {error}", file=sys.stderr)
        return 2
    except OSError as error:
        print(f"CTR packaging failed: {error}", file=sys.stderr)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())

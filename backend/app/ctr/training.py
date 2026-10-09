"""Explicit offline training; validation selects C and final test is never opened."""

import argparse
import hashlib
import json
import platform
import sys
import warnings
from datetime import datetime
from importlib.metadata import version
from pathlib import Path
from typing import Any

import joblib  # type: ignore[import-untyped]
import numpy as np
from numpy.typing import NDArray
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sklearn.compose import ColumnTransformer  # type: ignore[import-untyped]
from sklearn.exceptions import ConvergenceWarning  # type: ignore[import-untyped]
from sklearn.linear_model import LogisticRegression  # type: ignore[import-untyped]
from sklearn.metrics import log_loss  # type: ignore[import-untyped]
from sklearn.pipeline import Pipeline  # type: ignore[import-untyped]
from sklearn.preprocessing import OneHotEncoder, StandardScaler  # type: ignore[import-untyped]
from threadpoolctl import threadpool_limits  # type: ignore[import-untyped]

from app.ctr.dataset import FEATURE_SCHEMA, SPLIT_VERSION
from app.ctr.features import FEATURE_VERSION
from app.ctr.inputs import FEATURE_COLUMNS, FeatureInput

MODEL_VERSION = "ctr-logistic-v1"
DEPENDENCIES = ("scikit-learn", "numpy", "scipy", "joblib", "threadpoolctl")


class TrainingConfig(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)
    regularization: tuple[float, ...] = (0.1, 1.0, 10.0)
    seed: int = Field(default=20, strict=True, ge=0, lt=2**32)
    max_iter: int = Field(default=1000, strict=True, ge=1, le=100000)
    tolerance: float = Field(default=1e-6, gt=0, le=0.1)

    @model_validator(mode="after")
    def validate_candidates(self) -> "TrainingConfig":
        values = self.regularization
        if not 1 <= len(values) <= 8 or any(not np.isfinite(c) or c <= 0 for c in values):
            raise ValueError("declare 1–8 finite positive regularization C values")
        if tuple(sorted(set(values))) != values:
            raise ValueError("regularization C values must be distinct and ascending")
        return self


class _Example(BaseModel):
    model_config = ConfigDict(extra="forbid")
    impression_id: int = Field(strict=True, ge=0)
    impressed_at: datetime
    features: FeatureInput
    label: int = Field(strict=True, ge=0, le=1)


class _Boundary(BaseModel):
    model_config = ConfigDict(extra="forbid")
    impression_id: int = Field(strict=True, ge=0)
    impressed_at: datetime


class _SplitInfo(BaseModel):
    count: int = Field(strict=True, ge=0)
    clicks: int = Field(strict=True, ge=0)
    start_inclusive: int = Field(strict=True, ge=0)
    end_exclusive: int = Field(strict=True, ge=0)
    first: _Boundary | None
    last: _Boundary | None


class _FeatureManifest(BaseModel):
    status: str
    feature_version: str
    split_version: str
    feature_schema: dict[str, str]
    splits: dict[str, _SplitInfo]
    files: dict[str, str]
    source: dict[str, Any]

    @model_validator(mode="after")
    def validate_splits(self) -> "_FeatureManifest":
        names = ("train", "validation", "test")
        if (
            self.status != "complete"
            or self.feature_version != FEATURE_VERSION
            or self.split_version != SPLIT_VERSION
            or self.feature_schema != FEATURE_SCHEMA
        ):
            raise ValueError("requires complete compatible CTR feature splits")
        if set(self.splits) != set(names) or set(self.files) != {f"{n}.jsonl" for n in names}:
            raise ValueError("requires all train/validation/test splits metadata and checksums")
        total = sum(info.count for info in self.splits.values())
        ends = (total * 70 // 100, total * 85 // 100, total)
        start = 0
        for name, end in zip(names, ends, strict=True):
            info = self.splits[name]
            if (
                (info.start_inclusive, info.end_exclusive, info.count) != (start, end, end - start)
                or info.clicks > info.count
                or (info.first is not None) != bool(info.count)
                or (info.last is not None) != bool(info.count)
            ):
                raise ValueError(f"{name} splits metadata inconsistent with chronological policy")
            start = end
        if not self.source.get("history_id") or not self.source.get("dataset_id"):
            raise ValueError("source history/dataset identity required")
        return self


def _json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _load_split(
    directory: Path,
    name: str,
    manifest: dict[str, Any],
    seen: set[int],
    previous: tuple[datetime, int] | None,
) -> tuple[NDArray[np.object_], NDArray[np.int64], tuple[datetime, int]]:
    info = manifest["splits"][name]
    count = info["count"]
    if type(count) is not int or count < 1:
        raise ValueError(f"{name} split requires at least one labeled impression")
    matrix = np.empty((count, len(FEATURE_COLUMNS)), dtype=object)
    labels = np.empty(count, dtype=np.int64)
    digest = hashlib.sha256()
    actual = 0
    first_key = None
    with (directory / f"{name}.jsonl").open("rb") as stream:
        for index, line in enumerate(stream):
            digest.update(line)
            row = _Example.model_validate_json(line)
            if row.impressed_at.utcoffset() is None:
                raise ValueError(f"{name} impression requires timezone")
            key = (row.impressed_at, row.impression_id)
            if first_key is None:
                first_key = key
            if row.impression_id in seen or (previous is not None and key <= previous):
                raise ValueError("training/validation require distinct chronological impressions")
            if index >= count:
                raise ValueError(f"{name} split count mismatch")
            matrix[index] = row.features.ordered()
            labels[index] = row.label
            seen.add(row.impression_id)
            previous = key
            actual += 1
    if digest.hexdigest() != manifest["files"][f"{name}.jsonl"]:
        raise ValueError(f"{name} split checksum mismatch")
    if actual != count or int(labels.sum()) != info["clicks"]:
        raise ValueError(f"{name} split label/count mismatch")
    assert previous is not None
    first = _Boundary.model_validate(info["first"])
    last = _Boundary.model_validate(info["last"])
    if first_key != (first.impressed_at, first.impression_id) or previous != (
        last.impressed_at,
        last.impression_id,
    ):
        raise ValueError(f"{name} split time/identity boundaries mismatch")
    return matrix, labels, previous


def _pipeline(c: float, config: TrainingConfig) -> Pipeline:
    numeric = [FEATURE_COLUMNS.index(name) for name in ("shared_interest_count", "category_match")]
    categorical = [
        FEATURE_COLUMNS.index(name) for name in ("ad_category", "device_type", "age_group")
    ]
    return Pipeline(
        [
            (
                "preprocessing",
                ColumnTransformer(
                    [
                        ("numeric", StandardScaler(), numeric),
                        ("categorical", OneHotEncoder(handle_unknown="ignore"), categorical),
                    ],
                    remainder="drop",
                    sparse_threshold=1.0,
                ),
            ),
            (
                "classifier",
                LogisticRegression(
                    C=c,
                    penalty="l2",
                    solver="lbfgs",
                    class_weight=None,
                    max_iter=config.max_iter,
                    tol=config.tolerance,
                    random_state=config.seed,
                ),
            ),
        ]
    )


def train(directory: Path, output: Path, config: TrainingConfig) -> dict[str, Any]:
    if output.exists():
        raise FileExistsError("output already exists; select a new directory")
    manifest_bytes = (directory / "manifest.json").read_bytes()
    source = json.loads(manifest_bytes)
    _FeatureManifest.model_validate(source)
    seen: set[int] = set()
    x_train, y_train, previous = _load_split(directory, "train", source, seen, None)
    x_validation, y_validation, _ = _load_split(directory, "validation", source, seen, previous)
    del seen
    counts = {
        name: {"0": int((labels == 0).sum()), "1": int((labels == 1).sum())}
        for name, labels in (("train", y_train), ("validation", y_validation))
    }
    if set(y_train.tolist()) != {0, 1}:
        raise ValueError(
            f"training requires both labels 0 and 1; class_counts={counts}; generate more history"
        )
    output.mkdir(parents=True, exist_ok=False)
    try:
        best: Pipeline | None = None
        best_loss = float("inf")
        candidates = []
        with threadpool_limits(limits=1):
            for c in config.regularization:
                pipeline = _pipeline(c, config)
                with warnings.catch_warnings():
                    warnings.simplefilter("error", ConvergenceWarning)
                    try:
                        pipeline.fit(x_train, y_train)
                    except ConvergenceWarning as error:
                        raise ValueError(
                            f"C={c} did not converge; increase max_iter or inspect features; "
                            f"class_counts={counts}"
                        ) from error
                if set(pipeline.classes_.tolist()) != {0, 1}:
                    raise ValueError("classifier requires binary classes 0 and 1")
                probabilities = np.asarray(pipeline.predict_proba(x_validation), dtype=np.float64)
                if not np.isfinite(probabilities).all():
                    raise ValueError("validation predictions must be finite")
                loss = float(log_loss(y_validation, probabilities, labels=pipeline.classes_))
                candidates.append(
                    {
                        "C": c,
                        "validation_log_loss": loss,
                        "converged": True,
                        "iterations": pipeline.named_steps["classifier"].n_iter_.tolist(),
                    }
                )
                if loss < best_loss:
                    best, best_loss = pipeline, loss
            assert best is not None
            joblib.dump(best, output / "pipeline.joblib", compress=3)
            fixture = x_train[:3]
            expected = np.asarray(best.predict_proba(fixture), dtype=np.float64)
            reloaded = joblib.load(output / "pipeline.joblib")
            np.testing.assert_allclose(
                reloaded.predict_proba(fixture), expected, rtol=0, atol=1e-12
            )
        checksum = hashlib.sha256((output / "pipeline.joblib").read_bytes()).hexdigest()
        manifest = {
            "status": "complete",
            "model_version": MODEL_VERSION,
            "feature_version": FEATURE_VERSION,
            "feature_schema": FEATURE_SCHEMA,
            "feature_columns": list(FEATURE_COLUMNS),
            "label_definition": "binary click outcome grouped with historical impression",
            "configuration": config.model_dump(mode="json"),
            "parameters": {
                "C": best.named_steps["classifier"].C,
                "penalty": "l2",
                "solver": "lbfgs",
                "class_weight": None,
                "negative_undersampling": False,
                "numeric": "StandardScaler",
                "categorical": "OneHotEncoder(ignore unknown)",
                "fit_splits": ["train"],
                "native_threads": 1,
            },
            "class_counts": counts,
            "training_base_rate": float(y_train.mean()),
            "selection": {
                "metric": "validation_log_loss",
                "tie_break": "smallest C",
                "candidates": candidates,
                "final_test_read": False,
                "refit": False,
            },
            "dependencies": {name: version(name) for name in DEPENDENCIES},
            "runtime": {
                "python": platform.python_version(),
                "implementation": platform.python_implementation(),
            },
            "source": {
                "manifest_sha256": hashlib.sha256(manifest_bytes).hexdigest(),
                "feature_dataset": source,
            },
            "artifact": {"filename": "pipeline.joblib", "sha256": checksum},
            "prediction_fixture": {
                "rows": fixture.tolist(),
                "probabilities": expected.tolist(),
                "classes": best.classes_.tolist(),
                "absolute_tolerance": 1e-12,
            },
            "evaluation": "validation selection only; held-out evaluation belongs to ticket 21",
        }
        manifest["model_id"] = hashlib.sha256(_json(manifest).encode()).hexdigest()
        (output / "manifest.json").write_text(_json(manifest) + "\n", encoding="utf-8")
        return manifest
    except BaseException as error:
        (output / "status.json").write_text(
            _json({"status": "failed", "reason": str(error)}) + "\n", encoding="utf-8"
        )
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description="Train and export a CTR pipeline offline")
    parser.add_argument("--features", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--config", type=Path, help="JSON TrainingConfig (default C=0.1,1,10)")
    args = parser.parse_args()
    try:
        config = (
            TrainingConfig.model_validate_json(args.config.read_text(encoding="utf-8"))
            if args.config
            else TrainingConfig()
        )
        print(_json(train(args.features, args.output, config)))
        return 0
    except (ValueError, FileExistsError) as error:
        print(f"CTR training rejected: {error}", file=sys.stderr)
        return 2
    except OSError as error:
        print(f"CTR training failed: {error}", file=sys.stderr)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())

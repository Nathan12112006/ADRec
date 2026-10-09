"""Detached, process-resident CTR prediction adapter; no ranking or database access."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
from typing import Any

import numpy as np

from app.core.errors import WorkflowError
from app.ctr.artifacts import load_bundle, validate_probabilities
from app.ctr.features import FEATURE_VERSION, build_features
from app.ctr.inputs import feature_matrix
from app.ctr.training import MODEL_VERSION


class CTRUnavailable(WorkflowError):
    def __init__(self) -> None:
        super().__init__(503, "ctr_unavailable", "CTR model is unavailable")


@dataclass(frozen=True)
class BatchPrediction:
    ad_ids: tuple[int, ...]
    probabilities: tuple[float, ...]
    model_id: str | None
    model_version: str
    feature_version: str
    feature_elapsed_ms: float
    inference_elapsed_ms: float


class CTRModel:
    def __init__(self, pipeline: Any, model_id: str | None) -> None:
        self._pipeline = pipeline
        self._model_id = model_id
        self._positive_column = (
            pipeline.classes_.tolist().index(1) if pipeline is not None else None
        )

    @property
    def model_id(self) -> str | None:
        return self._model_id

    @classmethod
    def load(cls, path: Path) -> "CTRModel":
        try:
            pipeline, bundle = load_bundle(path)
            return cls(pipeline, bundle["model"]["model_id"])
        except Exception as error:
            raise CTRUnavailable() from error

    @classmethod
    def unavailable(cls) -> "CTRModel":
        return cls(None, None)

    def predict_batch(
        self, user: Mapping[str, Any], candidates: Sequence[Mapping[str, Any]]
    ) -> BatchPrediction:
        if not candidates:
            return BatchPrediction((), (), self._model_id, MODEL_VERSION, FEATURE_VERSION, 0.0, 0.0)
        if self._pipeline is None:
            raise CTRUnavailable()
        started = perf_counter()
        matrix = feature_matrix([build_features(user, ad) for ad in candidates])
        feature_ms = (perf_counter() - started) * 1000
        started = perf_counter()
        try:
            probabilities = np.asarray(self._pipeline.predict_proba(matrix), dtype=np.float64)
            validate_probabilities(probabilities, len(candidates))
        except Exception as error:
            raise CTRUnavailable() from error
        inference_ms = (perf_counter() - started) * 1000
        return BatchPrediction(
            tuple(ad["id"] for ad in candidates),
            tuple(float(value) for value in probabilities[:, self._positive_column]),
            self._model_id,
            MODEL_VERSION,
            FEATURE_VERSION,
            feature_ms,
            inference_ms,
        )

    def predict_one(self, user: Mapping[str, Any], candidate: Mapping[str, Any]) -> float:
        return self.predict_batch(user, [candidate]).probabilities[0]

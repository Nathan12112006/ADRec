import hashlib
import io
import json
from pathlib import Path
from typing import Annotated, Any
from uuid import UUID

import joblib  # type: ignore[import-untyped]
import numpy as np
import pytest
from fastapi import Depends
from fastapi.testclient import TestClient
from sklearn.base import BaseEstimator  # type: ignore[import-untyped]

from app.core.config import Settings
from app.ctr.artifacts import package_model
from app.ctr.dataset import write_feature_splits
from app.ctr.evaluation import evaluate
from app.ctr.features import FEATURE_VERSION, build_features
from app.ctr.inputs import feature_matrix
from app.ctr.serving import CTRModel, CTRUnavailable
from app.ctr.training import TrainingConfig, train
from app.history.artifacts import HistoryConfig, HistorySource, write_history
from app.main import create_app


@pytest.fixture
def bundle(tmp_path: Path) -> Path:
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
    write_history(source, tmp_path / "history", HistoryConfig(impressions=1000))
    write_feature_splits(tmp_path / "history", tmp_path / "features")
    train(tmp_path / "features", tmp_path / "model", TrainingConfig())
    evaluate(tmp_path / "features", tmp_path / "model", tmp_path / "evaluation")
    package_model(tmp_path / "model", tmp_path / "evaluation", tmp_path / "bundle")
    return tmp_path / "bundle"


def test_reloaded_adapter_preserves_order_and_matches_pipeline_and_single_predictions(
    bundle: Path,
) -> None:
    model = CTRModel.load(bundle)
    user = {"interests": ["music"], "device": "unseen-device", "age_group": "unseen-age"}
    ads: list[dict[str, Any]] = [
        {"id": 9, "interests": [], "category": "unseen-category"},
        {"id": 4, "interests": ["music"], "category": "music"},
        {"id": 8},
    ]
    result = model.predict_batch(user, ads)
    expected = joblib.load(bundle / "pipeline.joblib").predict_proba(
        feature_matrix([build_features(user, ad) for ad in ads])
    )[:, 1]
    assert result.ad_ids == (9, 4, 8)
    assert len(result.probabilities) == 3
    assert result.feature_version == FEATURE_VERSION
    assert (
        result.model_id == json.loads((bundle / "manifest.json").read_text())["model"]["model_id"]
    )
    np.testing.assert_allclose(result.probabilities, expected, rtol=0, atol=1e-12)
    np.testing.assert_allclose(
        np.asarray(result.probabilities, dtype=np.float64),
        np.asarray([model.predict_one(user, ad) for ad in ads], dtype=np.float64),
        rtol=0,
        atol=1e-12,
    )
    assert result.feature_elapsed_ms >= 0 and result.inference_elapsed_ms >= 0


def test_empty_batches_need_no_model_and_loaded_model_survives_artifact_removal(
    bundle: Path,
) -> None:
    model = CTRModel.load(bundle)
    for path in bundle.iterdir():
        path.unlink()
    assert model.predict_batch({}, []).probabilities == ()
    assert CTRModel.unavailable().predict_batch({}, []).probabilities == ()
    assert len(model.predict_batch({}, [{"id": 1}]).probabilities) == 1
    with pytest.raises(CTRUnavailable) as failure:
        CTRModel.load(bundle)
    assert failure.value.status_code == 503
    assert failure.value.code == "ctr_unavailable"


def test_application_ctr_failure_is_503_without_breaking_startup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.api.dependencies import get_ctr_model
    from app.core.observability import logger

    app = create_app(
        Settings(
            database_url="postgresql+psycopg://demo:secret@localhost/adflow",
            test_database_url="postgresql+psycopg://demo:secret@localhost/adflow_test",
            ctr_model_path=tmp_path / "missing",
        )
    )
    log_output = io.StringIO()
    monkeypatch.setattr(logger.handlers[0], "stream", log_output)

    @app.get("/test-ctr")
    def ctr_required(model: Annotated[CTRModel, Depends(get_ctr_model)]) -> dict[str, float]:
        return {"p": model.predict_one({}, {"id": 1})}

    with TestClient(app) as client:
        assert client.get("/health/live").status_code == 200
        response = client.get("/test-ctr")
        assert response.status_code == 503
        assert response.json() == {
            "error": {"code": "ctr_unavailable", "message": "CTR model is unavailable"}
        }
    events = [json.loads(line) for line in log_output.getvalue().splitlines()]
    assert {"event": "ctr_unavailable"} in events


def test_application_loads_model_at_startup_and_reuses_it_for_requests(bundle: Path) -> None:
    from app.api.dependencies import get_ctr_model

    app = create_app(
        Settings(
            database_url="postgresql+psycopg://demo:secret@localhost/adflow",
            test_database_url="postgresql+psycopg://demo:secret@localhost/adflow_test",
            ctr_model_path=bundle,
        )
    )

    @app.get("/test-ctr")
    def ctr_required(model: Annotated[CTRModel, Depends(get_ctr_model)]) -> dict[str, float]:
        return {"p": model.predict_one({}, {"id": 1})}

    with TestClient(app) as client:
        first = client.get("/test-ctr")
        assert first.status_code == 200
        for path in bundle.iterdir():
            path.unlink()
        assert client.get("/test-ctr").json() == first.json()


@pytest.mark.parametrize(
    "corruption", ["missing", "bytes", "schema", "runtime", "evaluation", "fixture"]
)
def test_unusable_artifacts_raise_typed_unavailable(bundle: Path, corruption: str) -> None:
    path = bundle / "manifest.json"
    manifest = json.loads(path.read_text())
    if corruption == "missing":
        path.unlink()
    elif corruption == "bytes":
        (bundle / "pipeline.joblib").write_bytes(b"corrupt pipeline")
    else:
        if corruption == "schema":
            manifest["model"]["feature_version"] = "future-version"
        elif corruption == "runtime":
            manifest["model"]["dependencies"]["scikit-learn"] = "0.0"
        elif corruption == "evaluation":
            manifest["evaluation"]["splits"]["test"]["model"]["count"] = 1
        else:
            manifest["model"]["prediction_fixture"]["probabilities"][0] = [0.0, 1.0]
        rewrite_manifest(bundle, manifest)
    with pytest.raises(CTRUnavailable) as failure:
        CTRModel.load(bundle)
    assert failure.value.status_code == 503
    assert "corrupt" not in str(failure.value)


def rewrite_manifest(path: Path, manifest: dict[str, Any]) -> None:
    def identity(value: dict[str, Any], field: str) -> str:
        raw = json.dumps(
            {key: item for key, item in value.items() if key != field},
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode()
        return hashlib.sha256(raw).hexdigest()

    manifest["model"]["model_id"] = identity(manifest["model"], "model_id")
    manifest["evaluation"]["model"] = manifest["model"]
    manifest["bundle_id"] = identity(manifest, "bundle_id")
    (path / "manifest.json").write_text(json.dumps(manifest))


class OutputClassifier(BaseEstimator):  # type: ignore[misc]
    """External-estimator fixture: valid startup rows, faulty larger batches."""

    def __init__(self, fitted: Any, mode: str) -> None:
        self.fitted = fitted
        self.mode = mode
        self.classes_ = fitted.classes_[::-1] if mode == "reversed" else fitted.classes_

    def fit(self, matrix: Any, labels: Any) -> "OutputClassifier":
        raise AssertionError("Serving must never fit")

    def predict_proba(self, matrix: Any) -> Any:
        probabilities = self.fitted.predict_proba(matrix)
        if self.mode == "reversed":
            return probabilities[:, ::-1]
        if matrix.shape[0] > 3:
            if self.mode == "nan":
                probabilities[0, 1] = np.nan
            elif self.mode == "bounds":
                probabilities[0] = [-0.1, 1.1]
            elif self.mode == "sum":
                probabilities[0] = [0.2, 0.2]
            elif self.mode == "count":
                return probabilities[:-1]
            elif self.mode == "exception":
                raise RuntimeError("Estimator failure")
        return probabilities


def estimator_fixture(bundle: Path, mode: str) -> None:
    pipeline = joblib.load(bundle / "pipeline.joblib")
    pipeline.steps[-1] = ("classifier", OutputClassifier(pipeline.steps[-1][1], mode))
    joblib.dump(pipeline, bundle / "pipeline.joblib")
    manifest = json.loads((bundle / "manifest.json").read_text())
    manifest["model"]["artifact"]["sha256"] = hashlib.sha256(
        (bundle / "pipeline.joblib").read_bytes()
    ).hexdigest()
    fixture = manifest["model"]["prediction_fixture"]
    fixture["classes"] = pipeline.classes_.tolist()
    fixture["probabilities"] = pipeline.predict_proba(
        np.asarray(fixture["rows"], dtype=object)
    ).tolist()
    rewrite_manifest(bundle, manifest)


def test_positive_probability_uses_estimator_class_labels(bundle: Path) -> None:
    normal = CTRModel.load(bundle).predict_one({}, {"id": 1})
    estimator_fixture(bundle, "reversed")
    assert CTRModel.load(bundle).predict_one({}, {"id": 1}) == pytest.approx(normal, abs=1e-12)


@pytest.mark.parametrize("mode", ["nan", "bounds", "sum", "count", "exception"])
def test_invalid_estimator_outputs_are_typed_unavailable(bundle: Path, mode: str) -> None:
    estimator_fixture(bundle, mode)
    model = CTRModel.load(bundle)
    with pytest.raises(CTRUnavailable) as failure:
        model.predict_batch({}, [{"id": index} for index in range(4)])
    assert failure.value.status_code == 503

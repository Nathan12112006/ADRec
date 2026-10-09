"""Exercise both public strategies with a persisted fitted model in each runtime."""

import json
import platform
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import UUID

from app.ctr.artifacts import package_model
from app.ctr.dataset import write_feature_splits
from app.ctr.evaluation import evaluate
from app.ctr.serving import CTRModel, CTRUnavailable
from app.ctr.training import TrainingConfig, train
from app.history.artifacts import HistoryConfig, HistorySource, write_history
from app.ranking.strategies import ExpectedValue, InterestOverlap, RankingResult


def check(bundle: Path) -> dict:
    model = CTRModel.load(bundle)
    user = {"interests": ["music"], "device": "mobile", "age_group": "25-34"}
    ads = [
        {"id": 9, "interests": ["music"], "category": "music", "bid": "0"},
        {"id": 4, "interests": [], "category": "unknown", "bid": "100"},
    ]
    v1 = InterestOverlap().rank(user, ads)
    v2 = ExpectedValue(model).rank(user, ads)
    assert [ad.ad_id for ad in v1.candidates] == [9, 4]
    assert [ad.ad_id for ad in v2.candidates] == [4, 9]
    assert v1.model_id is None and v1.candidates[0].predicted_ctr is None
    for result in (v1, v2):
        assert (
            RankingResult.model_validate_json(
                result.model_dump_json()
            ).model_dump_json()
            == result.model_dump_json()
        )
    assert ExpectedValue(CTRModel.unavailable()).rank({}, []).candidates == ()
    try:
        ExpectedValue(CTRModel.unavailable()).rank(user, ads)
    except CTRUnavailable as error:
        assert error.status_code == 503
    else:
        raise AssertionError("V2 must retain typed model unavailability")
    return {
        "passed": True,
        "python": platform.python_version(),
        "v1": v1.model_dump(mode="json"),
        "v2": v2.model_dump(mode="json"),
        "scope": "Same two candidates; model-based ranking smoke, no outcome/lift or performance claim",
    }


if len(sys.argv) > 1:
    print(json.dumps(check(Path(sys.argv[1])), sort_keys=True))
else:
    with TemporaryDirectory() as directory:
        root = Path(directory)
        source = HistorySource(
            dataset_id=UUID(int=24),
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
        train(root / "features", root / "model", TrainingConfig())
        evaluate(root / "features", root / "model", root / "evaluation")
        package_model(root / "model", root / "evaluation", root / "bundle")
        print(json.dumps(check(root / "bundle"), sort_keys=True))

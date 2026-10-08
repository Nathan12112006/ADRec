import io
import json
import platform
from contextlib import redirect_stdout
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import UUID

from app.ctr.dataset import main, write_feature_splits
from app.history.artifacts import HistoryConfig, HistorySource, write_history

source = HistorySource(
    dataset_id=UUID(int=19),
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
    first = write_feature_splits(root / "history", root / "features")
    repeat = write_feature_splits(root / "history", root / "repeat")
    assert first == repeat
    assert [info["count"] for info in first["splits"].values()] == [700, 150, 150]
    with redirect_stdout(io.StringIO()) as captured:
        assert (
            main(["--history", str(root / "history"), "--output", str(root / "cli")])
            == 0
        )
    assert json.loads(captured.getvalue()) == first
    print(
        json.dumps(
            {
                "python_version": platform.python_version(),
                "passed": True,
                "repeat_equal": True,
                "manifest": first,
            },
            sort_keys=True,
        )
    )

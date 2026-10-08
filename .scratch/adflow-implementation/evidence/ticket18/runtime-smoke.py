"""Small public writer smoke, without database or serving dependencies."""

import json
import platform
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import UUID

from app.history.artifacts import HistoryConfig, HistorySource, write_history

source = HistorySource(
    dataset_id=UUID(int=18),
    entity_manifest={"fixture": "runtime-smoke-v1"},
    users=(
        {
            "id": 1,
            "interests": ["technology"],
            "category_preferences": ["technology"],
            "device": "desktop",
            "age_group": "25-34",
            "country": "US",
        },
    ),
    ads=(
        {
            "id": 2,
            "advertiser_id": 3,
            "interests": ["technology"],
            "category": "technology",
            "bid": "2.00",
            "active": True,
            "advertiser_active": True,
        },
    ),
)
with TemporaryDirectory() as root:
    first = write_history(source, Path(root) / "first", HistoryConfig(impressions=1000))
    repeat = write_history(
        source, Path(root) / "repeat", HistoryConfig(impressions=1000)
    )
    assert first == repeat
    assert first["counts"]["impressions"] == 1000
    print(
        json.dumps(
            {
                "python": platform.python_version(),
                "system": platform.system(),
                "counts": first["counts"],
                "files": first["files"],
                "identical_repeat": True,
            },
            indent=2,
        )
    )

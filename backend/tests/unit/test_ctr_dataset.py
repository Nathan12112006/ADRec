import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any
from uuid import UUID

import pytest

from app.ctr.dataset import write_feature_splits
from app.ctr.features import FEATURE_VERSION, build_features
from app.history.artifacts import HistoryConfig, HistorySource, write_history


def history(path: Path, count: int = 20) -> HistorySource:
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
    write_history(source, path, HistoryConfig(impressions=count))
    return source


def rows(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text().splitlines()]


def test_splits_keep_all_labels_with_impressions_and_use_shared_frozen_features(
    tmp_path: Path,
) -> None:
    source = history(tmp_path / "history")
    manifest = write_feature_splits(tmp_path / "history", tmp_path / "features")
    assert manifest["feature_version"] == FEATURE_VERSION
    assert (
        manifest["source"]["history_id"]
        == json.loads((tmp_path / "history/manifest.json").read_text())["history_id"]
    )
    expected_features = build_features(source.users[0], source.ads[0])
    all_rows = []
    for split, expected_ids in (
        ("train", list(range(14))),
        ("validation", [14, 15, 16]),
        ("test", [17, 18, 19]),
    ):
        split_rows = rows(tmp_path / f"features/{split}.jsonl")
        assert [row["impression_id"] for row in split_rows] == expected_ids
        assert all(row["features"] == expected_features for row in split_rows)
        all_rows.extend(split_rows)
    original = rows(tmp_path / "history/exposures.jsonl")
    assert [row["label"] for row in all_rows] == [row["clicked"] for row in original]
    assert len({row["impression_id"] for row in all_rows}) == 20
    assert write_feature_splits(tmp_path / "history", tmp_path / "repeat") == manifest


def replace_exposures(path: Path, records: list[dict[str, Any]]) -> None:
    data = "".join(json.dumps(row) + "\n" for row in records).encode()
    (path / "exposures.jsonl").write_bytes(data)
    manifest = json.loads((path / "manifest.json").read_text())
    manifest["files"]["exposures.jsonl"] = hashlib.sha256(data).hexdigest()
    manifest["counts"]["clicks"] = sum(row["clicked"] for row in records)
    (path / "manifest.json").write_text(json.dumps(manifest))


def test_duplicate_impressions_are_rejected_without_complete_output(tmp_path: Path) -> None:
    path = tmp_path / "history"
    history(path)
    original = rows(path / "exposures.jsonl")
    original[-1] = original[0]
    replace_exposures(path, original)
    with pytest.raises(ValueError, match="duplicate impression"):
        write_feature_splits(path, tmp_path / "bad")
    assert not (tmp_path / "bad/manifest.json").exists()
    assert json.loads((tmp_path / "bad/status.json").read_text()) == {"status": "failed"}


def test_offline_command_prepares_splits_and_reports_rejected_inputs(tmp_path: Path) -> None:
    history(tmp_path / "history")
    command = [
        sys.executable,
        "-m",
        "app.ctr.dataset",
        "--history",
        str(tmp_path / "history"),
        "--output",
        str(tmp_path / "features"),
    ]
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["splits"]["train"]["count"] == 14
    refused = subprocess.run(command, capture_output=True, text=True, check=False)
    assert refused.returncode == 2
    assert "output already exists" in refused.stderr


def test_chronology_sorts_shuffled_rows_and_breaks_utc_time_ties_by_identity(
    tmp_path: Path,
) -> None:
    path = tmp_path / "history"
    history(path)
    original = rows(path / "exposures.jsonl")
    for row in original:
        row.update(
            impressed_at="2026-01-01T01:00:00+01:00",
            clicked=1,
            clicked_at="2026-01-02T00:00:00+00:00",
        )
    original[0]["impressed_at"] = "2026-01-01T00:00:01+00:00"
    replace_exposures(path, original[::-1])
    manifest = write_feature_splits(path, tmp_path / "features")
    train = rows(tmp_path / "features/train.jsonl")
    test = rows(tmp_path / "features/test.jsonl")
    assert [row["impression_id"] for row in train] == list(range(1, 15))
    assert [row["impression_id"] for row in test] == [18, 19, 0]
    assert manifest["splits"]["train"]["clicks"] == 14
    assert manifest["splits"]["test"]["last"] == {
        "impression_id": 0,
        "impressed_at": "2026-01-01T00:00:01.000000+00:00",
    }


def test_later_profile_edits_and_excluded_fields_cannot_rewrite_frozen_features(
    tmp_path: Path,
) -> None:
    path = tmp_path / "history"
    source = history(path)
    source.users[0].update(interests=[], device="edited")
    source.ads[0].update(category="edited", bid="100000")
    write_feature_splits(path, tmp_path / "features")
    assert rows(tmp_path / "features/train.jsonl")[0]["features"] == {
        "shared_interest_count": 1,
        "category_match": True,
        "ad_category": "music",
        "device_type": "mobile",
        "age_group": "25-34",
    }


@pytest.mark.parametrize("count, expected", [(1, [0, 0, 1]), (3, [2, 0, 1]), (7, [4, 1, 2])])
def test_small_history_rounding_and_empty_splits_are_explicit(
    tmp_path: Path, count: int, expected: list[int]
) -> None:
    history(tmp_path / "history", count)
    manifest = write_feature_splits(tmp_path / "history", tmp_path / "features")
    assert [info["count"] for info in manifest["splits"].values()] == expected
    for info in manifest["splits"].values():
        if info["count"] == 0:
            assert info["first"] is info["last"] is None


@pytest.mark.parametrize("filename", ["users.jsonl", "ads.jsonl", "exposures.jsonl"])
def test_source_checksum_failure_never_claims_complete(tmp_path: Path, filename: str) -> None:
    path = tmp_path / "history"
    history(path)
    with (path / filename).open("ab") as stream:
        stream.write(b"\n")
    with pytest.raises(ValueError):
        write_feature_splits(path, tmp_path / "bad")
    assert not (tmp_path / "bad/manifest.json").exists()


@pytest.mark.parametrize(
    "change",
    [
        {"user_id": 999},
        {"ad_id": 999},
        {"clicked": 2},
        {"clicked": True},
        {"clicked": 1, "clicked_at": None},
        {"impressed_at": "2026-01-01T00:00:00"},
        {"clicked": 1, "clicked_at": "2025-01-01T00:00:00+00:00"},
        {"probability": 0.99},
    ],
)
def test_invalid_references_labels_times_and_hidden_row_fields_are_rejected(
    tmp_path: Path, change: dict[str, Any]
) -> None:
    path = tmp_path / "history"
    history(path)
    original = rows(path / "exposures.jsonl")
    original[0].update(change)
    replace_exposures(path, original)
    with pytest.raises(ValueError):
        write_feature_splits(path, tmp_path / "bad")
    assert not (tmp_path / "bad/manifest.json").exists()


def test_existing_feature_output_is_preserved(tmp_path: Path) -> None:
    history(tmp_path / "history")
    write_feature_splits(tmp_path / "history", tmp_path / "features")
    before = {path.name: path.read_bytes() for path in (tmp_path / "features").iterdir()}
    with pytest.raises(FileExistsError):
        write_feature_splits(tmp_path / "history", tmp_path / "features")
    assert {path.name: path.read_bytes() for path in (tmp_path / "features").iterdir()} == before


@pytest.mark.parametrize(
    "change",
    [
        {"files": {}},
        {"counts": {}},
        {"status": "failed"},
        {"history_version": "future"},
        {"history_id": None},
    ],
)
def test_incomplete_or_incompatible_source_manifest_is_rejected(
    tmp_path: Path, change: dict[str, Any]
) -> None:
    path = tmp_path / "history"
    history(path)
    manifest = json.loads((path / "manifest.json").read_text())
    manifest.update(change)
    (path / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError):
        write_feature_splits(path, tmp_path / "bad")
    assert not (tmp_path / "bad/manifest.json").exists()

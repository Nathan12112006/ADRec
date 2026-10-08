import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import UUID

import pytest
from pydantic import ValidationError

from app.history.artifacts import HistoryConfig, HistorySource, history_batches, write_history
from app.history.outcomes import OutcomeConfig


def source() -> HistorySource:
    return HistorySource(
        dataset_id=UUID(int=18),
        entity_manifest={"generator_version": "fixture"},
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
                "category": "technology",
                "interests": ["technology"],
                "bid": "2.00",
                "active": True,
                "advertiser_active": True,
            },
        ),
    )


def test_history_files_reproduce_complete_labels_references_and_simulated_times(
    tmp_path: Path,
) -> None:
    config = HistoryConfig(impressions=20, batch_size=3, seed=18)
    first = write_history(source(), tmp_path / "first", config)
    repeat = write_history(source(), tmp_path / "repeat", config)
    assert first == repeat
    assert (tmp_path / "first" / "exposures.jsonl").read_bytes() == (
        tmp_path / "repeat" / "exposures.jsonl"
    ).read_bytes()
    rows = [
        json.loads(line)
        for line in (tmp_path / "first" / "exposures.jsonl").read_text().splitlines()
    ]
    assert len(rows) == len({row["impression_id"] for row in rows}) == 20
    assert all(row["user_id"] == 1 and row["ad_id"] == 2 for row in rows)
    assert all(type(row["clicked"]) is int and row["clicked"] in (0, 1) for row in rows)
    assert all((row["clicked_at"] is not None) == bool(row["clicked"]) for row in rows)
    assert all(row["clicked_at"] >= row["impressed_at"] for row in rows if row["clicked"])
    assert rows[0]["impressed_at"] == "2026-01-01T00:00:00+00:00"
    assert rows[-1]["impressed_at"] == "2026-01-01T00:00:19+00:00"
    assert all("probability" not in row and "hidden" not in row for row in rows)


def test_batches_bound_memory_and_do_not_change_history_or_random_streams() -> None:
    config = HistoryConfig(impressions=21, batch_size=4)
    batches = list(history_batches(source(), config))
    assert [len(batch) for batch in batches] == [4, 4, 4, 4, 4, 1]
    rows = [row for batch in batches for row in batch]
    other = config.model_copy(update={"batch_size": 7, "max_click_delay_seconds": 500})
    other_rows = [row for batch in history_batches(source(), other) for row in batch]
    assert [(row["user_id"], row["ad_id"], row["clicked"]) for row in rows] == [
        (row["user_id"], row["ad_id"], row["clicked"]) for row in other_rows
    ]
    assert rows == [
        row
        for batch in history_batches(source(), config.model_copy(update={"batch_size": 7}))
        for row in batch
    ]


def test_bid_changes_never_change_exposures_or_clicks() -> None:
    original = source()
    changed = original.model_copy(update={"ads": ({**original.ads[0], "bid": "999.00"},)})
    config = HistoryConfig(impressions=200)
    assert list(history_batches(original, config)) == list(history_batches(changed, config))


def test_outcome_settings_and_source_order_do_not_drive_random_exposure() -> None:
    original = source()
    varied = original.model_copy(
        update={
            "ads": original.ads
            + ({**original.ads[0], "id": 4, "category": "music", "interests": ["music"]},)
        }
    )
    config = HistoryConfig(impressions=100)
    other = config.model_copy(update={"outcome": OutcomeConfig(intercept=0)})

    def pairs(inputs: HistorySource, settings: HistoryConfig) -> list[tuple[int, int]]:
        return [
            (row["user_id"], row["ad_id"])
            for batch in history_batches(inputs, settings)
            for row in batch
        ]

    assert pairs(varied, config) == pairs(varied, other)
    assert pairs(varied, config) == pairs(
        varied.model_copy(update={"ads": varied.ads[::-1]}), config
    )


def test_random_exposure_includes_nonmatching_ads_and_saves_observed_sanity_rates(
    tmp_path: Path,
) -> None:
    original = source()
    varied = original.model_copy(
        update={
            "ads": original.ads
            + ({**original.ads[0], "id": 4, "category": "music", "interests": ["music"]},)
        }
    )
    manifest = write_history(varied, tmp_path / "rates", HistoryConfig(impressions=10000))
    matched, unmatched = manifest["sanity_rates"]["matched"], manifest["sanity_rates"]["unmatched"]
    assert matched["impressions"] > 4000 and unmatched["impressions"] > 4000
    assert matched["observed_ctr"] > unmatched["observed_ctr"] > 0
    assert manifest["counts"]["clicks"] == matched["clicks"] + unmatched["clicks"]


def test_existing_output_is_preserved_and_invalid_source_never_claims_complete(
    tmp_path: Path,
) -> None:
    output = tmp_path / "history"
    write_history(source(), output, HistoryConfig(impressions=3))
    before = (output / "manifest.json").read_bytes()
    with pytest.raises(FileExistsError):
        write_history(source(), output, HistoryConfig(impressions=5))
    assert (output / "manifest.json").read_bytes() == before
    inactive = source().model_copy(update={"ads": ({**source().ads[0], "active": False},)})
    with pytest.raises(ValueError, match="eligible"):
        write_history(inactive, tmp_path / "invalid", HistoryConfig())
    assert not (tmp_path / "invalid").exists()


@pytest.mark.parametrize(
    "settings",
    [
        {"impressions": 0},
        {"impressions": True},
        {"batch_size": 0},
        {"batch_size": 10001},
        {"start": datetime(2026, 1, 1)},
        {"outcome": {"hidden_scale": float("nan")}},
    ],
)
def test_invalid_history_configuration_is_rejected(settings: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        HistoryConfig(**settings)


def test_simulated_time_overflow_is_a_configuration_error() -> None:
    with pytest.raises(ValidationError):
        HistoryConfig(start=datetime(9999, 12, 31, tzinfo=timezone.utc), impressions=100000)


def test_filesystem_failure_retains_failed_status_without_complete_manifest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    original_open = Path.open

    def unavailable(path: Path, *args: Any, **kwargs: Any) -> Any:
        if path.name == "exposures.jsonl":
            raise OSError("disk unavailable")
        return original_open(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", unavailable)
    with pytest.raises(OSError, match="disk unavailable"):
        write_history(source(), tmp_path / "failed", HistoryConfig())
    assert json.loads((tmp_path / "failed" / "status.json").read_text()) == {"status": "failed"}
    assert not (tmp_path / "failed" / "manifest.json").exists()

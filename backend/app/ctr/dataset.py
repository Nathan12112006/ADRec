"""Verified frozen history to deterministic, disk-sorted chronological feature splits."""

import argparse
import hashlib
import json
import sqlite3
import sys
from collections.abc import Iterator, Sequence
from contextlib import ExitStack, closing
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.ctr.features import FEATURE_VERSION, Features, build_features

SPLIT_VERSION = "ctr-chronological-70-15-15-v1"
FEATURE_SCHEMA = {
    "shared_interest_count": "integer",
    "category_match": "boolean",
    "ad_category": "categorical string",
    "device_type": "categorical string",
    "age_group": "categorical string",
}


class _Counts(BaseModel):
    model_config = ConfigDict(strict=True)
    users: int = Field(ge=0)
    eligible_ads: int = Field(ge=0)
    impressions: int = Field(ge=1)
    clicks: int = Field(ge=0)


class _HistoryManifest(BaseModel):
    model_config = ConfigDict(strict=True)
    status: Literal["complete"]
    history_version: Literal["historical-exposure-v1"]
    history_id: str = Field(min_length=1)
    dataset_id: str = Field(min_length=1)
    outcome_version: str
    configuration: dict[str, Any]
    entity_manifest: dict[str, Any]
    counts: _Counts
    files: dict[str, str]

    @model_validator(mode="after")
    def validate_files(self) -> "_HistoryManifest":
        if set(self.files) != {"users.jsonl", "ads.jsonl", "exposures.jsonl"}:
            raise ValueError("history requires all three snapshot/exposure checksums")
        return self


class _Exposure(BaseModel):
    model_config = ConfigDict(extra="forbid")
    impression_id: int = Field(strict=True, ge=0)
    user_id: int = Field(strict=True)
    ad_id: int = Field(strict=True)
    impressed_at: datetime
    clicked: int = Field(strict=True, ge=0, le=1)
    clicked_at: datetime | None

    @model_validator(mode="after")
    def validate_label(self) -> "_Exposure":
        if self.impressed_at.utcoffset() is None:
            raise ValueError("impression requires a timezone")
        if (self.clicked_at is not None) != bool(self.clicked):
            raise ValueError("each exposure requires one complete click outcome")
        if self.clicked_at is not None and (
            self.clicked_at.utcoffset() is None or self.clicked_at < self.impressed_at
        ):
            raise ValueError("click requires a timezone and cannot precede impression")
        return self


def _json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _records(path: Path, expected_hash: str) -> Iterator[dict[str, Any]]:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for line in stream:
            digest.update(line)
            record = json.loads(line)
            if not isinstance(record, dict):
                raise ValueError(f"invalid record in {path.name}")
            yield record
    if digest.hexdigest() != expected_hash:
        raise ValueError(f"source checksum mismatch: {path.name}")


def _catalog(path: Path, expected_hash: str) -> dict[int, dict[str, Any]]:
    result: dict[int, dict[str, Any]] = {}
    for row in _records(path, expected_hash):
        identity = row.get("id")
        if type(identity) is not int or identity in result:
            raise ValueError("snapshot IDs must be distinct integers")
        result[identity] = row
    return result


def write_feature_splits(history: Path, output: Path) -> dict[str, Any]:
    """O(U+A) catalog memory, bounded row memory, O(H log H) disk sorting.

    No database/model access. Only the five allowlisted features enter `features`;
    identity, timestamp and label are separate fields for auditing and evaluation.
    """
    if output.exists():
        raise FileExistsError("output already exists; select a new directory")
    manifest_bytes = (history / "manifest.json").read_bytes()
    source = _HistoryManifest.model_validate_json(manifest_bytes).model_dump()
    users = _catalog(history / "users.jsonl", source["files"]["users.jsonl"])
    ads = _catalog(history / "ads.jsonl", source["files"]["ads.jsonl"])
    if len(users) != source["counts"]["users"] or len(ads) != source["counts"]["eligible_ads"]:
        raise ValueError("snapshot count mismatch")
    output.mkdir(parents=True, exist_ok=False)
    try:
        with TemporaryDirectory(prefix=".sort-", dir=output) as temporary:
            with closing(sqlite3.connect(str(Path(temporary) / "history.sqlite"))) as connection:
                connection.execute("PRAGMA temp_store=FILE")
                connection.execute("PRAGMA cache_size=-8192")
                connection.execute(
                    "CREATE TABLE examples (id INTEGER PRIMARY KEY, time TEXT, "
                    "features TEXT, label INTEGER)"
                )
                count = clicks = 0
                for raw in _records(
                    history / "exposures.jsonl", source["files"]["exposures.jsonl"]
                ):
                    exposure = _Exposure.model_validate(raw)
                    if exposure.user_id not in users or exposure.ad_id not in ads:
                        raise ValueError("exposure references unknown snapshot")
                    features: Features = build_features(
                        users[exposure.user_id], ads[exposure.ad_id]
                    )
                    try:
                        connection.execute(
                            "INSERT INTO examples VALUES (?, ?, ?, ?)",
                            (
                                exposure.impression_id,
                                exposure.impressed_at.astimezone(timezone.utc).isoformat(
                                    timespec="microseconds"
                                ),
                                _json(features),
                                exposure.clicked,
                            ),
                        )
                    except sqlite3.IntegrityError as error:
                        raise ValueError("duplicate impression identity") from error
                    count += 1
                    clicks += exposure.clicked
                if count != source["counts"]["impressions"] or clicks != source["counts"]["clicks"]:
                    raise ValueError("exposure/label count mismatch")
                if count == 0:
                    raise ValueError("history requires at least one impression")
                connection.commit()
                result = _write_splits(connection, output, count)
        result.update(
            {
                "status": "complete",
                "feature_version": FEATURE_VERSION,
                "feature_schema": FEATURE_SCHEMA,
                "missing_category": "__missing__ (null, empty or absent categorical)",
                "unknown_categories": (
                    "preserved as raw strings; training-only fitted encoding belongs "
                    "to model pipeline"
                ),
                "split_version": SPLIT_VERSION,
                "split_policy": (
                    "sort by UTC (impressed_at, impression_id); floor(0.70*N), floor(0.85*N), N; "
                    "labels stay with impressions, including clicks after a boundary"
                ),
                "source": {
                    "history_id": source["history_id"],
                    "dataset_id": source["dataset_id"],
                    "manifest_sha256": hashlib.sha256(manifest_bytes).hexdigest(),
                    "files": source["files"],
                    "history_version": source["history_version"],
                    "outcome_version": source["outcome_version"],
                    "configuration": source["configuration"],
                    "entity_manifest": source["entity_manifest"],
                },
            }
        )
        (output / "manifest.json").write_text(_json(result) + "\n", encoding="utf-8")
        return result
    except BaseException:
        (output / "status.json").write_text('{"status":"failed"}\n', encoding="utf-8")
        raise


def _write_splits(connection: sqlite3.Connection, output: Path, count: int) -> dict[str, Any]:
    boundaries = (count * 70 // 100, count * 85 // 100, count)
    names = ("train", "validation", "test")
    splits: dict[str, Any] = {
        name: {"count": 0, "clicks": 0, "first": None, "last": None} for name in names
    }
    hashes = {name: hashlib.sha256() for name in names}
    with ExitStack() as stack:
        streams = {
            name: stack.enter_context(
                (output / f"{name}.jsonl").open("w", encoding="utf-8", newline="\n")
            )
            for name in names
        }
        for index, (identity, time, features, label) in enumerate(
            connection.execute("SELECT id, time, features, label FROM examples ORDER BY time, id")
        ):
            name = names[0 if index < boundaries[0] else 1 if index < boundaries[1] else 2]
            row = {
                "impression_id": identity,
                "impressed_at": time,
                "features": json.loads(features),
                "label": label,
            }
            line = _json(row) + "\n"
            streams[name].write(line)
            hashes[name].update(line.encode())
            info = splits[name]
            key = {"impressed_at": time, "impression_id": identity}
            if info["first"] is None:
                info["first"] = key
            info["last"] = key
            info["count"] += 1
            info["clicks"] += label
    start = 0
    for name, end in zip(names, boundaries, strict=True):
        splits[name].update({"start_inclusive": start, "end_exclusive": end})
        start = end
    return {
        "splits": splits,
        "files": {f"{name}.jsonl": digest.hexdigest() for name, digest in hashes.items()},
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build CTR features and chronological splits offline"
    )
    parser.add_argument("--history", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        manifest = write_feature_splits(args.history, args.output)
        print(_json(manifest))
        return 0
    except (ValueError, FileExistsError) as error:
        print(f"Feature preparation rejected: {error}", file=sys.stderr)
        return 2
    except (OSError, sqlite3.Error) as error:
        print(f"Feature preparation failed: {error}", file=sys.stderr)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())

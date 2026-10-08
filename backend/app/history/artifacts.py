"""Bounded history generation from a frozen source; output is separate from live tables."""

import hashlib
import json
import platform
from collections.abc import Iterator
from datetime import datetime, timedelta, timezone
from pathlib import Path
from random import Random
from typing import Any
from uuid import NAMESPACE_URL, UUID, uuid5

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.history.outcomes import (
    OUTCOME_VERSION,
    OutcomeAd,
    OutcomeConfig,
    OutcomeGenerator,
    OutcomeUser,
    stream_seed,
)

HISTORY_VERSION = "historical-exposure-v1"


class HistoryConfig(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)
    seed: int = Field(default=18, strict=True, ge=-(2**63), lt=2**63)
    impressions: int = Field(default=10000, strict=True, ge=1, le=100_000_000)
    batch_size: int = Field(default=1000, strict=True, ge=1, le=10000)
    start: datetime = datetime(2026, 1, 1, tzinfo=timezone.utc)
    interval_seconds: int = Field(default=1, strict=True, ge=1, le=86400)
    max_click_delay_seconds: int = Field(default=300, strict=True, ge=1, le=86400)
    outcome: OutcomeConfig = OutcomeConfig()

    @model_validator(mode="after")
    def validate_time(self) -> "HistoryConfig":
        if self.start.utcoffset() is None:
            raise ValueError("start requires a timezone")
        # Validate the full time range before writing any output.
        try:
            self.start + timedelta(
                seconds=self.impressions * self.interval_seconds + self.max_click_delay_seconds
            )
        except OverflowError as error:
            raise ValueError("simulated time range exceeds datetime bounds") from error
        return self


class HistorySource(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    dataset_id: UUID
    entity_manifest: dict[str, Any]
    users: tuple[dict[str, Any], ...]
    ads: tuple[dict[str, Any], ...]


def _json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _contexts(source: HistorySource) -> tuple[list[OutcomeUser], list[OutcomeAd]]:
    users = [
        OutcomeUser(**{key: row[key] for key in OutcomeUser.model_fields})
        for row in sorted(source.users, key=lambda row: row["id"])
    ]
    ads = [
        OutcomeAd(**{key: row[key] for key in OutcomeAd.model_fields})
        for row in sorted(source.ads, key=lambda row: row["id"])
    ]
    if not users or not ads:
        raise ValueError("history requires users and eligible ads")
    if len({user.id for user in users}) != len(users) or len({ad.id for ad in ads}) != len(ads):
        raise ValueError("source IDs must be distinct")
    if any(not row["active"] or not row["advertiser_active"] for row in source.ads):
        raise ValueError("history source must contain only eligible ads")
    return users, ads


def history_batches(source: HistorySource, config: HistoryConfig) -> Iterator[list[dict[str, Any]]]:
    """Memory is O(users + eligible ads + batch_size), independent of history length."""
    users, ads = _contexts(source)
    exposure = Random(stream_seed(config.seed, "exposure"))
    delays = Random(stream_seed(config.seed, "click-delay"))
    generator = OutcomeGenerator(config.outcome, seed=config.seed)
    batch: list[dict[str, Any]] = []
    start = config.start.astimezone(timezone.utc)
    for index in range(config.impressions):
        user = users[exposure.randrange(len(users))]
        ad = ads[exposure.randrange(len(ads))]
        clicked = generator.sample(user, ad, opportunity=str(index))
        when = start + timedelta(seconds=index * config.interval_seconds)
        delay = delays.randint(1, config.max_click_delay_seconds)
        batch.append(
            {
                "impression_id": index,
                "user_id": user.id,
                "ad_id": ad.id,
                "impressed_at": when.isoformat(),
                "clicked": clicked,
                "clicked_at": (when + timedelta(seconds=delay)).isoformat() if clicked else None,
            }
        )
        if len(batch) == config.batch_size:
            yield batch
            batch = []
    if batch:
        yield batch


def write_history(source: HistorySource, output: Path, config: HistoryConfig) -> dict[str, Any]:
    users, ads = _contexts(source)
    output.mkdir(parents=True, exist_ok=False)
    try:
        files: dict[str, str] = {}
        for filename, records in (("users.jsonl", source.users), ("ads.jsonl", source.ads)):
            digest = hashlib.sha256()
            with (output / filename).open("w", encoding="utf-8", newline="\n") as stream:
                for record in sorted(records, key=lambda row: row["id"]):
                    line = _json(record) + "\n"
                    digest.update(line.encode())
                    stream.write(line)
            files[filename] = digest.hexdigest()
        users_by_id = {user.id: user for user in users}
        ads_by_id = {ad.id: ad for ad in ads}
        rates = {group: {"impressions": 0, "clicks": 0} for group in ("matched", "unmatched")}
        clicks = 0
        digest = hashlib.sha256()
        with (output / "exposures.jsonl").open("w", encoding="utf-8", newline="\n") as stream:
            for batch in history_batches(source, config):
                for row in batch:
                    user, ad = users_by_id[row["user_id"]], ads_by_id[row["ad_id"]]
                    matched = bool(set(user.interests) & set(ad.interests))
                    group = rates["matched" if matched else "unmatched"]
                    group["impressions"] += 1
                    group["clicks"] += row["clicked"]
                    clicks += row["clicked"]
                    line = _json(row) + "\n"
                    digest.update(line.encode())
                    stream.write(line)
        files["exposures.jsonl"] = digest.hexdigest()
        identity = {
            "history_version": HISTORY_VERSION,
            "outcome_version": OUTCOME_VERSION,
            "python_version": platform.python_version(),
            "dataset_id": str(source.dataset_id),
            "entity_manifest": source.entity_manifest,
            "configuration": config.model_dump(mode="json"),
            "files": files,
        }
        manifest: dict[str, Any] = {
            **identity,
            "history_id": str(uuid5(NAMESPACE_URL, _json(identity))),
            "status": "complete",
            "counts": {
                "users": len(users),
                "eligible_ads": len(ads),
                "impressions": config.impressions,
                "clicks": clicks,
            },
            "observed_ctr": clicks / config.impressions,
            "sanity_rates": {
                key: {
                    **value,
                    "observed_ctr": value["clicks"] / value["impressions"]
                    if value["impressions"]
                    else None,
                }
                for key, value in rates.items()
            },
            "exposure_policy": (
                "independent uniform users and uniform eligible ads with replacement"
            ),
            "streams": {
                key: str(stream_seed(config.seed, key))
                for key in ("exposure", "outcomes", "click-delay", "hidden")
            },
            "outcome_rule": (
                "sigmoid(intercept + distinct shared interests * weight + "
                "category preference * weight + device offset + hidden user + hidden ad)"
            ),
            "hidden_rule": (
                "per-entity seeded uniform [-hidden_scale, hidden_scale]; never saved in rows"
            ),
            "outcome_draw": (
                "Random(SHA256(outcome_version/seed/outcomes/impression_id)); "
                "live callers use their stable opportunity identity"
            ),
            "simulated_time_range": {
                "start": config.start.astimezone(timezone.utc).isoformat(),
                "last_impression": (
                    config.start.astimezone(timezone.utc)
                    + timedelta(seconds=(config.impressions - 1) * config.interval_seconds)
                ).isoformat(),
                "max_click_delay_seconds": config.max_click_delay_seconds,
            },
            "split_definitions": {
                "policy": (
                    "chronological 70/15/15 by (impressed_at, impression_id); "
                    "label stays with impression"
                ),
                "train_end_exclusive": config.impressions * 70 // 100,
                "validation_end_exclusive": config.impressions * 85 // 100,
                "test_end_exclusive": config.impressions,
            },
            "label_definition": (
                "one binary click outcome per historical exposure; "
                "clicked_at only for positive labels"
            ),
            "model_input_exclusions": [
                "bid",
                "IDs",
                "experiment variant",
                "hidden preferences",
                "true probability",
                "clicked",
                "clicked_at",
            ],
        }
        (output / "manifest.json").write_text(_json(manifest) + "\n", encoding="utf-8")
        return manifest
    except BaseException:
        (output / "status.json").write_text('{"status":"failed"}\n', encoding="utf-8")
        raise

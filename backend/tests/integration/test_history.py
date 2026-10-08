import json
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import func, select, update

from app.db.session import Database
from app.history.artifacts import HistoryConfig, write_history
from app.history.source import export_source
from app.models.records import Ad, Advertiser, Event, Recommendation, RequestOutcome
from app.seeding import SeedConfig, seed_database


def test_history_exports_eligible_frozen_snapshots_and_never_writes_live_totals(
    database: Database, tmp_path: Path
) -> None:
    seed = SeedConfig(seed=uuid4().int % 2**62, users=3, advertisers=2, ads=12)
    seed_database(database, seed, append=True)
    with database.transaction() as session:
        advertiser = session.scalar(
            select(Advertiser)
            .where(Advertiser.dataset_id == seed.dataset_id)
            .order_by(Advertiser.id)
        )
        assert advertiser is not None
        advertiser.active = False
        active_ads = list(
            session.scalars(
                select(Ad.id)
                .where(Ad.dataset_id == seed.dataset_id, Ad.advertiser_id != advertiser.id)
                .order_by(Ad.id)
            )
        )
        assert len(active_ads) >= 2
        session.execute(update(Ad).where(Ad.id == active_ads[0]).values(active=False))

    def counts() -> list[int]:
        with database.session() as session:
            return [
                int(session.scalar(select(func.count()).select_from(model)) or 0)
                for model in (Recommendation, RequestOutcome, Event)
            ]

    before = counts()
    frozen = export_source(database, seed.dataset_id)
    assert {row["id"] for row in frozen.ads} == set(active_ads[1:])
    original_bid = frozen.ads[0]["bid"]
    with database.transaction() as session:
        session.execute(update(Ad).where(Ad.id == frozen.ads[0]["id"]).values(bid=99))
    manifest = write_history(frozen, tmp_path / "history", HistoryConfig(impressions=100))
    saved = [
        json.loads(line) for line in (tmp_path / "history" / "ads.jsonl").read_text().splitlines()
    ]
    assert saved[0]["bid"] == original_bid
    assert manifest["counts"]["impressions"] == 100
    assert counts() == before


def test_history_cli_saves_manifest_and_refuses_existing_output(
    database: Database, tmp_path: Path
) -> None:
    seed = SeedConfig(seed=uuid4().int % 2**62, users=2, advertisers=1, ads=4)
    seed_database(database, seed, append=True)
    args = [
        sys.executable,
        "-m",
        "app.history.cli",
        "--dataset-id",
        str(seed.dataset_id),
        "--output",
        str(tmp_path / "history"),
        "--impressions",
        "30",
        "--batch-size",
        "7",
    ]
    result = subprocess.run(args, capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["counts"]["impressions"] == 30
    before = (tmp_path / "history" / "manifest.json").read_bytes()
    repeat = subprocess.run(args, capture_output=True, text=True, timeout=20)
    assert repeat.returncode != 0
    assert (tmp_path / "history" / "manifest.json").read_bytes() == before


def test_unknown_or_empty_source_cannot_create_history(database: Database, tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="unknown history dataset"):
        export_source(database, uuid4())
    seed = SeedConfig(seed=uuid4().int % 2**62, users=2, advertisers=0, ads=0)
    seed_database(database, seed, append=True)
    frozen = export_source(database, seed.dataset_id)
    with pytest.raises(ValueError, match="requires users and eligible ads"):
        write_history(frozen, tmp_path / "empty", HistoryConfig())
    assert not (tmp_path / "empty").exists()

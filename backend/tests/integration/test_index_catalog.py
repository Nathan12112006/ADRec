import json
import subprocess
import sys
from collections.abc import Iterator
from decimal import Decimal
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from sqlalchemy.orm import Session

from app.db.catalog import read_catalog
from app.db.session import Database
from app.models.records import Ad, Advertiser, Dataset
from app.retrieval.snapshots import build_snapshot, load_snapshot
from app.retrieval.vectors import user_vector
from app.seeding import SeedConfig, seed_database


@pytest.fixture
def catalog_inventory(database: Database) -> Iterator[tuple[Session, UUID, tuple[int, ...]]]:
    with database.session() as session:
        dataset = Dataset(seed=12, generator_version="snapshot-test", configuration={})
        session.add(dataset)
        session.flush()
        advertisers = [
            Advertiser(dataset_id=dataset.id, name="active", active=True),
            Advertiser(dataset_id=dataset.id, name="inactive", active=False),
        ]
        session.add_all(advertisers)
        session.flush()
        ids = []
        for category, active, advertiser in [
            ("technology", True, advertisers[0]),
            ("gaming", True, advertisers[0]),
            ("technology", False, advertisers[0]),
            ("technology", True, advertisers[1]),
        ]:
            ad = Ad(
                dataset_id=dataset.id,
                advertiser_id=advertiser.id,
                title="Synthetic ad",
                description="Fixture",
                target_url="https://example.test",
                category=category,
                interests=[category],
                bid=Decimal("1.25"),
                active=active,
            )
            session.add(ad)
            session.flush()
            ids.append(ad.id)
        yield session, dataset.id, tuple(ids)


def test_catalog_build_includes_only_eligible_ads_and_reloads_database_ids(
    catalog_inventory: tuple[Session, UUID, tuple[int, ...]],
    tmp_path: Path,
) -> None:
    session, dataset_id, ids = catalog_inventory
    catalog = read_catalog(session, dataset_id)
    assert [entry.ad_id for entry in catalog.entries] == list(ids[:2])
    snapshot = build_snapshot(
        tmp_path / "snapshot",
        catalog.entries,
        dataset_id=catalog.dataset_id,
        catalog_version=catalog.version,
    )
    query = user_vector(["technology"])
    assert query is not None
    hits = load_snapshot(tmp_path / "snapshot").search(query)
    assert [hit.ad_id for hit in hits] == list(ids[:2])
    assert [hit.similarity for hit in hits] == [1, 0]
    assert snapshot.manifest.catalog_version == catalog.version


@pytest.mark.parametrize(
    "field,value",
    [
        ("bid", Decimal("2.50")),
        ("title", "Edited ad"),
        ("active", False),
        ("category", "music"),
        ("interests", ["gaming"]),
    ],
)
def test_catalog_fingerprint_changes_with_current_ad_data(
    catalog_inventory: tuple[Session, UUID, tuple[int, ...]],
    field: str,
    value: object,
) -> None:
    session, dataset_id, ids = catalog_inventory
    original = read_catalog(session, dataset_id)
    assert read_catalog(session, dataset_id).version == original.version
    ad = session.get(Ad, ids[0])
    assert ad is not None
    setattr(ad, field, value)
    session.flush()
    assert read_catalog(session, dataset_id).version != original.version


def test_advertiser_deactivation_changes_version_and_excludes_its_ads(
    catalog_inventory: tuple[Session, UUID, tuple[int, ...]],
) -> None:
    session, dataset_id, ids = catalog_inventory
    original = read_catalog(session, dataset_id)
    ad = session.get(Ad, ids[0])
    assert ad is not None
    advertiser = session.get(Advertiser, ad.advertiser_id)
    assert advertiser is not None
    advertiser.active = False
    session.flush()
    changed = read_catalog(session, dataset_id)
    assert changed.version != original.version
    assert changed.entries == ()


def test_unknown_dataset_is_not_misreported_as_empty_inventory(database: Database) -> None:
    with database.session() as session, pytest.raises(ValueError, match="unknown dataset"):
        read_catalog(session, UUID(int=0))


def test_invalid_eligible_topics_abort_export(
    catalog_inventory: tuple[Session, UUID, tuple[int, ...]],
) -> None:
    session, dataset_id, ids = catalog_inventory
    ad = session.get(Ad, ids[0])
    assert ad is not None
    ad.category = "invalid"
    session.flush()
    with pytest.raises(ValueError):
        read_catalog(session, dataset_id)


@pytest.mark.parametrize("index", ["flat", "hnsw"])
def test_cli_builds_from_the_isolated_database_and_reloads_in_a_fresh_process(
    database: Database,
    tmp_path: Path,
    index: str,
) -> None:
    config = SeedConfig(seed=uuid4().int % (2**63), users=1, advertisers=1, ads=6)
    seed_database(database, config, append=True)
    path = tmp_path / "cli-snapshot"
    built = subprocess.run(
        [
            sys.executable,
            "-m",
            "app.retrieval.cli",
            "build",
            "--database",
            "test",
            "--dataset-id",
            str(config.dataset_id),
            "--output",
            str(path),
            *(
                [
                    "--index",
                    "hnsw",
                    "--hnsw-m",
                    "16",
                    "--ef-construction",
                    "80",
                    "--ef-search",
                    "64",
                ]
                if index == "hnsw"
                else []
            ),
        ],
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert built.returncode == 0, built.stderr
    manifest = json.loads(built.stdout)["manifest"]
    assert manifest["dataset_id"] == str(config.dataset_id)
    assert manifest["count"] == 6
    assert manifest["index_type"] == ("IndexHNSWFlat" if index == "hnsw" else "IndexFlatIP")
    assert manifest["hnsw"] == (
        {"m": 16, "ef_construction": 80, "ef_search": 64} if index == "hnsw" else None
    )
    loaded = subprocess.run(
        [
            sys.executable,
            "-m",
            "app.retrieval.cli",
            "load",
            str(path),
            "--interests",
            "technology",
            "--limit",
            "3",
        ],
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert loaded.returncode == 0, loaded.stderr
    assert json.loads(loaded.stdout)["manifest"] == manifest
    assert len(json.loads(loaded.stdout)["hits"]) == 3

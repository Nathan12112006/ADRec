import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from uuid import UUID

import faiss
import numpy as np
import pytest

from app.retrieval.snapshots import (
    ActiveSnapshot,
    HnswSettings,
    IndexEntry,
    build_snapshot,
    load_snapshot,
)
from app.retrieval.vectors import ad_vector, user_vector


def test_hnsw_persists_known_database_ids_cosines_and_declared_settings(tmp_path: Path) -> None:
    settings = HnswSettings(m=16, ef_construction=80, ef_search=64)
    snapshot = build_snapshot(
        tmp_path / "hnsw",
        [
            IndexEntry(ad_id=9001, vector=ad_vector(["gaming"], category="technology")),
            IndexEntry(ad_id=42, vector=ad_vector([], category="technology")),
            IndexEntry(ad_id=700, vector=ad_vector([], category="music")),
        ],
        dataset_id=UUID(int=1),
        catalog_version="catalog-1",
        hnsw=settings,
    )
    query = user_vector(["technology"])
    assert query is not None
    hits = snapshot.search(query, limit=3)
    assert [hit.ad_id for hit in hits] == [42, 9001, 700]
    assert [hit.similarity for hit in hits] == pytest.approx([1, 0.70710678, 0])
    reloaded = load_snapshot(tmp_path / "hnsw")
    assert reloaded.search(query, limit=3) == hits
    assert reloaded.manifest.hnsw == settings
    assert reloaded.manifest.index_type == "IndexHNSWFlat"
    assert reloaded.manifest.snapshot_version == snapshot.manifest.snapshot_version


def test_per_query_search_depth_is_validated_and_does_not_mutate_shared_snapshot(
    tmp_path: Path,
) -> None:
    snapshot = build_snapshot(
        tmp_path / "hnsw",
        [IndexEntry(ad_id=42, vector=ad_vector([], category="technology"))],
        dataset_id=UUID(int=1),
        catalog_version="catalog-1",
        hnsw=HnswSettings(),
    )
    query = user_vector(["technology"])
    assert query is not None
    with ThreadPoolExecutor(max_workers=4) as pool:
        hits = list(
            pool.map(
                lambda depth: snapshot.search(query, limit=1, ef_search=depth), [1, 16, 64, 256]
            )
        )
    assert all(result[0].ad_id == 42 for result in hits)
    assert snapshot.manifest.hnsw == HnswSettings()
    assert load_snapshot(tmp_path / "hnsw").manifest == snapshot.manifest
    for invalid in (0, -1, 1_000_001, True):
        with pytest.raises(ValueError):
            snapshot.search(query, limit=1, ef_search=invalid)


def test_hnsw_manifest_cannot_silently_default_missing_search_settings(tmp_path: Path) -> None:
    path = tmp_path / "hnsw"
    build_snapshot(path, [], dataset_id=UUID(int=1), catalog_version="empty", hnsw=HnswSettings())
    active = ActiveSnapshot()
    previous = active.reload(path)
    manifest = json.loads((path / "manifest.json").read_text())
    del manifest["hnsw"]["ef_search"]
    (path / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError):
        active.reload(path)
    assert active.acquire() is previous


@pytest.mark.parametrize(
    "field,value",
    [
        ("m", 1),
        ("m", 129),
        ("m", True),
        ("m", "32"),
        ("ef_construction", 0),
        ("ef_construction", 31),
        ("ef_construction", 1_000_001),
        ("ef_search", 0),
        ("ef_search", 1_000_001),
        ("ef_search", True),
    ],
)
def test_hnsw_rejects_invalid_settings_before_publishing(
    tmp_path: Path, field: str, value: object
) -> None:
    with pytest.raises(ValueError):
        build_snapshot(
            tmp_path / "invalid",
            [],
            dataset_id=UUID(int=1),
            catalog_version="empty",
            hnsw=HnswSettings.model_validate({field: value}),
        )
    assert not (tmp_path / "invalid").exists()


@pytest.mark.parametrize("field,value", [("m", 16), ("ef_construction", 100), ("ef_search", 64)])
def test_hnsw_declared_settings_must_match_native_artifact_before_reload(
    tmp_path: Path, field: str, value: int
) -> None:
    path = tmp_path / "hnsw"
    build_snapshot(path, [], dataset_id=UUID(int=1), catalog_version="empty", hnsw=HnswSettings())
    active = ActiveSnapshot()
    previous = active.reload(path)
    manifest = json.loads((path / "manifest.json").read_text())
    manifest["hnsw"][field] = value
    (path / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="settings"):
        active.reload(path)
    assert active.acquire() is previous


def test_original_flat_schema_loads_with_its_original_identity(tmp_path: Path) -> None:
    path = tmp_path / "legacy"
    build_snapshot(
        path,
        [IndexEntry(ad_id=42, vector=ad_vector([], category="technology"))],
        dataset_id=UUID(int=1),
        catalog_version="catalog-1",
    )
    manifest = json.loads((path / "manifest.json").read_text())
    manifest["schema_version"] = 1
    manifest["builder_version"] = "flat-snapshot-v1"
    del manifest["hnsw"]
    (path / "manifest.json").write_text(json.dumps(manifest))
    loaded = load_snapshot(path)
    assert loaded.manifest.schema_version == 1
    assert loaded.manifest.builder_version == "flat-snapshot-v1"
    assert loaded.manifest.hnsw is None
    query = user_vector(["technology"])
    assert query is not None
    assert loaded.search(query)[0].ad_id == 42
    with pytest.raises(ValueError, match="only to HNSW"):
        loaded.search(query, ef_search=64)


def test_hnsw_boundary_ties_allow_interchangeable_members_with_consistent_order(
    tmp_path: Path,
) -> None:
    entries = [
        IndexEntry(ad_id=ad_id, vector=ad_vector([], category="technology"))
        for ad_id in range(1, 33)
    ]
    query = user_vector(["technology"])
    assert query is not None
    for name, settings in [("flat", None), ("hnsw", HnswSettings())]:
        snapshot = build_snapshot(
            tmp_path / name, entries, dataset_id=UUID(int=1), catalog_version="ties", hnsw=settings
        )
        hits = snapshot.search(query, limit=5)
        ids = [hit.ad_id for hit in hits]
        assert len(ids) == len(set(ids)) == 5
        assert set(ids) <= set(range(1, 33))
        assert ids == sorted(ids)
        assert all(hit.similarity == pytest.approx(1) for hit in hits)


@pytest.mark.parametrize("problem", ["checksum", "mapping", "metric", "flat", "nan"])
def test_hnsw_rejects_corrupt_payloads_and_native_mismatches_before_swapping(
    tmp_path: Path, problem: str
) -> None:
    path = tmp_path / "hnsw"
    build_snapshot(
        path,
        [IndexEntry(ad_id=42, vector=ad_vector([], category="technology"))],
        dataset_id=UUID(int=1),
        catalog_version="catalog-1",
        hnsw=HnswSettings(),
    )
    active = ActiveSnapshot()
    previous = active.reload(path)
    manifest = json.loads((path / "manifest.json").read_text())
    if problem == "checksum":
        (path / "index.faiss").write_bytes(b"corrupt")
    elif problem == "mapping":
        payload = b"[99, 99]"
        (path / "ids.json").write_bytes(payload)
        manifest["mapping_sha256"] = hashlib.sha256(payload).hexdigest()
    else:
        native: faiss.Index = (
            faiss.IndexFlatIP(13)
            if problem == "flat"
            else faiss.IndexHNSWFlat(
                13, 32, faiss.METRIC_L2 if problem == "metric" else faiss.METRIC_INNER_PRODUCT
            )
        )
        if isinstance(native, faiss.IndexHNSWFlat):
            native.hnsw.efConstruction = 200
            native.hnsw.efSearch = 128
        values = np.zeros((1, 13), dtype=np.float32)
        values[0, 0] = float("nan") if problem == "nan" else 1
        native.add(values)
        payload = bytes(faiss.serialize_index(native))
        (path / "index.faiss").write_bytes(payload)
        manifest["index_sha256"] = hashlib.sha256(payload).hexdigest()
    (path / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError):
        active.reload(path)
    assert active.acquire() is previous

import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from uuid import UUID

import faiss
import numpy as np
import pytest

from app.retrieval.snapshots import ActiveSnapshot, IndexEntry, build_snapshot, load_snapshot
from app.retrieval.vectors import ad_vector, user_vector


def test_flat_search_preserves_database_ids_and_normalized_scores_across_reload(
    tmp_path: Path,
) -> None:
    path = tmp_path / "version-1"
    snapshot = build_snapshot(
        path,
        [
            IndexEntry(ad_id=9001, vector=ad_vector(["gaming"], category="technology")),
            IndexEntry(ad_id=42, vector=ad_vector([], category="technology")),
            IndexEntry(ad_id=700, vector=ad_vector([], category="music")),
        ],
        dataset_id=UUID(int=1),
        catalog_version="catalog-1",
    )
    query = user_vector(["technology"])
    assert query is not None
    hits = snapshot.search(query, limit=3)
    assert [hit.ad_id for hit in hits] == [42, 9001, 700]
    assert [hit.similarity for hit in hits] == pytest.approx([1.0, 0.70710678, 0.0])
    loaded = load_snapshot(path)
    assert loaded.search(query, limit=3) == hits
    assert loaded.manifest.snapshot_version == snapshot.manifest.snapshot_version
    assert loaded.manifest.catalog_version == "catalog-1"
    assert loaded.manifest.count == 3


@pytest.mark.parametrize("filename", ["index.faiss", "ids.json"])
def test_corrupted_payload_checksum_is_rejected_before_loading(
    tmp_path: Path, filename: str
) -> None:
    path = tmp_path / "snapshot"
    build_snapshot(
        path,
        [IndexEntry(ad_id=42, vector=ad_vector([], category="technology"))],
        dataset_id=UUID(int=1),
        catalog_version="catalog-1",
    )
    artifact = path / filename
    artifact.write_bytes(artifact.read_bytes() + b" ")
    with pytest.raises(ValueError, match="checksum"):
        load_snapshot(path)


@pytest.mark.parametrize(
    "field,value",
    [
        ("schema_version", 2),
        ("builder_version", "future-builder"),
        ("runtime.faiss_version", "0.0.0"),
        ("runtime.numpy_version", "0.0.0"),
        ("runtime.python_version", "0.0.0"),
        ("runtime.system", "other-os"),
        ("topics", ["gaming", "technology"]),
        ("dimension", 12),
        ("metric", "L2"),
    ],
)
def test_incompatible_snapshot_does_not_replace_the_active_reference(
    tmp_path: Path,
    field: str,
    value: object,
) -> None:
    path = tmp_path / "snapshot"
    built = build_snapshot(
        path,
        [IndexEntry(ad_id=42, vector=ad_vector([], category="technology"))],
        dataset_id=UUID(int=1),
        catalog_version="catalog-1",
    )
    active = ActiveSnapshot()
    assert active.acquire() is None
    original = active.reload(path)
    manifest = json.loads((path / "manifest.json").read_text())
    if field.startswith("runtime."):
        manifest["runtime"][field.split(".")[1]] = value
    else:
        manifest[field] = value
    (path / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError):
        active.reload(path)
    assert active.acquire() is original
    query = user_vector(["technology"])
    assert query is not None
    assert original.search(query, limit=1) == built.search(query, limit=1)


@pytest.mark.parametrize("ids", [[], [0], [-1], [True], ["42"], [42, 42]])
def test_mapping_must_pair_every_vector_with_one_valid_database_id(
    tmp_path: Path,
    ids: list[object],
) -> None:
    path = tmp_path / "snapshot"
    build_snapshot(
        path,
        [IndexEntry(ad_id=42, vector=ad_vector([], category="technology"))],
        dataset_id=UUID(int=1),
        catalog_version="catalog-1",
    )
    mapping = json.dumps(ids).encode()
    (path / "ids.json").write_bytes(mapping)
    manifest = json.loads((path / "manifest.json").read_text())
    manifest["mapping_sha256"] = hashlib.sha256(mapping).hexdigest()
    (path / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="mapping"):
        load_snapshot(path)


def test_duplicate_database_ids_are_rejected_before_publishing_a_snapshot(tmp_path: Path) -> None:
    entry = IndexEntry(ad_id=42, vector=ad_vector([], category="technology"))
    with pytest.raises(ValueError, match="distinct"):
        build_snapshot(
            tmp_path / "invalid",
            [entry, entry],
            dataset_id=UUID(int=1),
            catalog_version="catalog-1",
        )
    assert not (tmp_path / "invalid").exists()


@pytest.mark.parametrize("limit", [0, -1, 1_000_001, True])
def test_snapshot_search_rejects_invalid_limits(tmp_path: Path, limit: int) -> None:
    snapshot = build_snapshot(
        tmp_path / "snapshot", [], dataset_id=UUID(int=1), catalog_version="empty"
    )
    query = user_vector(["technology"])
    assert query is not None
    with pytest.raises(ValueError):
        snapshot.search(query, limit=limit)


def test_empty_snapshot_returns_no_hits_and_ties_are_ordered_by_database_id(tmp_path: Path) -> None:
    query = user_vector(["technology"])
    assert query is not None
    empty = build_snapshot(tmp_path / "empty", [], dataset_id=UUID(int=1), catalog_version="empty")
    assert load_snapshot(tmp_path / "empty").search(query) == ()
    assert empty.manifest.count == 0
    entries = [
        IndexEntry(ad_id=ad_id, vector=ad_vector([], category="technology"))
        for ad_id in (99, 2, 800)
    ]
    tied = build_snapshot(
        tmp_path / "tied", entries, dataset_id=UUID(int=1), catalog_version="tied"
    )
    assert [hit.ad_id for hit in tied.search(query, limit=500)] == [2, 99, 800]
    boundary = tied.search(query, limit=2)
    assert len(boundary) == 2
    assert [hit.ad_id for hit in boundary] == sorted(hit.ad_id for hit in boundary)


@pytest.mark.parametrize("problem", ["dimension", "metric", "count", "zero", "weighted", "nan"])
def test_native_index_must_match_the_manifest_and_valid_binary_vectors(
    tmp_path: Path,
    problem: str,
) -> None:
    path = tmp_path / "snapshot"
    build_snapshot(
        path,
        [IndexEntry(ad_id=42, vector=ad_vector([], category="technology"))],
        dataset_id=UUID(int=1),
        catalog_version="catalog-1",
    )
    dimension = 12 if problem == "dimension" else 13
    native = faiss.IndexFlatL2(dimension) if problem == "metric" else faiss.IndexFlatIP(dimension)
    values = np.zeros((2 if problem == "count" else 1, dimension), dtype=np.float32)
    if problem not in ("zero", "weighted", "nan"):
        values[:, 0] = 1
    elif problem == "weighted":
        values[0, :2] = [0.6, 0.8]
    elif problem == "nan":
        values[0, 0] = float("nan")
    native.add(values)
    payload = bytes(faiss.serialize_index(native))
    (path / "index.faiss").write_bytes(payload)
    manifest = json.loads((path / "manifest.json").read_text())
    manifest["index_sha256"] = hashlib.sha256(payload).hexdigest()
    (path / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError):
        load_snapshot(path)


@pytest.mark.parametrize(
    "field", ["schema_version", "builder_version", "topics", "metric", "vector_version", "dtype"]
)
def test_manifest_requires_explicit_format_and_semantics_fields(tmp_path: Path, field: str) -> None:
    path = tmp_path / "snapshot"
    build_snapshot(path, [], dataset_id=UUID(int=1), catalog_version="empty")
    manifest = json.loads((path / "manifest.json").read_text())
    del manifest[field]
    (path / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError):
        load_snapshot(path)


def test_reload_rejects_wrong_catalog_or_dataset_and_keeps_inflight_snapshot(
    tmp_path: Path,
) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    build_snapshot(
        first,
        [IndexEntry(ad_id=42, vector=ad_vector([], category="technology"))],
        dataset_id=UUID(int=1),
        catalog_version="catalog-1",
    )
    build_snapshot(
        second,
        [IndexEntry(ad_id=99, vector=ad_vector([], category="technology"))],
        dataset_id=UUID(int=1),
        catalog_version="catalog-2",
    )
    active = ActiveSnapshot()
    inflight = active.reload(first)
    with pytest.raises(ValueError):
        active.reload(second, expected_catalog_version="catalog-1")
    with pytest.raises(ValueError):
        active.reload(second, expected_dataset_id=UUID(int=2))
    assert active.acquire() is inflight
    replacement = active.reload(
        second, expected_catalog_version="catalog-2", expected_dataset_id=UUID(int=1)
    )
    query = user_vector(["technology"])
    assert query is not None
    assert inflight.search(query)[0].ad_id == 42
    assert replacement.search(query)[0].ad_id == 99
    assert active.acquire() is replacement


def test_failed_artifact_write_never_publishes_a_partial_version(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_write = Path.write_bytes

    def fail_mapping_write(path: Path, data: bytes) -> int:
        if path.name == "ids.json":
            raise OSError("simulated disk full")
        return original_write(path, data)

    monkeypatch.setattr(Path, "write_bytes", fail_mapping_write)
    with pytest.raises(OSError):
        build_snapshot(tmp_path / "failed", [], dataset_id=UUID(int=1), catalog_version="empty")
    assert not (tmp_path / "failed").exists()


def test_missing_reload_files_do_not_replace_an_active_snapshot(tmp_path: Path) -> None:
    path = tmp_path / "snapshot"
    build_snapshot(path, [], dataset_id=UUID(int=1), catalog_version="empty")
    active = ActiveSnapshot()
    original = active.reload(path)
    with pytest.raises(ValueError):
        active.reload(tmp_path / "missing")
    assert active.acquire() is original


def test_existing_version_cannot_be_overwritten(tmp_path: Path) -> None:
    path = tmp_path / "snapshot"
    original = build_snapshot(
        path,
        [IndexEntry(ad_id=42, vector=ad_vector([], category="technology"))],
        dataset_id=UUID(int=1),
        catalog_version="catalog-1",
    )
    with pytest.raises(ValueError, match="already exists"):
        build_snapshot(path, [], dataset_id=UUID(int=1), catalog_version="replacement")
    assert load_snapshot(path).manifest == original.manifest


def test_concurrent_readers_keep_complete_mapping_version_pairs_during_reload(
    tmp_path: Path,
) -> None:
    first, second = tmp_path / "first", tmp_path / "second"
    for path, ad_id, version in [(first, 42, "first"), (second, 99, "second")]:
        build_snapshot(
            path,
            [IndexEntry(ad_id=ad_id, vector=ad_vector([], category="technology"))],
            dataset_id=UUID(int=1),
            catalog_version=version,
        )
    active = ActiveSnapshot()
    active.reload(first)
    query = user_vector(["technology"])
    assert query is not None

    def read() -> set[tuple[str, int]]:
        observed = set()
        for _ in range(20):
            snapshot = active.acquire()
            assert snapshot is not None
            observed.add((snapshot.manifest.catalog_version, snapshot.search(query)[0].ad_id))
        return observed

    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = [pool.submit(read) for _ in range(4)]
        active.reload(second)
        observed = set().union(*(future.result(timeout=10) for future in futures))
    assert observed.issubset({("first", 42), ("second", 99)})
    assert active.acquire() is not None

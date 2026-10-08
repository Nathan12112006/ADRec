"""Offline CPU FAISS snapshots with paired stable database-ID mappings."""

import hashlib
import json
import platform
import sys
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Lock
from typing import Annotated, Literal, Protocol, cast
from uuid import UUID, uuid4

import faiss
import numpy as np
from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, model_validator

from app.core.topics import TOPICS
from app.retrieval.limits import MAX_SEARCH_LIMIT
from app.retrieval.vectors import TopicVector


class IndexEntry(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    ad_id: int = Field(strict=True, gt=0, le=2**63 - 1)
    vector: TopicVector


class _HnswGraph(Protocol):
    """Native graph attributes omitted from the pinned FAISS type stubs."""

    search_bounded_queue: bool
    check_relative_distance: bool

    def nb_neighbors(self, layer: int) -> int: ...


class RuntimeIdentity(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    faiss_version: str
    numpy_version: str
    python_version: str
    system: str
    machine: str
    byteorder: str
    faiss_build: str


def current_runtime() -> RuntimeIdentity:
    return RuntimeIdentity(
        faiss_version=str(faiss.__version__),
        numpy_version=np.__version__,
        python_version=platform.python_version(),
        system=platform.system(),
        machine=platform.machine(),
        byteorder=sys.byteorder,
        faiss_build=str(faiss.get_compile_options()),
    )


class HnswSettings(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    m: int = Field(default=32, strict=True, ge=2, le=128)
    ef_construction: int = Field(default=200, strict=True, ge=1, le=MAX_SEARCH_LIMIT)
    ef_search: int = Field(default=128, strict=True, ge=1, le=MAX_SEARCH_LIMIT)

    @model_validator(mode="after")
    def validate_build_depth(self) -> "HnswSettings":
        if self.ef_construction < self.m:
            raise ValueError("ef_construction must cover m")
        return self


class SnapshotManifest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal[1, 2] = 2
    builder_version: Literal["flat-snapshot-v1", "cpu-snapshot-v2"] = "cpu-snapshot-v2"
    snapshot_version: UUID
    dataset_id: UUID
    catalog_version: str = Field(min_length=1)
    index_type: Literal["IndexFlatIP", "IndexHNSWFlat"] = "IndexFlatIP"
    hnsw: HnswSettings | None = None
    metric: Literal["inner_product"] = "inner_product"
    vocabulary_version: Literal["topics-v1"] = "topics-v1"
    vector_version: Literal["binary-cosine-v1"] = "binary-cosine-v1"
    topics: tuple[str, ...] = TOPICS
    dimension: Literal[13] = 13
    dtype: Literal["float32"] = "float32"
    count: int = Field(strict=True, ge=0)
    build_threads: int = Field(strict=True, ge=1)
    runtime: RuntimeIdentity
    index_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    mapping_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_family(self) -> "SnapshotManifest":
        if (self.index_type == "IndexHNSWFlat") != (self.hnsw is not None):
            raise ValueError("HNSW settings must match the index family")
        if self.schema_version == 1:
            if self.builder_version != "flat-snapshot-v1" or self.hnsw is not None:
                raise ValueError("legacy schema supports only the original Flat builder")
        elif self.builder_version != "cpu-snapshot-v2":
            raise ValueError("schema 2 requires the CPU snapshot builder")
        return self


@dataclass(frozen=True)
class IndexHit:
    ad_id: int
    similarity: float


@dataclass(frozen=True, eq=False)
class IndexSnapshot:
    manifest: SnapshotManifest
    _ids: tuple[int, ...] = field(repr=False)
    _index: faiss.Index = field(repr=False)

    def search(
        self, query: TopicVector, *, limit: int = 500, ef_search: int | None = None
    ) -> tuple[IndexHit, ...]:
        """Vector-only search. Current eligibility/metadata belongs to retrieval adapters."""
        if type(limit) is not int or not 1 <= limit <= MAX_SEARCH_LIMIT:
            raise ValueError("search limit must be a positive integer within the expansion bound")
        if ef_search is not None:
            if self.manifest.hnsw is None:
                raise ValueError("ef_search applies only to HNSW snapshots")
            if type(ef_search) is not int or not 1 <= ef_search <= MAX_SEARCH_LIMIT:
                raise ValueError("ef_search must be a positive integer within the search bound")
        if not self.manifest.count:
            return ()
        values = np.asarray([query.values], dtype=np.float32)
        if self.manifest.hnsw is None:
            scores, positions = self._index.search(values, min(limit, self.manifest.count))
        else:
            # The native class exists in 1.15.1 but is absent from its bundled stubs.
            parameters = faiss.SearchParametersHNSW()  # type: ignore[attr-defined]
            parameters.bounded_queue = True
            parameters.check_relative_distance = True
            parameters.efSearch = (
                ef_search if ef_search is not None else self.manifest.hnsw.ef_search
            )
            scores, positions = self._index.search(
                values, min(limit, self.manifest.count), params=parameters
            )
        hits = [
            IndexHit(self._ids[int(position)], min(1.0, max(0.0, float(score))))
            for score, position in zip(scores[0], positions[0], strict=True)
            if position >= 0
        ]
        return tuple(sorted(hits, key=lambda hit: (-hit.similarity, hit.ad_id)))


def build_snapshot(
    directory: Path,
    entries: Iterable[IndexEntry],
    *,
    dataset_id: UUID,
    catalog_version: str,
    hnsw: HnswSettings | None = None,
) -> IndexSnapshot:
    """Prepare a new version offline; existing artifact directories are never reused."""
    ordered = sorted(entries, key=lambda entry: entry.ad_id)
    if len({entry.ad_id for entry in ordered}) != len(ordered):
        raise ValueError("snapshot entries must have distinct database IDs")
    vectors = np.asarray([entry.vector.values for entry in ordered], dtype=np.float32).reshape(
        len(ordered), len(TOPICS)
    )
    index: faiss.Index
    if hnsw is None:
        index = faiss.IndexFlatIP(len(TOPICS))
    else:
        index = faiss.IndexHNSWFlat(len(TOPICS), hnsw.m, faiss.METRIC_INNER_PRODUCT)
        index.hnsw.efConstruction = hnsw.ef_construction
        index.hnsw.efSearch = hnsw.ef_search
    index.add(vectors)
    index_bytes = bytes(faiss.serialize_index(index))
    mapping_bytes = json.dumps([entry.ad_id for entry in ordered]).encode()
    manifest = SnapshotManifest(
        snapshot_version=uuid4(),
        dataset_id=dataset_id,
        catalog_version=catalog_version,
        index_type="IndexFlatIP" if hnsw is None else "IndexHNSWFlat",
        hnsw=hnsw,
        count=len(ordered),
        build_threads=int(faiss.omp_get_max_threads()),
        runtime=current_runtime(),
        index_sha256=hashlib.sha256(index_bytes).hexdigest(),
        mapping_sha256=hashlib.sha256(mapping_bytes).hexdigest(),
    )
    if directory.exists():
        raise ValueError("snapshot directory already exists; choose a new version path")
    directory.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix=".snapshot-", dir=directory.parent) as temporary:
        stage = Path(temporary)
        (stage / "index.faiss").write_bytes(index_bytes)
        (stage / "ids.json").write_bytes(mapping_bytes)
        (stage / "manifest.json").write_text(manifest.model_dump_json(indent=2), encoding="utf-8")
        complete = load_snapshot(stage)
        stage.rename(directory)
    return complete


SnapshotFailure = Literal["missing_index", "corrupt_index", "incompatible_index", "stale_index"]


class SnapshotLoadError(ValueError):
    def __init__(self, reason: SnapshotFailure, message: str) -> None:
        super().__init__(message)
        self.reason = reason


def _read_artifact(directory: Path, filename: str) -> bytes:
    try:
        return (directory / filename).read_bytes()
    except FileNotFoundError as error:
        raise SnapshotLoadError(
            "missing_index", "missing or unreadable snapshot artifacts"
        ) from error
    except OSError as error:
        raise SnapshotLoadError(
            "corrupt_index", "missing or unreadable snapshot artifacts"
        ) from error


def _load_snapshot(
    directory: Path,
    *,
    expected_catalog_version: str | None = None,
    expected_dataset_id: UUID | None = None,
) -> IndexSnapshot:
    """Load a paired snapshot off the request path."""
    raw_manifest = json.loads(_read_artifact(directory, "manifest.json"))
    required = set(SnapshotManifest.model_fields)
    if isinstance(raw_manifest, dict) and raw_manifest.get("schema_version") == 1:
        required -= {"hnsw"}
    if not isinstance(raw_manifest, dict) or set(raw_manifest) != required:
        raise ValueError("snapshot manifest must explicitly declare every schema field")
    if (
        type(raw_manifest["schema_version"]) is not int
        or raw_manifest["schema_version"] not in (1, 2)
        or raw_manifest["builder_version"]
        != ("flat-snapshot-v1" if raw_manifest["schema_version"] == 1 else "cpu-snapshot-v2")
        or raw_manifest["index_type"] not in ("IndexFlatIP", "IndexHNSWFlat")
    ):
        raise SnapshotLoadError("incompatible_index", "incompatible snapshot schema or builder")
    for name in (
        "metric",
        "vocabulary_version",
        "vector_version",
        "dimension",
        "dtype",
    ):
        default = SnapshotManifest.model_fields[name].default
        if type(raw_manifest[name]) is not type(default) or raw_manifest[name] != default:
            raise SnapshotLoadError(
                "incompatible_index", "incompatible snapshot schema or vector settings"
            )
    raw_hnsw = raw_manifest.get("hnsw")
    if raw_hnsw is not None and (
        not isinstance(raw_hnsw, dict) or set(raw_hnsw) != set(HnswSettings.model_fields)
    ):
        raise ValueError("snapshot must explicitly declare every HNSW setting")
    manifest = SnapshotManifest.model_validate(raw_manifest)
    if manifest.topics != TOPICS:
        raise SnapshotLoadError("incompatible_index", "incompatible vocabulary order")
    if manifest.runtime != current_runtime():
        raise SnapshotLoadError(
            "incompatible_index", "incompatible snapshot runtime; rebuild in the serving runtime"
        )
    if (
        expected_catalog_version is not None
        and manifest.catalog_version != expected_catalog_version
    ):
        raise SnapshotLoadError("stale_index", "stale catalog snapshot")
    if expected_dataset_id is not None and manifest.dataset_id != expected_dataset_id:
        raise SnapshotLoadError("stale_index", "snapshot belongs to a different dataset")
    mapping_bytes = _read_artifact(directory, "ids.json")
    index_bytes = _read_artifact(directory, "index.faiss")
    if hashlib.sha256(mapping_bytes).hexdigest() != manifest.mapping_sha256:
        raise ValueError("mapping checksum mismatch")
    if hashlib.sha256(index_bytes).hexdigest() != manifest.index_sha256:
        raise ValueError("index checksum mismatch")
    try:
        ids = TypeAdapter(
            tuple[Annotated[int, Field(strict=True, gt=0, le=2**63 - 1)], ...]
        ).validate_json(mapping_bytes)
    except ValueError as error:
        raise ValueError("invalid database-ID mapping") from error
    if len(ids) != manifest.count or tuple(sorted(set(ids))) != ids:
        raise ValueError("mapping must be sorted, distinct and match the vector count")
    try:
        index = faiss.deserialize_index(np.frombuffer(index_bytes, dtype=np.uint8))
    except RuntimeError as error:
        raise ValueError("invalid serialized FAISS index") from error
    if (
        type(index) is not (faiss.IndexFlatIP if manifest.hnsw is None else faiss.IndexHNSWFlat)
        or index.d != manifest.dimension
        or index.ntotal != manifest.count
        or not index.is_trained
        or index.metric_type != faiss.METRIC_INNER_PRODUCT
    ):
        raise ValueError("native index does not match the manifest")
    if manifest.hnsw is not None:
        assert isinstance(index, faiss.IndexHNSWFlat)
        storage = faiss.downcast_index(index.storage)
        graph = cast(_HnswGraph, index.hnsw)
        if (
            type(storage) not in (faiss.IndexFlat, faiss.IndexFlatIP)
            or storage.d != manifest.dimension
            or storage.ntotal != manifest.count
            or storage.metric_type != faiss.METRIC_INNER_PRODUCT
            or graph.nb_neighbors(0) != 2 * manifest.hnsw.m
            or graph.nb_neighbors(1) != manifest.hnsw.m
            or index.hnsw.efConstruction != manifest.hnsw.ef_construction
            or index.hnsw.efSearch != manifest.hnsw.ef_search
            or not graph.search_bounded_queue
            or not graph.check_relative_distance
        ):
            raise ValueError("native HNSW settings/storage do not match the manifest")
    for offset in range(0, manifest.count, 1000):
        vectors = index.reconstruct_n(offset, min(1000, manifest.count - offset))
        for values in vectors:
            TopicVector(values=tuple(float(value) for value in values))
    return IndexSnapshot(manifest, ids, index)


def load_snapshot(
    directory: Path,
    *,
    expected_catalog_version: str | None = None,
    expected_dataset_id: UUID | None = None,
) -> IndexSnapshot:
    try:
        return _load_snapshot(
            directory,
            expected_catalog_version=expected_catalog_version,
            expected_dataset_id=expected_dataset_id,
        )
    except SnapshotLoadError:
        raise
    except ValueError as error:
        raise SnapshotLoadError("corrupt_index", str(error)) from error


@dataclass(frozen=True)
class SnapshotState:
    snapshot: IndexSnapshot | None
    failure_reason: SnapshotFailure | None


class ActiveSnapshot:
    """Validate replacements offline, then swap only a complete immutable reference."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._active: IndexSnapshot | None = None
        self._failure_reason: SnapshotFailure | None = None

    def acquire(self) -> IndexSnapshot | None:
        with self._lock:
            return self._active

    def status(self) -> SnapshotState:
        with self._lock:
            return SnapshotState(self._active, self._failure_reason)

    def reload(
        self,
        directory: Path,
        *,
        expected_catalog_version: str | None = None,
        expected_dataset_id: UUID | None = None,
    ) -> IndexSnapshot:
        try:
            replacement = load_snapshot(
                directory,
                expected_catalog_version=expected_catalog_version,
                expected_dataset_id=expected_dataset_id,
            )
        except SnapshotLoadError as error:
            with self._lock:
                self._failure_reason = error.reason
            raise
        with self._lock:
            self._active = replacement
            self._failure_reason = None
        return replacement

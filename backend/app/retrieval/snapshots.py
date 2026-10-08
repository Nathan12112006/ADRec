"""Offline exact FAISS snapshots with paired stable database-ID mappings."""

import hashlib
import json
import platform
import sys
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Lock
from typing import Annotated, Literal
from uuid import UUID, uuid4

import faiss
import numpy as np
from pydantic import BaseModel, ConfigDict, Field, TypeAdapter

from app.core.topics import TOPICS
from app.retrieval.limits import MAX_SEARCH_LIMIT
from app.retrieval.vectors import TopicVector


class IndexEntry(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    ad_id: int = Field(strict=True, gt=0, le=2**63 - 1)
    vector: TopicVector


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


class SnapshotManifest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal[1] = 1
    builder_version: Literal["flat-snapshot-v1"] = "flat-snapshot-v1"
    snapshot_version: UUID
    dataset_id: UUID
    catalog_version: str = Field(min_length=1)
    index_type: Literal["IndexFlatIP"] = "IndexFlatIP"
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


@dataclass(frozen=True)
class IndexHit:
    ad_id: int
    similarity: float


@dataclass(frozen=True, eq=False)
class ExactSnapshot:
    manifest: SnapshotManifest
    _ids: tuple[int, ...] = field(repr=False)
    _index: faiss.Index = field(repr=False)

    def search(self, query: TopicVector, *, limit: int = 500) -> tuple[IndexHit, ...]:
        """Vector-only search. Current eligibility/metadata belongs to retrieval adapters."""
        if type(limit) is not int or not 1 <= limit <= MAX_SEARCH_LIMIT:
            raise ValueError("search limit must be a positive integer within the expansion bound")
        if not self.manifest.count:
            return ()
        values = np.asarray([query.values], dtype=np.float32)
        scores, positions = self._index.search(values, min(limit, self.manifest.count))
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
) -> ExactSnapshot:
    """Prepare a new version offline; existing artifact directories are never reused."""
    ordered = sorted(entries, key=lambda entry: entry.ad_id)
    if len({entry.ad_id for entry in ordered}) != len(ordered):
        raise ValueError("snapshot entries must have distinct database IDs")
    vectors = np.asarray([entry.vector.values for entry in ordered], dtype=np.float32).reshape(
        len(ordered), len(TOPICS)
    )
    index = faiss.IndexFlatIP(len(TOPICS))
    index.add(vectors)
    index_bytes = bytes(faiss.serialize_index(index))
    mapping_bytes = json.dumps([entry.ad_id for entry in ordered]).encode()
    manifest = SnapshotManifest(
        snapshot_version=uuid4(),
        dataset_id=dataset_id,
        catalog_version=catalog_version,
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


def _read_artifact(directory: Path, filename: str) -> bytes:
    try:
        return (directory / filename).read_bytes()
    except OSError as error:
        raise ValueError("missing or unreadable snapshot artifacts") from error


def load_snapshot(
    directory: Path,
    *,
    expected_catalog_version: str | None = None,
    expected_dataset_id: UUID | None = None,
) -> ExactSnapshot:
    """Load a paired snapshot off the request path."""
    raw_manifest = json.loads(_read_artifact(directory, "manifest.json"))
    if not isinstance(raw_manifest, dict) or set(raw_manifest) != set(
        SnapshotManifest.model_fields
    ):
        raise ValueError("snapshot manifest must explicitly declare every schema field")
    manifest = SnapshotManifest.model_validate(raw_manifest)
    if manifest.topics != TOPICS:
        raise ValueError("incompatible vocabulary order")
    if manifest.runtime != current_runtime():
        raise ValueError("incompatible snapshot runtime; rebuild in the serving runtime")
    if (
        expected_catalog_version is not None
        and manifest.catalog_version != expected_catalog_version
    ):
        raise ValueError("stale catalog snapshot")
    if expected_dataset_id is not None and manifest.dataset_id != expected_dataset_id:
        raise ValueError("snapshot belongs to a different dataset")
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
        type(index) is not faiss.IndexFlatIP
        or index.d != manifest.dimension
        or index.ntotal != manifest.count
        or not index.is_trained
        or index.metric_type != faiss.METRIC_INNER_PRODUCT
    ):
        raise ValueError("native index does not match the manifest")
    for offset in range(0, manifest.count, 1000):
        vectors = index.reconstruct_n(offset, min(1000, manifest.count - offset))
        for values in vectors:
            TopicVector(values=tuple(float(value) for value in values))
    return ExactSnapshot(manifest, ids, index)


class ActiveSnapshot:
    """Validate replacements offline, then swap only a complete immutable reference."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._active: ExactSnapshot | None = None

    def acquire(self) -> ExactSnapshot | None:
        with self._lock:
            return self._active

    def reload(
        self,
        directory: Path,
        *,
        expected_catalog_version: str | None = None,
        expected_dataset_id: UUID | None = None,
    ) -> ExactSnapshot:
        replacement = load_snapshot(
            directory,
            expected_catalog_version=expected_catalog_version,
            expected_dataset_id=expected_dataset_id,
        )
        with self._lock:
            self._active = replacement
        return replacement

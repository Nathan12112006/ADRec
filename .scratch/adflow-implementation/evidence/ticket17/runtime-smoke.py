"""Run existing public snapshot seams in the native or Docker runtime."""

import json
import math
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import UUID

import faiss
from app.retrieval.snapshots import (
    ActiveSnapshot,
    HnswSettings,
    IndexEntry,
    build_snapshot,
    current_runtime,
)
from app.retrieval.vectors import ad_vector, user_vector

faiss.omp_set_num_threads(1)
results = []
with TemporaryDirectory() as root:
    for family, settings in [("flat", None), ("hnsw", HnswSettings())]:
        path = Path(root) / family
        built = build_snapshot(
            path,
            [
                IndexEntry(ad_id=42, vector=ad_vector([], category="technology")),
                IndexEntry(
                    ad_id=9001, vector=ad_vector(["gaming"], category="technology")
                ),
                IndexEntry(ad_id=700, vector=ad_vector([], category="music")),
            ],
            dataset_id=UUID("00000000-0000-0000-0000-000000000017"),
            catalog_version="ticket17-known",
            hnsw=settings,
        )
        active = ActiveSnapshot()
        loaded = active.reload(path)
        query = user_vector(["technology"])
        hits = loaded.search(query, limit=3)
        assert [hit.ad_id for hit in hits] == [42, 9001, 700]
        assert all(
            math.isclose(hit.similarity, expected, abs_tol=1e-6)
            for hit, expected in zip(hits, [1, 0.70710678, 0])
        )
        assert built.search(query, limit=3) == hits
        (path / "index.faiss").write_bytes(b"corrupt")
        try:
            active.reload(path)
        except ValueError:
            pass
        else:
            raise AssertionError("corrupt replacement accepted")
        assert active.acquire() is loaded
        assert loaded.search(query, limit=3) == hits
        results.append(
            {
                "family": family,
                "ids": [hit.ad_id for hit in hits],
                "scores": [hit.similarity for hit in hits],
                "corrupt_reload_retained_active": True,
            }
        )
print(
    json.dumps(
        {
            "runtime": current_runtime().model_dump(mode="json"),
            "threads": 1,
            "results": results,
        },
        indent=2,
    )
)

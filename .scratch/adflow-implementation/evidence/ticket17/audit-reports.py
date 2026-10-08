"""Audit saved observations; do not regenerate or change measured timings."""

import gzip
import hashlib
import json
from math import ceil
from pathlib import Path

source = Path(__file__).resolve().parents[1] / "ticket16"
results = []
for size, ads, queries in [("small", 1000, 20), ("full", 100000, 30)]:
    raw = gzip.decompress((source / f"{size}-report.json.gz").read_bytes())
    report = json.loads(raw)
    summary = json.loads((source / f"{size}-summary.json").read_text())
    digest = hashlib.sha256(raw).hexdigest()
    assert digest == summary.pop("raw_report_sha256")
    assert summary == {key: value for key, value in report.items() if key != "samples"}
    assert report["status"] == "complete"
    assert report["provenance"]["eligible_ads"] == ads
    assert report["provenance"]["actual_personalized_queries"] == queries
    assert report["provenance"]["actual_empty_queries"] == 3
    assert report["config"]["repetitions"] == 3
    assert len(report["samples"]) == (queries + 3) * 3 * 3
    assert (
        hashlib.sha256((source / f"{size}-queries.json").read_bytes()).hexdigest()
        == report["provenance"]["query_sha256"]
    )
    paths = {}
    for family in ("flat", "hnsw"):
        samples = [
            s
            for s in report["samples"]
            if s["path"] == family and s["population"] == "personalized"
        ]
        assert len(samples) == queries * 3
        for sample in samples:
            assert sample["candidate_count"] == len(set(sample["candidate_ids"])) == 500
        times = sorted(s["retrieval_ms"] for s in samples)
        p95 = times[ceil(0.95 * len(times)) - 1]
        assert p95 == report["promotion"][f"{family}_retrieval_p95_ms"]
        paths[family] = {
            "samples": len(samples),
            "retrieval_p95_ms": p95,
            "modes": sorted({s["mode"] for s in samples}),
        }
    assert report["promotion"]["eligible"] is False
    assert report["promotion"]["applied"] is False
    results.append(
        {
            "size": size,
            "eligible_ads": ads,
            "raw_sha256": digest,
            "paths": paths,
            "promotion": report["promotion"],
        }
    )
print(json.dumps(results, indent=2))

"""Repeat full feature preparation, then audit labels, ordering, schemas and output hashes."""

import hashlib
import json
import platform
import sys
from pathlib import Path
from time import perf_counter

from app.ctr.dataset import write_feature_splits

history = Path(sys.argv[1])
output = Path(sys.argv[2])
output.mkdir(parents=True, exist_ok=False)
runs = []
manifests = []
for name in ("first", "repeat"):
    started = perf_counter()
    manifest = write_feature_splits(history, output / name)
    runs.append({"run": name, "wall_seconds": perf_counter() - started})
    manifests.append(manifest)
    print(json.dumps(runs[-1]), flush=True)
assert manifests[0] == manifests[1]
source_manifest = json.loads((history / "manifest.json").read_text())
audit = {}
for name in ("first", "repeat"):
    previous = None
    total = clicks = 0
    with (history / "exposures.jsonl").open(encoding="utf-8") as originals:
        for split in ("train", "validation", "test"):
            digest = hashlib.sha256()
            split_count = split_clicks = 0
            with (output / name / f"{split}.jsonl").open("rb") as stream:
                for line in stream:
                    digest.update(line)
                    row = json.loads(line)
                    original = json.loads(next(originals))
                    assert row["impression_id"] == original["impression_id"]
                    assert row["label"] == original["clicked"]
                    assert set(row) == {
                        "features",
                        "label",
                        "impression_id",
                        "impressed_at",
                    }
                    assert set(row["features"]) == {
                        "shared_interest_count",
                        "category_match",
                        "ad_category",
                        "device_type",
                        "age_group",
                    }
                    key = (row["impressed_at"], row["impression_id"])
                    assert previous is None or previous < key
                    previous = key
                    split_count += 1
                    split_clicks += row["label"]
            info = manifests[0]["splits"][split]
            assert (split_count, split_clicks) == (info["count"], info["clicks"])
            assert digest.hexdigest() == manifests[0]["files"][f"{split}.jsonl"]
            total += split_count
            clicks += split_clicks
        assert originals.readline() == ""
    assert total == source_manifest["counts"]["impressions"]
    assert clicks == source_manifest["counts"]["clicks"]
    audit[name] = {"impressions": total, "clicks": clicks, "passed": True}
report = {
    "python_version": platform.python_version(),
    "platform": platform.platform(),
    "runs": runs,
    "repeat_manifest_equal": True,
    "audit": audit,
    "source_history_id": source_manifest["history_id"],
    "limitation": "Local offline wall costs; sequential runs before audits; no serving/model claim.",
}
(output / "measurement.json").write_text(json.dumps(report, indent=2) + "\n")
print(json.dumps(report, indent=2))

"""Reproduce the full CTR chain from frozen source snapshots, without database writes."""

import hashlib
import json
import platform
import subprocess
import sys
from pathlib import Path
from time import perf_counter

from app.ctr.serving import CTRModel
from app.history.artifacts import HistoryConfig, HistorySource, write_history


def checksum(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read(path: Path) -> dict:
    return json.loads(path.read_bytes())


def command(module: str, *arguments: str) -> dict:
    result = subprocess.run(
        [sys.executable, "-m", module, *arguments],
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(result.stdout)


root = Path(sys.argv[1]).resolve()
output = Path(sys.argv[2]).resolve()
evidence = Path(sys.argv[3]).resolve()
output.mkdir(parents=True, exist_ok=False)
history = root / "history-ticket18-full/first"
features = root / "ctr-ticket19-full/first"
model = root / "ctr-ticket20-full/first"
evaluation = root / "ctr-ticket21-verified/first"
bundle = root / "ctr-ticket22-native"
inputs = [
    path
    for folder in (history, features, model, evaluation, bundle)
    for path in folder.iterdir()
    if path.is_file()
]
before = {str(path.relative_to(root)): checksum(path) for path in inputs}
manifest = read(history / "manifest.json")
source = HistorySource(
    dataset_id=manifest["dataset_id"],
    entity_manifest=manifest["entity_manifest"],
    users=tuple(
        json.loads(line) for line in (history / "users.jsonl").read_text().splitlines()
    ),
    ads=tuple(
        json.loads(line) for line in (history / "ads.jsonl").read_text().splitlines()
    ),
)
runs = []


def record(stage: str, started: float) -> None:
    row = {"stage": stage, "wall_seconds": perf_counter() - started}
    runs.append(row)
    print(json.dumps(row), flush=True)


started = perf_counter()
generated = write_history(
    source, output / "history", HistoryConfig.model_validate(manifest["configuration"])
)
assert generated == manifest
for filename, digest in generated["files"].items():
    assert checksum(output / "history" / filename) == digest
record("history", started)

started = perf_counter()
command(
    "app.ctr.dataset",
    "--history",
    str(output / "history"),
    "--output",
    str(output / "features"),
)
assert read(output / "features/manifest.json") == read(features / "manifest.json")
record("features", started)

started = perf_counter()
trained = command(
    "app.ctr.training",
    "--features",
    str(output / "features"),
    "--output",
    str(output / "model"),
)
assert trained == read(model / "manifest.json")
assert checksum(output / "model/pipeline.joblib") == trained["artifact"]["sha256"]
record("training", started)

started = perf_counter()
report = command(
    "app.ctr.evaluation",
    "--features",
    str(output / "features"),
    "--model",
    str(output / "model"),
    "--output",
    str(output / "evaluation"),
)
assert report == read(evaluation / "report.json")
for filename, digest in report["files"].items():
    assert checksum(output / "evaluation" / filename) == digest
record("evaluation", started)

started = perf_counter()
packaged = command(
    "app.ctr.artifacts",
    "--model",
    str(output / "model"),
    "--evaluation",
    str(output / "evaluation"),
    "--output",
    str(output / "bundle"),
)
assert packaged == read(bundle / "manifest.json")
loaded = CTRModel.load(output / "bundle")
ads = [source.ads[index] for index in (9, 4, 8)]
predictions = loaded.predict_batch(source.users[0], ads)
assert predictions.ad_ids == tuple(ad["id"] for ad in ads)
assert all(0 <= p <= 1 for p in predictions.probabilities)
assert all(
    abs(p - loaded.predict_one(source.users[0], ad)) <= 1e-12
    for p, ad in zip(predictions.probabilities, ads, strict=True)
)
assert loaded.predict_batch({}, []).probabilities == ()
assert (
    0
    <= loaded.predict_one(
        {"device": "unknown", "age_group": "unknown", "interests": []},
        {"id": 1, "category": "unknown"},
    )
    <= 1
)
record("package_reload_predict", started)
assert before == {str(path.relative_to(root)): checksum(path) for path in inputs}

result = {
    "passed": True,
    "python": platform.python_version(),
    "platform": platform.platform(),
    "output": str(output),
    "comparison": "Exact manifests, pipeline checksum and evaluation outputs equal retained tickets 18-22 within the same runtime",
    "inputs_unchanged": True,
    "input_sha256": before,
    "runs": runs,
    "history_id": manifest["history_id"],
    "dataset_id": manifest["dataset_id"],
    "counts": manifest["counts"],
    "model_id": trained["model_id"],
    "bundle_id": packaged["bundle_id"],
    "baseline": report["baseline"],
    "metrics": {
        name: {
            predictor: {
                key: value
                for key, value in cohort[predictor].items()
                if key != "reliability"
            }
            for predictor in ("model", "baseline")
        }
        for name, cohort in report["splits"].items()
    },
    "limitation": "Frozen entity snapshots are reused; database export/entity generation are covered by retained earlier evidence. Wall costs include startup/validation/I/O and concurrent verification; no controlled performance claim. No generator or model setting changed after final-test inspection.",
}
evidence.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"passed": True, "report": str(evidence)}), flush=True)

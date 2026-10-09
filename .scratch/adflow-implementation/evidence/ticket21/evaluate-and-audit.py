"""Reproduce final frozen evaluation without fitting or altering historical/model artifacts."""

import hashlib
import json
import platform
import subprocess
import sys
from pathlib import Path
from time import perf_counter


def checksum(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


features, model, output = [Path(value).resolve() for value in sys.argv[1:]]
output.mkdir(parents=True, exist_ok=False)
inputs = list(features.iterdir()) + list(model.iterdir())
before = {str(path): checksum(path) for path in inputs if path.is_file()}
reports = []
runs = []
for name in ("first", "repeat"):
    started = perf_counter()
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "app.ctr.evaluation",
            "--features",
            str(features),
            "--model",
            str(model),
            "--output",
            str(output / name),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    runs.append({"run": name, "wall_seconds": perf_counter() - started})
    report = json.loads(result.stdout)
    assert report["status"] == "complete"
    for cohort in report["splits"].values():
        for predictor in ("model", "baseline"):
            metrics = cohort[predictor]
            assert metrics["count"] == cohort["boundaries"]["count"]
            assert metrics["clicks"] == cohort["boundaries"]["clicks"]
            assert (
                sum(row["count"] for row in metrics["reliability"]) == metrics["count"]
            )
        assert cohort["baseline"]["roc_auc"] == 0.5
    for filename, digest in report["files"].items():
        assert checksum(output / name / filename) == digest
    reports.append(report)
    print(json.dumps(runs[-1]), flush=True)
assert reports[0] == reports[1]
assert before == {str(path): checksum(path) for path in inputs if path.is_file()}
measurement = {
    "passed": True,
    "python": platform.python_version(),
    "platform": platform.platform(),
    "repeat_equal": True,
    "inputs_unchanged": True,
    "runs": runs,
    "model_id": reports[0]["model"]["model_id"],
    "baseline": reports[0]["baseline"],
    "metrics": {
        name: {
            predictor: {
                key: value
                for key, value in cohort[predictor].items()
                if key != "reliability"
            }
            for predictor in ("model", "baseline")
        }
        for name, cohort in reports[0]["splits"].items()
    },
    "limitation": "Offline wall costs include startup, checksums, parsing, predictions, scoring, plotting and writing; concurrent checks ran; no controlled serving performance claim.",
}
(output / "measurement.json").write_text(json.dumps(measurement, indent=2) + "\n")
print(json.dumps(measurement, indent=2))

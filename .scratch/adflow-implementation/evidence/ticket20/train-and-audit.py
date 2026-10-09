"""Run the public training CLI twice, then audit identity and reloaded prediction agreement."""

import hashlib
import json
import platform
import subprocess
import sys
from pathlib import Path
from time import perf_counter

import joblib
import numpy as np

features = Path(sys.argv[1]).resolve()
output = Path(sys.argv[2]).resolve()
output.mkdir(parents=True, exist_ok=False)
manifests = []
runs = []
for name in ("first", "repeat"):
    command = [
        sys.executable,
        "-m",
        "app.ctr.training",
        "--features",
        str(features),
        "--output",
        str(output / name),
    ]
    started = perf_counter()
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    elapsed = perf_counter() - started
    if result.returncode:
        raise RuntimeError(result.stderr)
    manifest = json.loads(result.stdout)
    manifests.append(manifest)
    runs.append({"run": name, "wall_seconds": elapsed})
    print(json.dumps(runs[-1]), flush=True)
assert manifests[0] == manifests[1]
audit = {}
for name, manifest in zip(("first", "repeat"), manifests, strict=True):
    path = output / name / "pipeline.joblib"
    assert (
        hashlib.sha256(path.read_bytes()).hexdigest() == manifest["artifact"]["sha256"]
    )
    pipeline = joblib.load(path)
    fixture = manifest["prediction_fixture"]
    probabilities = pipeline.predict_proba(np.asarray(fixture["rows"], dtype=object))
    np.testing.assert_allclose(
        probabilities, fixture["probabilities"], rtol=0, atol=1e-12
    )
    assert pipeline.classes_.tolist() == [0, 1]
    assert np.isfinite(probabilities).all()
    assert ((0 <= probabilities) & (probabilities <= 1)).all()
    assert manifest["selection"]["final_test_read"] is False
    assert manifest["selection"]["refit"] is False
    assert all(row["converged"] for row in manifest["selection"]["candidates"])
    assert manifest["parameters"]["class_weight"] is None
    audit[name] = {
        "passed": True,
        "model_id": manifest["model_id"],
        "class_counts": manifest["class_counts"],
        "selected_C": manifest["parameters"]["C"],
    }
report = {
    "python": platform.python_version(),
    "platform": platform.platform(),
    "runs": runs,
    "repeat_equal": True,
    "audit": audit,
    "limitation": "Local offline command wall costs including startup/load/fit/export; no serving claim.",
}
(output / "measurement.json").write_text(json.dumps(report, indent=2) + "\n")
print(json.dumps(report, indent=2))

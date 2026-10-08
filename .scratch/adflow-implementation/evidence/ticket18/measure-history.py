"""Measure the real CLI twice; retain provenance and exact manifest agreement."""

import argparse
import hashlib
import json
import os
import platform
import subprocess
from pathlib import Path
from time import perf_counter, process_time

from app.history.cli import main

parser = argparse.ArgumentParser()
parser.add_argument("--dataset-id", required=True)
parser.add_argument("--output", type=Path, required=True)
parser.add_argument("--impressions", type=int, required=True)
args = parser.parse_args()
runs = []
manifests = []
for suffix in ("first", "repeat"):
    output = args.output / suffix
    started = perf_counter()
    cpu_started = process_time()
    result = main(
        [
            "--dataset-id",
            args.dataset_id,
            "--output",
            str(output),
            "--impressions",
            str(args.impressions),
            "--seed",
            "18",
        ]
    )
    wall, cpu = perf_counter() - started, process_time() - cpu_started
    assert result == 0
    memory = json.loads(
        subprocess.check_output(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                f"Get-Process -Id {os.getpid()} | Select-Object WorkingSet64,PeakWorkingSet64 | ConvertTo-Json",
            ],
            text=True,
        )
    )
    manifest = json.loads((output / "manifest.json").read_text())
    manifests.append(manifest)
    runs.append(
        {
            "output": str(output),
            "wall_seconds": wall,
            "process_cpu_seconds": cpu,
            "process_memory_after": memory,
            "artifact_bytes": sum(p.stat().st_size for p in output.iterdir()),
        }
    )
assert manifests[0] == manifests[1]
source = Path("app/history")
report = {
    "runs": runs,
    "identical_manifests_and_file_hashes": True,
    "manifest": manifests[0],
    "runtime": {
        "python": platform.python_version(),
        "system": platform.system(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "logical_cpus": os.cpu_count(),
    },
    "source_sha256": {
        str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in source.glob("*.py")
    },
    "resource_note": "CLI wall/CPU includes export and file generation, excludes entity preparation; process-wide cumulative peak working set, repeat reuses process, not incremental memory",
}
(args.output / "measurement.json").write_text(json.dumps(report, indent=2) + "\n")
print(
    json.dumps(
        {"measurement_path": str(args.output / "measurement.json"), "runs": runs},
        indent=2,
    )
)

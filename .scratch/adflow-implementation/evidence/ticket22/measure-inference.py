"""Measure shared features and one batch model call separately, without database access."""

import json
import os
import platform
import sys
from itertools import islice
from pathlib import Path
from time import perf_counter

import numpy as np
from app.ctr.serving import CTRModel
from threadpoolctl import threadpool_limits

bundle, history, output = [Path(value) for value in sys.argv[1:]]
with (history / "users.jsonl").open() as stream:
    user = json.loads(next(stream))
with (history / "ads.jsonl").open() as stream:
    ads = [json.loads(line) for line in islice(stream, 500)]
manifest = json.loads((bundle / "manifest.json").read_text())
results = []
with threadpool_limits(limits=1):
    started = perf_counter()
    model = CTRModel.load(bundle)
    load_ms = (perf_counter() - started) * 1000
    for count in (1, 50, 500):
        candidates = ads[:count]
        assert len(candidates) == count
        for _ in range(10):
            model.predict_batch(user, candidates)
        samples = [model.predict_batch(user, candidates) for _ in range(50)]
        assert samples[-1].ad_ids == tuple(ad["id"] for ad in candidates)
        np.testing.assert_allclose(
            np.asarray(samples[-1].probabilities),
            np.asarray([model.predict_one(user, ad) for ad in candidates]),
            rtol=0,
            atol=1e-12,
        )
        results.append(
            {
                "candidates": count,
                "warmups": 10,
                "repetitions": 50,
                "features_ms": {
                    "median": float(np.median([s.feature_elapsed_ms for s in samples])),
                    "p95": float(
                        np.percentile([s.feature_elapsed_ms for s in samples], 95)
                    ),
                },
                "batch_inference_ms": {
                    "median": float(
                        np.median([s.inference_elapsed_ms for s in samples])
                    ),
                    "p95": float(
                        np.percentile([s.inference_elapsed_ms for s in samples], 95)
                    ),
                },
            }
        )
report = {
    "passed": True,
    "python": platform.python_version(),
    "platform": platform.platform(),
    "processor": platform.processor(),
    "cpu_identifier": os.environ.get("PROCESSOR_IDENTIFIER"),
    "logical_cpus": os.cpu_count(),
    "native_threads": 1,
    "concurrent_callers": 1,
    "model_id": manifest["model"]["model_id"],
    "bundle_id": manifest["bundle_id"],
    "model_load_ms": load_ms,
    "results": results,
    "limitation": "Local component timing; feature timing includes validation/matrix construction, inference timing includes output validation. Excludes retrieval, database, HTTP, load and overall request costs. No speedup/target claim; other verification processes may be active.",
}
output.write_text(json.dumps(report, indent=2) + "\n")
print(json.dumps(report, indent=2))

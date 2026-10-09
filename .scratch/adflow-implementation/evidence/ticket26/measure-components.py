"""Profile production sorting through public rank calls; measure CTR phases separately."""

import cProfile
import json
import os
import platform
import pstats
import statistics
import sys
from pathlib import Path
from time import perf_counter

from app.ctr.serving import CTRModel
from app.ranking.strategies import ExpectedValue, InterestOverlap
from threadpoolctl import threadpool_limits


def distribution(values: list[float]) -> dict:
    ordered = sorted(values)
    return {
        "median_ms": statistics.median(values),
        "p95_ms": ordered[47],
        "samples_ms": values,
    }


history = Path(sys.argv[1]).resolve()
bundle = Path(sys.argv[2]).resolve()
with (history / "users.jsonl").open() as stream:
    user = json.loads(next(stream))
with (history / "ads.jsonl").open() as stream:
    ads = [json.loads(next(stream)) for _ in range(500)]
model = CTRModel.load(bundle)
rows = []
with threadpool_limits(limits=1):
    for count in (1, 50, 500):
        candidates = ads[:count]
        strategies = {"v1": InterestOverlap(), "v2": ExpectedValue(model)}
        for _ in range(10):
            model.predict_batch(user, candidates)
            for strategy in strategies.values():
                strategy.rank(user, candidates)
        features, inference = [], []
        for _ in range(50):
            prediction = model.predict_batch(user, candidates)
            features.append(prediction.feature_elapsed_ms)
            inference.append(prediction.inference_elapsed_ms)
        sorting = {}
        for name, strategy in strategies.items():
            samples = []
            for _ in range(50):
                profiler = cProfile.Profile(timer=perf_counter)
                result = profiler.runcall(strategy.rank, user, candidates)
                assert len(result.candidates) == count
                matching = [
                    value
                    for (filename, _, function), value in pstats.Stats(
                        profiler
                    ).stats.items()
                    if function == "_order"
                    and filename.replace("\\", "/").endswith("/ranking/strategies.py")
                ]
                assert len(matching) == 1 and matching[0][1] == 1
                samples.append(matching[0][3] * 1000)
            sorting[name] = distribution(samples)
        rows.append(
            {
                "candidates": count,
                "feature_construction": distribution(features),
                "batch_inference": distribution(inference),
                "profiled_sorting": sorting,
            }
        )
report = {
    "passed": True,
    "python": platform.python_version(),
    "platform": platform.platform(),
    "processor": platform.processor(),
    "logical_cpus": os.cpu_count(),
    "threads": 1,
    "callers": 1,
    "warmups_per_size": 10,
    "samples_per_component": 50,
    "history_manifest": json.loads((history / "manifest.json").read_bytes())[
        "history_id"
    ],
    "model_id": prediction.model_id,
    "candidate_selection": "first frozen user and first 1/50/500 frozen ads in source-file order",
    "sorting_scope": "cProfile cumulative _order time during public rank: production sorted(), decimal/key construction and tuple conversion; scoring and inference excluded",
    "ctr_scope": "separate unprofiled public CTRModel.predict_batch adapter timings for features and inference/output validation",
    "limitations": "Sorting includes profiler overhead and is not an uninstrumented latency comparison with CTR timings. Excludes database, retrieval, HTTP and model load. One process; other desktop work may run. No speedup, saturation or latency target claimed.",
    "rows": rows,
}
with Path(sys.argv[3]).open("x", encoding="utf-8") as stream:
    json.dump(report, stream, sort_keys=True, indent=2, allow_nan=False)
print(
    json.dumps(
        {
            "passed": True,
            "rows": [
                {
                    "candidates": row["candidates"],
                    "feature_median_ms": row["feature_construction"]["median_ms"],
                    "inference_median_ms": row["batch_inference"]["median_ms"],
                    "v1_sort_median_ms": row["profiled_sorting"]["v1"]["median_ms"],
                    "v2_sort_median_ms": row["profiled_sorting"]["v2"]["median_ms"],
                }
                for row in rows
            ],
        }
    )
)

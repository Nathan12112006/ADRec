from typing import Literal

from pytest import MonkeyPatch

from app.core.observability import RollingTelemetry


def record(
    telemetry: RollingTelemetry,
    *,
    duration: float,
    population: Literal["selection", "error"] = "selection",
    variant: str | None = "control",
    stages: dict[str, float] | None = None,
) -> None:
    telemetry.record(
        route="/api/v1/recommendations",
        method="POST",
        status=200,
        duration_ms=duration,
        population=population,
        experiment_id="experiment-1",
        variant=variant,
        attribution="assigned" if variant else "outside_experiment",
        error_code=None,
        retrieval_mode=None,
        fallback_reason=None,
        stages=stages or {},
    )


def test_rolling_telemetry_caps_samples_and_reports_percentiles_and_stage_counts() -> None:
    telemetry = RollingTelemetry(max_records=2, max_bytes=4096)
    record(telemetry, duration=10, stages={"selection_ms": 4})
    record(telemetry, duration=20, stages={"selection_ms": 6})
    record(telemetry, duration=30, population="error")

    snapshot = telemetry.snapshot()
    assert snapshot["sample_count"] == 2
    assert snapshot["dropped_in_window"] == 1
    assert snapshot["coverage_complete"] is False
    assert snapshot["retained_bytes"] <= snapshot["max_bytes"]
    rows = {row["population"]: row for row in snapshot["populations"]}
    assert rows["selection"]["average_ms"] == 20
    assert rows["selection"]["p50_ms"] == 20
    assert rows["selection"]["p95_ms"] == 20
    assert rows["selection"]["stages"]["selection_ms"] == {
        "count": 1,
        "average_ms": 6,
        "p50_ms": 6,
        "p95_ms": 6,
        "p99_ms": 6,
    }
    assert rows["error"]["count"] == 1


def test_rolling_telemetry_marks_new_process_coverage_and_oversize_drops(
    monkeypatch: MonkeyPatch,
) -> None:
    from app.core import observability

    current = [100.0]
    monkeypatch.setattr(observability, "monotonic", lambda: current[0])
    telemetry = RollingTelemetry(retention_seconds=60, max_bytes=1024)
    record(telemetry, duration=1)
    current[0] = 161.0
    snapshot = telemetry.snapshot()
    assert snapshot["sample_count"] == 0
    assert snapshot["dropped_in_window"] == 0
    assert snapshot["coverage_complete"] is False

    telemetry.record(
        route="x" * 2000,
        method="GET",
        status=200,
        duration_ms=1,
        population="other",
        experiment_id=None,
        variant=None,
        attribution=None,
        error_code=None,
        retrieval_mode=None,
        fallback_reason=None,
        stages={},
    )
    assert telemetry.snapshot()["dropped_in_window"] == 1

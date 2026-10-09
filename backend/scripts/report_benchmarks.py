"""Write per-run client/server workload reports from a controlled benchmark matrix."""

from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime
from pathlib import Path
from typing import Any


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _phase_time(phases: list[dict[str, Any]], name: str) -> datetime | None:
    for phase in phases:
        if phase.get("event") == name and isinstance(phase.get("timestamp"), str):
            try:
                return datetime.fromisoformat(phase["timestamp"])
            except ValueError:
                return None
    return None


def _counter_delta(
    start: dict[str, Any] | None, end: dict[str, Any] | None
) -> dict[str, Any] | None:
    if not start or not end:
        return None
    fields = (
        "opportunities_started",
        "opportunities_completed",
        "selections",
        "no_ad_outcomes",
        "accepted_impressions",
        "accepted_clicks",
        "client_retry_attempts",
        "backend_confirmed_replays",
        "failed_opportunities",
    )
    delta: dict[str, Any] = {key: int(end.get(key, 0)) - int(start.get(key, 0)) for key in fields}
    errors: dict[str, Any] = {}
    for category in ("http_by_status", "application_by_code", "semantic_by_reason"):
        before = start.get("errors", {}).get(category, {})
        after = end.get("errors", {}).get(category, {})
        errors[category] = {
            key: int(after.get(key, 0)) - int(before.get(key, 0))
            for key in sorted(set(before) | set(after))
            if int(after.get(key, 0)) - int(before.get(key, 0)) != 0
        }
    for category in ("transport", "timeouts"):
        errors[category] = int(end.get("errors", {}).get(category, 0)) - int(
            start.get("errors", {}).get(category, 0)
        )
    delta["errors"] = errors
    started_delta = delta["opportunities_started"]
    completed_delta = delta["opportunities_completed"]
    delta["in_flight_at_measurement_end_estimate"] = max(0, started_delta - completed_delta)
    delta["cross_boundary_completions_estimate"] = max(0, completed_delta - started_delta)
    return delta


def _client_stats(path: Path, duration_seconds: float | None) -> dict[str, Any]:
    populations: list[dict[str, Any]] = []
    totals = {"requests": 0, "failures": 0}
    if path.is_file():
        with path.open(encoding="utf-8-sig", newline="") as source:
            for row in csv.DictReader(source):
                name = row.get("Name", "")
                if not name or name.lower() in {"aggregated", "total"}:
                    continue
                try:
                    requests = int(row.get("Request Count", "0") or 0)
                    failures = int(row.get("Failure Count", "0") or 0)
                except ValueError:
                    continue
                if requests == 0 and failures == 0:
                    continue
                totals["requests"] += requests
                totals["failures"] += failures

                def number(label: str, row: dict[str, str] = row) -> float | None:
                    raw = row.get(label)
                    if not raw or raw.lower() in {"n/a", "none"}:
                        return None
                    try:
                        return float(raw)
                    except ValueError:
                        return None

                populations.append(
                    {
                        "method": row.get("Type"),
                        "name": name,
                        "requests": requests,
                        "failures": failures,
                        "requests_per_second": (
                            requests / duration_seconds if duration_seconds else None
                        ),
                        "mean_ms": number("Average Response Time"),
                        "p50_ms": number("50%") or number("Median Response Time"),
                        "p95_ms": number("95%"),
                        "p99_ms": number("99%"),
                        "percentile_method": "Locust 2.46.7 response-time histogram approximation",
                    }
                )
    return {
        "scope": "measurement_window_locust_response_completions",
        "duration_seconds": duration_seconds,
        "requests": totals["requests"],
        "failures": totals["failures"],
        "requests_per_second": (
            totals["requests"] / duration_seconds if duration_seconds else None
        ),
        "populations": populations,
    }


def _server_snapshot(path: Path) -> dict[str, Any] | None:
    value = _read_json(path)
    if value is None:
        return None
    return {
        "scope": value.get("coverage_scope", "process_local_rolling_window"),
        "process_started_at": value.get("process_started_at"),
        "window_start": value.get("window_start"),
        "window_end": value.get("window_end"),
        "retention_seconds": value.get("retention_seconds"),
        "coverage_complete": value.get("coverage_complete"),
        "dropped_in_window": value.get("dropped_in_window"),
        "sample_count": value.get("sample_count"),
        "retained_bytes": value.get("retained_bytes"),
        "max_records": value.get("max_records"),
        "max_bytes": value.get("max_bytes"),
        "cache_health": value.get("cache_health"),
        "capabilities": value.get("capabilities"),
        "populations": [
            {
                "population": item.get("population"),
                "attribution": item.get("attribution"),
                "count": item.get("count"),
                "mean_ms": item.get("average_ms"),
                "p50_ms": item.get("p50_ms"),
                "p95_ms": item.get("p95_ms"),
                "p99_ms": item.get("p99_ms"),
                "error_codes": item.get("error_codes"),
                "retrieval_modes": item.get("retrieval_modes"),
                "fallback_reasons": item.get("fallback_reasons"),
                "stages": item.get("stages", {}),
            }
            for item in value.get("populations", [])
        ],
    }


def _report_run(run_directory: Path) -> dict[str, Any]:
    manifest = _read_json(run_directory / "run.json") or {}
    configuration = _read_json(run_directory / "configuration.json") or {}
    measurement = _read_json(run_directory / "measurement_counters.json") or {}
    start = measurement.get("start")
    end = measurement.get("end")
    counter_delta = _counter_delta(start, end)
    phases = manifest.get("phases", [])
    start_time = _phase_time(phases, "measurement_started")
    end_time = _phase_time(phases, "measurement_ended")
    duration = (end_time - start_time).total_seconds() if start_time and end_time else None
    locust_path = run_directory / "locust_stats.csv"
    client = _client_stats(locust_path, duration)
    if counter_delta is not None and duration:
        counter_delta["completed_opportunities_per_second"] = (
            counter_delta["opportunities_completed"] / duration
        )
        counter_delta["selections_per_second"] = counter_delta["selections"] / duration
    return {
        "run": run_directory.name,
        "status": manifest.get("status", "incomplete"),
        "exit_code": manifest.get("exit_code"),
        "configuration": configuration,
        "measurement": {
            "started_at": start_time.isoformat() if start_time else None,
            "ended_at": end_time.isoformat() if end_time else None,
            "actual_duration_seconds": duration,
            "actual_users": next(
                (
                    item.get("actual_users")
                    for item in phases
                    if item.get("event") == "ramp_complete"
                ),
                None,
            ),
            "completed_drain": any(item.get("event") == "drain_completed" for item in phases),
            "counters": counter_delta,
            "counter_scope_note": (
                "Cumulative snapshots bracket the measurement. A task crossing a phase boundary "
                "can contribute its completion to the adjacent phase."
            ),
        },
        "client_http": client,
        "server_metrics": {
            "scope_note": (
                "AdFlow telemetry is a process-local rolling sample window, not run-isolated. "
                "Snapshots may include warm-up, observer requests, prior traffic or later drain."
            ),
            "measurement_start": _server_snapshot(
                run_directory / "server_metrics_measurement_start.json"
            ),
            "measurement_end": _server_snapshot(
                run_directory / "server_metrics_measurement_end.json"
            ),
        },
        "errors": {
            "measurement_window_locust_failures": client["failures"],
            "workload_counter_delta": counter_delta.get("errors") if counter_delta else None,
            "whole_run_summary": manifest.get("summary", {}).get("errors"),
        },
        "resources": {
            "host_before": manifest.get("host_resources_before"),
            "host_after": manifest.get("host_resources_after"),
            "api_container_before": manifest.get("api_container_usage_before"),
            "api_container_after": manifest.get("api_container_usage_after"),
            "sampling_note": "Boundary snapshots only; these values are not peak resource usage.",
        },
        "artifacts": manifest.get("artifacts", []),
    }


def _format(value: Any, digits: int = 2) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, float):
        return f"{value:.{digits}f}"
    return str(value)


def _markdown(reports: list[dict[str, Any]]) -> str:
    lines = [
        "# Controlled benchmark report",
        "",
        "Each repetition is reported separately. Percentiles are never averaged across runs.",
        "Locust client percentiles use the pinned version's approximate response-time histogram.",
        "AdFlow server percentiles are nearest-rank values over retained process-local samples;",
        "bounded rolling snapshots may include traffic outside measurement.",
        "Resource values are boundary snapshots, not peaks.",
        "",
        "## Runs",
        "",
        "| Run | State | Users | Seconds | HTTP | HTTP/s | Opp/s | Failed |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for report in reports:
        configuration = report.get("configuration", {})
        measurement = report.get("measurement", {})
        counters = measurement.get("counters") or {}
        client = report.get("client_http", {})
        lines.append(
            (
                "| {run} | {status} | {users} | {duration} | {requests} | "
                "{rps} | {ops} | {failures} |"
            ).format(
                run=report["run"],
                status=report["status"],
                users=measurement.get("actual_users") or configuration.get("users", "n/a"),
                duration=_format(measurement.get("actual_duration_seconds")),
                requests=client.get("requests", 0),
                rps=_format(client.get("requests_per_second")),
                ops=_format(counters.get("completed_opportunities_per_second")),
                failures=client.get("failures", 0),
            )
        )
    for report in reports:
        lines.extend(["", f"## {report['run']}", ""])
        lines.append("### Client HTTP by endpoint and response population")
        lines.append("")
        lines.append(
            "| Method | Name | Requests | Failed | Mean ms | P50 ms | P95 ms | P99 ms | RPS |"
        )
        lines.append("| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |")
        for item in report.get("client_http", {}).get("populations", []):
            lines.append(
                (
                    "| {method} | {name} | {requests} | {failures} | {mean} | "
                    "{p50} | {p95} | {p99} | {rps} |"
                ).format(
                    method=item.get("method", ""),
                    name=item.get("name", ""),
                    requests=item.get("requests", 0),
                    failures=item.get("failures", 0),
                    mean=_format(item.get("mean_ms")),
                    p50=_format(item.get("p50_ms")),
                    p95=_format(item.get("p95_ms")),
                    p99=_format(item.get("p99_ms")),
                    rps=_format(item.get("requests_per_second")),
                )
            )
        measurement = report.get("measurement", {})
        counters = measurement.get("counters")
        lines.extend(["", "### Durable workload counters", ""])
        if counters is None:
            lines.append("Measurement counter snapshots are unavailable.")
        else:
            lines.append(
                (
                    "Completed opportunities: {completed}; starts: {started}; "
                    "selections: {selections}; no-ad: {no_ad}; impressions: {impressions}; "
                    "clicks: {clicks}; retries: {retries}; backend replays: {replays}; "
                    "failed: {failed}; completed opportunities/s: {ops}."
                ).format(
                    completed=counters.get("opportunities_completed"),
                    started=counters.get("opportunities_started"),
                    selections=counters.get("selections"),
                    no_ad=counters.get("no_ad_outcomes"),
                    impressions=counters.get("accepted_impressions"),
                    clicks=counters.get("accepted_clicks"),
                    retries=counters.get("client_retry_attempts"),
                    replays=counters.get("backend_confirmed_replays"),
                    failed=counters.get("failed_opportunities"),
                    ops=_format(counters.get("completed_opportunities_per_second")),
                )
            )
            lines.append(
                f"Error categories: `{json.dumps(counters.get('errors', {}), sort_keys=True)}`"
            )
        lines.extend(["", "### Server process-window telemetry", ""])
        snapshots = report.get("server_metrics", {})
        for label in ("measurement_start", "measurement_end"):
            snapshot = snapshots.get(label)
            lines.append(f"**{label}**: ")
            if snapshot is None:
                lines.append("unavailable.")
                continue
            lines.append(
                "window {start} to {end}; retained {samples}/{limit}; dropped {dropped}; "
                "coverage complete={coverage}.".format(
                    start=snapshot.get("window_start"),
                    end=snapshot.get("window_end"),
                    samples=snapshot.get("sample_count"),
                    limit=snapshot.get("max_records"),
                    dropped=snapshot.get("dropped_in_window"),
                    coverage=snapshot.get("coverage_complete"),
                )
            )
            lines.append("")
            lines.append(
                "| Population | N | Mean ms | P50 ms | P95 ms | P99 ms | Stage p50/p95/p99 ms |"
            )
            lines.append("| --- | ---: | ---: | ---: | ---: | ---: | --- |")
            for population in snapshot.get("populations", []):
                stages = "; ".join(
                    f"{name} {stage.get('p50_ms')}/{stage.get('p95_ms')}/{stage.get('p99_ms')}"
                    for name, stage in sorted(population.get("stages", {}).items())
                )
                lines.append(
                    (
                        "| {name}/{attribution} | {count} | {mean} | {p50} | "
                        "{p95} | {p99} | {stages} |"
                    ).format(
                        name=population.get("population"),
                        attribution=population.get("attribution") or "n/a",
                        count=population.get("count"),
                        mean=_format(population.get("mean_ms")),
                        p50=_format(population.get("p50_ms")),
                        p95=_format(population.get("p95_ms")),
                        p99=_format(population.get("p99_ms")),
                        stages=stages,
                    )
                )
        lines.extend(["", "### Coverage and resources", ""])
        lines.append(
            f"Measurement: {measurement.get('started_at')} to {measurement.get('ended_at')}; "
            f"actual {measurement.get('actual_duration_seconds')} seconds; "
            f"drain completed={measurement.get('completed_drain')}."
        )
        lines.append(
            "Resource snapshots: " + json.dumps(report.get("resources", {}), sort_keys=True)
        )
        lines.append("")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("matrix", type=Path, help="matrix directory or its matrix.json file")
    args = parser.parse_args()
    matrix_path = args.matrix / "matrix.json" if args.matrix.is_dir() else args.matrix
    if not matrix_path.is_file():
        parser.error("matrix.json was not found")
    matrix_directory = matrix_path.parent
    matrix = _read_json(matrix_path) or {}
    report_directories = sorted(
        path
        for path in matrix_directory.iterdir()
        if path.is_dir() and (path / "run.json").is_file()
    )
    reports = [_report_run(path) for path in report_directories]
    if not reports:
        parser.error("matrix contains no run manifests")
    output = {
        "matrix": matrix,
        "methodology": {
            "repetition_percentiles": "preserved per run; never averaged",
            "locust_percentiles": "pinned Locust response-time histogram approximation",
            "server_percentiles": "nearest-rank over retained process-local samples",
            "server_scope": "rolling process window; not run-isolated",
            "resource_scope": "before/after snapshots; not peak usage",
        },
        "runs": reports,
    }
    (matrix_directory / "report.json").write_text(
        json.dumps(output, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (matrix_directory / "report.md").write_text(_markdown(reports), encoding="utf-8")
    print(f"Wrote {matrix_directory / 'report.md'} and {matrix_directory / 'report.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

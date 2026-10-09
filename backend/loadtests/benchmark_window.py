"""Locust controller for explicit post-ramp warm-up, measurement and finite drain."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from importlib import import_module
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.request import urlopen

import gevent
from locust import events
from locust.stats import StatsCSVFileWriter
from redis import Redis

_environment: Any | None = None

# Locust 2.46.7 closes its CSV handles before killing the background stats
# writer. Track that writer and stop it first so shutdown does not race a final
# history update against closed files.
_original_spawn = gevent.spawn
_stats_writers: dict[int, Any] = {}
_original_close_files = StatsCSVFileWriter.close_files


def _tracked_spawn(function: Any, *args: Any, **kwargs: Any) -> Any:
    greenlet = _original_spawn(function, *args, **kwargs)
    writer = getattr(function, "__self__", None)
    if (
        isinstance(writer, StatsCSVFileWriter)
        and getattr(function, "__name__", None) == "stats_writer"
    ):
        _stats_writers[id(writer)] = greenlet
    return greenlet


def _close_stats_files(writer: StatsCSVFileWriter) -> None:
    greenlet = _stats_writers.pop(id(writer), None)
    if greenlet is not None and not greenlet.dead:
        greenlet.kill(block=True)
    _original_close_files(writer)


gevent.spawn = _tracked_spawn
StatsCSVFileWriter.close_files = _close_stats_files


def _record(path: Path, event: str, **values: Any) -> None:
    record = {"event": event, "timestamp": datetime.now(timezone.utc).isoformat(), **values}
    with path.open("a", encoding="utf-8") as output:
        output.write(json.dumps(record, sort_keys=True) + "\n")
        output.flush()


def _capture_server_metrics(environment: Any, run_directory: Path, phase: str) -> None:
    host = getattr(environment, "host", None)
    if not host:
        _record(Path(run_directory) / "phases.jsonl", "server_metrics_capture_failed", phase=phase)
        return
    try:
        with urlopen(host.rstrip("/") + "/api/v1/metrics", timeout=5) as response:
            metrics = json.load(response)
        (run_directory / f"server_metrics_{phase}.json").write_text(
            json.dumps(metrics, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    except (OSError, URLError, ValueError) as error:
        _record(
            run_directory / "phases.jsonl",
            "server_metrics_capture_failed",
            phase=phase,
            reason=type(error).__name__,
        )


def _snapshot_workload_counters() -> dict[str, Any] | None:
    workload = import_module("adflow_workloads")
    return workload.snapshot_counters()


@events.init_command_line_parser.add_listener
def add_window_options(parser: Any) -> None:
    parser.add_argument("--adflow-warmup-seconds", type=int, default=60)
    parser.add_argument("--adflow-measurement-seconds", type=int, default=180)
    parser.add_argument("--adflow-drain-seconds", type=int, default=30)
    parser.add_argument("--adflow-run-directory", type=Path, required=True)
    parser.add_argument("--adflow-cache-state", choices=("cold", "warm"), default="warm")
    parser.add_argument("--adflow-cache-container", default="adflow-redis-1")
    parser.add_argument("--adflow-cache-enabled", action="store_true")
    parser.add_argument("--adflow-dataset-id", required=True)


def _clear_dataset_cache(dataset_id: str) -> int:
    redis_url = os.environ.get("ADFLOW_REDIS_URL")
    if not redis_url:
        raise RuntimeError("Redis URL is required for the requested cold-cache reset")
    pattern = f"adflow:{dataset_id}:profile:user-profile-v1:*"
    prefix = f"adflow:{dataset_id}:profile:user-profile-v1:"
    deleted = 0
    client = Redis.from_url(redis_url, socket_connect_timeout=1, socket_timeout=1)
    try:
        batch: list[str] = []
        for key in client.scan_iter(match=pattern, count=500):
            decoded = key.decode() if isinstance(key, bytes) else str(key)
            if decoded.startswith(prefix):
                batch.append(decoded)
            if len(batch) >= 500:
                deleted += client.unlink(*batch)
                batch.clear()
        if batch:
            deleted += client.unlink(*batch)
    finally:
        client.close()
    return deleted


@events.test_start.add_listener
def mark_run_start(environment: Any, **_: Any) -> None:
    global _environment
    _environment = environment
    options = environment.parsed_options
    if (
        min(
            options.adflow_warmup_seconds,
            options.adflow_measurement_seconds,
            options.adflow_drain_seconds,
        )
        < 0
        or options.adflow_measurement_seconds == 0
    ):
        raise ValueError("benchmark warm-up/drain must be non-negative and measurement positive")
    options.adflow_run_directory.mkdir(parents=True, exist_ok=True)
    _record(options.adflow_run_directory / "phases.jsonl", "run_started")


@events.spawning_complete.add_listener
def schedule_measurement(user_count: int, **_: Any) -> None:
    environment = _environment
    if environment is None:
        raise RuntimeError("Locust environment was not initialized before ramp completion")
    options = environment.parsed_options
    phases = options.adflow_run_directory / "phases.jsonl"
    _record(phases, "ramp_complete", actual_users=user_count)

    def measure_and_stop() -> None:
        gevent.sleep(options.adflow_warmup_seconds)
        if options.adflow_cache_state == "cold" and options.adflow_cache_enabled:
            try:
                deleted = _clear_dataset_cache(options.adflow_dataset_id)
            except (OSError, RuntimeError) as error:
                _record(phases, "cache_reset_failed", reason=type(error).__name__)
                environment.process_exit_code = 1
                environment.runner.quit()
                return
            _record(
                phases,
                "cold_cache_reset",
                dataset_id=options.adflow_dataset_id,
                deleted_dataset_profile_keys=deleted,
            )
        else:
            _record(
                phases,
                "cache_preparation_complete",
                cache_state=options.adflow_cache_state,
                cache_enabled=options.adflow_cache_enabled,
            )
        _capture_server_metrics(environment, options.adflow_run_directory, "measurement_start")
        counters_start = _snapshot_workload_counters()
        environment.runner.stats.reset_all()
        _record(
            phases,
            "measurement_started",
            warmup_seconds=options.adflow_warmup_seconds,
            counters=counters_start,
        )
        gevent.sleep(options.adflow_measurement_seconds)
        _capture_server_metrics(environment, options.adflow_run_directory, "measurement_end")
        counters_end = _snapshot_workload_counters()
        (options.adflow_run_directory / "measurement_counters.json").write_text(
            json.dumps(
                {
                    "scope": "cumulative workload counter snapshots bracketing measurement",
                    "start": counters_start,
                    "end": counters_end,
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        _record(
            phases,
            "measurement_ended",
            measurement_seconds=options.adflow_measurement_seconds,
            counters=counters_end,
        )
        _record(phases, "drain_started", drain_timeout_seconds=options.adflow_drain_seconds)
        environment.runner.stop()
        _record(phases, "drain_completed")
        environment.runner.quit()

    gevent.spawn(measure_and_stop)

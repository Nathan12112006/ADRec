"""Bounded per-request stage timings, with no global metric history."""

import json
import logging
from collections import deque
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from math import ceil
from threading import Lock
from time import monotonic, perf_counter
from typing import Any, Literal

stages: ContextVar[dict[str, float] | None] = ContextVar("request_stages", default=None)
logger = logging.getLogger("adflow.requests")


@dataclass(frozen=True)
class TelemetryRecord:
    observed_at: datetime
    monotonic_at: float
    route: str
    method: str
    status: int
    duration_ms: float
    population: Literal["selection", "no_ad", "replay", "impression", "click", "error", "other"]
    experiment_id: str | None
    variant: str | None
    attribution: Literal["assigned", "outside_experiment", "unknown"] | None
    error_code: str | None
    retrieval_mode: str | None
    fallback_reason: str | None
    stages: dict[str, float]
    size_bytes: int


class RollingTelemetry:
    """Bounded process-local request observations; durable events remain authoritative."""

    def __init__(
        self, *, retention_seconds: int = 900, max_records: int = 10_000, max_bytes: int = 8_000_000
    ) -> None:
        if not 1 <= retention_seconds <= 900 or max_records < 1 or max_bytes < 1024:
            raise ValueError("invalid telemetry bounds")
        self.retention_seconds = retention_seconds
        self.max_records = max_records
        self.max_bytes = max_bytes
        self.process_started_at = datetime.now(timezone.utc)
        self._records: deque[TelemetryRecord] = deque()
        self._dropped_buckets: deque[tuple[int, int]] = deque()
        self._bytes = 0
        self._lock = Lock()

    def _expire(self, now: float) -> None:
        cutoff = now - self.retention_seconds
        while self._records and self._records[0].monotonic_at < cutoff:
            expired = self._records.popleft()
            self._bytes -= expired.size_bytes
        while self._dropped_buckets and self._dropped_buckets[0][0] + 1 < cutoff:
            self._dropped_buckets.popleft()

    def _mark_dropped(self, now: float) -> None:
        bucket = int(now)
        if self._dropped_buckets and self._dropped_buckets[-1][0] == bucket:
            previous, count = self._dropped_buckets.pop()
            self._dropped_buckets.append((previous, count + 1))
        else:
            self._dropped_buckets.append((bucket, 1))

    def record(
        self,
        *,
        route: str,
        method: str,
        status: int,
        duration_ms: float,
        population: Literal[
            "selection", "no_ad", "replay", "impression", "click", "error", "other"
        ],
        experiment_id: str | None,
        variant: str | None,
        attribution: Literal["assigned", "outside_experiment", "unknown"] | None,
        error_code: str | None,
        retrieval_mode: str | None,
        fallback_reason: str | None,
        stages: dict[str, float],
    ) -> None:
        value = {
            "route": route,
            "method": method,
            "status": status,
            "duration_ms": duration_ms,
            "population": population,
            "experiment_id": experiment_id,
            "variant": variant,
            "attribution": attribution,
            "error_code": error_code,
            "retrieval_mode": retrieval_mode,
            "fallback_reason": fallback_reason,
            "stages": stages,
        }
        size = len(json.dumps(value, separators=(",", ":"), allow_nan=False).encode()) + 128
        with self._lock:
            now = monotonic()
            self._expire(now)
            if size > self.max_bytes:
                self._mark_dropped(now)
                return
            while self._records and (
                len(self._records) >= self.max_records or self._bytes + size > self.max_bytes
            ):
                removed = self._records.popleft()
                self._bytes -= removed.size_bytes
                self._mark_dropped(now)
            record = TelemetryRecord(
                datetime.now(timezone.utc),
                now,
                route,
                method,
                status,
                duration_ms,
                population,
                experiment_id,
                variant,
                attribution,
                error_code,
                retrieval_mode,
                fallback_reason,
                dict(stages),
                size,
            )
            self._records.append(record)
            self._bytes += size

    def snapshot(self, *, now: datetime | None = None) -> dict[str, Any]:
        observed = now or datetime.now(timezone.utc)
        if observed.tzinfo is None:
            raise ValueError("snapshot time must be timezone-aware")
        window_start = observed - timedelta(seconds=self.retention_seconds)
        with self._lock:
            mono_now = monotonic()
            self._expire(mono_now)
            records = tuple(item for item in self._records if item.observed_at <= observed)
            cutoff = mono_now - self.retention_seconds
            dropped = sum(count for second, count in self._dropped_buckets if second + 1 >= cutoff)
            retained_bytes = sum(item.size_bytes for item in records)
        groups: dict[tuple[str | None, str | None, str, str | None], list[TelemetryRecord]] = {}
        for record in records:
            key = (record.experiment_id, record.variant, record.population, record.attribution)
            groups.setdefault(key, []).append(record)
        populations = []
        for (experiment_id, variant, population, attribution), items in sorted(
            groups.items(),
            key=lambda item: (item[0][0] or "", item[0][1] or "", item[0][2], item[0][3] or ""),
        ):
            durations = sorted(item.duration_ms for item in items)
            stage_timings = {}
            for name in sorted({name for item in items for name in item.stages}):
                samples = sorted(item.stages[name] for item in items if name in item.stages)
                stage_timings[name] = {
                    "count": len(samples),
                    "average_ms": sum(samples) / len(samples),
                    "p50_ms": samples[max(0, ceil(0.50 * len(samples)) - 1)],
                    "p95_ms": samples[max(0, ceil(0.95 * len(samples)) - 1)],
                    "p99_ms": samples[max(0, ceil(0.99 * len(samples)) - 1)],
                }
            populations.append(
                {
                    "experiment_id": experiment_id,
                    "variant": variant,
                    "population": population,
                    "attribution": attribution,
                    "count": len(items),
                    "average_ms": sum(durations) / len(durations),
                    "p50_ms": durations[max(0, ceil(0.50 * len(durations)) - 1)],
                    "p95_ms": durations[max(0, ceil(0.95 * len(durations)) - 1)],
                    "p99_ms": durations[max(0, ceil(0.99 * len(durations)) - 1)],
                    "error_codes": {
                        code: sum(item.error_code == code for item in items)
                        for code in sorted(
                            {item.error_code for item in items if item.error_code is not None}
                        )
                    },
                    "retrieval_modes": {
                        mode: sum(item.retrieval_mode == mode for item in items)
                        for mode in sorted(
                            {item.retrieval_mode for item in items if item.retrieval_mode}
                        )
                    },
                    "fallback_reasons": {
                        reason: sum(item.fallback_reason == reason for item in items)
                        for reason in sorted(
                            {item.fallback_reason for item in items if item.fallback_reason}
                        )
                    },
                    "stages": stage_timings,
                }
            )
        covered_from = max(window_start, self.process_started_at)
        return {
            "window_start": window_start.isoformat(),
            "window_end": observed.isoformat(),
            "covered_from": covered_from.isoformat(),
            "process_started_at": self.process_started_at.isoformat(),
            "retention_seconds": self.retention_seconds,
            "sample_count": len(records),
            "retained_bytes": retained_bytes,
            "max_records": self.max_records,
            "max_bytes": self.max_bytes,
            "dropped_in_window": dropped,
            "coverage_complete": self.process_started_at <= window_start and dropped == 0,
            "populations": populations,
        }


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        return json.dumps(record.__dict__["request_context"], sort_keys=True)


def configure_logging(level: str) -> None:
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(JsonFormatter())
        logger.addHandler(handler)
    logger.setLevel(level)
    logger.propagate = False


@contextmanager
def stage(name: str) -> Iterator[None]:
    started = perf_counter()
    try:
        yield
    finally:
        timings = stages.get()
        if timings is not None:
            timings[name] = timings.get(name, 0.0) + (perf_counter() - started) * 1000

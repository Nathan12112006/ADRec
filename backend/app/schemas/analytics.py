"""Typed backend summaries for the read-only dashboard."""

from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class AnalyticsOverviewResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dataset_id: UUID | None
    dataset_created_at: datetime | None
    as_of: datetime
    availability: Literal["available", "empty"]
    window_scope: Literal["dataset_lifetime"] = "dataset_lifetime"
    window_start: datetime | None
    window_end: datetime
    coverage: Literal["durable_postgresql_snapshot", "empty_dataset"]
    provisional: bool
    event_window_hours: int = 24
    event_windows_closed_through: datetime
    users: int
    advertisers: int
    active_advertisers: int
    ads: int
    active_ads: int
    recommendations: int
    request_outcomes: int
    no_ad_outcomes: int
    exposed_users: int
    impressions: int
    clicks: int
    observed_ctr: Decimal | None
    simulated_revenue: Decimal
    revenue_unit: Literal["simulated_dollars"] = "simulated_dollars"


class StageMetric(BaseModel):
    model_config = ConfigDict(extra="forbid")

    count: int
    average_ms: float
    p50_ms: float
    p95_ms: float
    p99_ms: float


class TelemetryPopulation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    experiment_id: str | None
    variant: Literal["control", "treatment"] | None
    population: Literal["selection", "no_ad", "replay", "impression", "click", "error", "other"]
    attribution: Literal["assigned", "outside_experiment", "unknown"] | None
    count: int
    average_ms: float
    p50_ms: float
    p95_ms: float
    p99_ms: float
    error_codes: dict[str, int]
    retrieval_modes: dict[str, int]
    fallback_reasons: dict[str, int]
    stages: dict[str, StageMetric]


class CacheMetricsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scope: Literal["process_lifetime"] = "process_lifetime"
    hits: int
    misses: int
    invalid_payloads: int
    read_errors: int
    write_errors: int
    invalidation_errors: int
    hit_ratio: float | None
    bypasses: dict[str, int]


class RuntimeCapabilities(BaseModel):
    model_config = ConfigDict(extra="forbid")

    retrieval: Literal["hnsw", "flat", "exact_fallback"]
    retrieval_failure: str | None
    ranking_v1: bool
    ranking_v2: bool
    ctr_model_id: str | None


class MetricsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    as_of: datetime
    window_start: datetime
    window_end: datetime
    covered_from: datetime
    process_started_at: datetime
    retention_seconds: int
    coverage_complete: bool
    coverage_scope: Literal["process_local_rolling_window"] = "process_local_rolling_window"
    dropped_in_window: int
    sample_count: int
    retained_bytes: int
    max_records: int
    max_bytes: int
    latency_unit: Literal["milliseconds"] = "milliseconds"
    populations: list[TelemetryPopulation]
    cache: CacheMetricsResponse
    cache_health: Literal["disabled", "ready", "degraded"]
    capabilities: RuntimeCapabilities
    database_readiness_path: Literal["/health/ready"] = "/health/ready"

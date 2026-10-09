export type AnalyticsOverview = {
  dataset_id: string | null
  dataset_created_at: string | null
  as_of: string
  availability: 'available' | 'empty'
  window_scope: 'dataset_lifetime'
  window_start: string | null
  window_end: string
  coverage: 'durable_postgresql_snapshot' | 'empty_dataset'
  provisional: boolean
  event_window_hours: number
  event_windows_closed_through: string
  users: number
  advertisers: number
  active_advertisers: number
  ads: number
  active_ads: number
  recommendations: number
  request_outcomes: number
  no_ad_outcomes: number
  exposed_users: number
  impressions: number
  clicks: number
  observed_ctr: string | null
  simulated_revenue: string
  revenue_unit: 'simulated_dollars'
}

export type ExperimentSummary = {
  id: string
  name: string
  status: 'draft' | 'running' | 'stopped'
  control_basis_points: number
  control_strategy: string
  treatment_strategy: string
  model_id: string
  retrieval_mode: string
  candidate_limit: number
  search_limit: number
  hnsw_ef_search: number | null
  created_at: string
  started_at: string | null
  stopped_at: string | null
}

export type FallbackMetric = { mode: string; reason: string; count: number }
export type ExperimentVariantMetrics = {
  attempts: number
  attempted_users: number
  no_ad_outcomes: number
  recommendations: number
  exposed_users: number
  impressions: number
  clicks: number
  simulated_revenue: string
  ctr: string | null
  revenue_per_exposed_user: string | null
  fallbacks: FallbackMetric[]
}

type ComparisonValue = string | number | null
export type ExperimentComparisonMetric = {
  control: ComparisonValue
  treatment: ComparisonValue
  absolute_difference: ComparisonValue
  relative_lift_percent: string | null
}

export type ExperimentResults = {
  experiment_id: string
  experiment_status: 'draft' | 'running' | 'stopped'
  synthetic: boolean
  statistical_test: null
  cohort_start: string
  cohort_end_exclusive: string
  as_of: string
  provisional: boolean
  event_window_hours: number
  event_windows_closed_through: string
  variants: Record<'control' | 'treatment', ExperimentVariantMetrics>
  comparison: Record<string, ExperimentComparisonMetric>
  latency_populations: TelemetryPopulation[]
  telemetry: ExperimentTelemetry
}

export type StageMetric = { count: number; average_ms: number; p50_ms: number; p95_ms: number; p99_ms: number }
export type TelemetryPopulation = {
  experiment_id: string | null
  variant: 'control' | 'treatment' | null
  population: 'selection' | 'no_ad' | 'replay' | 'impression' | 'click' | 'error' | 'other'
  attribution: 'assigned' | 'outside_experiment' | 'unknown' | null
  count: number
  average_ms: number
  p50_ms: number
  p95_ms: number
  p99_ms: number
  error_codes: Record<string, number>
  retrieval_modes: Record<string, number>
  fallback_reasons: Record<string, number>
  stages: Record<string, StageMetric>
}

export type ExperimentTelemetry = {
  window_start: string | null
  window_end: string | null
  covered_from: string | null
  process_started_at: string | null
  coverage_complete: boolean
  dropped_in_window: number | null
  unknown_attribution_errors: TelemetryPopulation[]
}

export class ApiError extends Error {
  readonly status: number

  constructor(message: string, status: number) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

export async function getJson<T>(path: string, signal?: AbortSignal): Promise<T> {
  let response: Response
  try {
    response = await fetch(path, {
      headers: { Accept: 'application/json' },
      signal,
    })
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') throw error
    throw new ApiError('The API could not be reached.', 0)
  }

  const payload: unknown = await response.json().catch(() => null)
  if (!response.ok) {
    const message = isRecord(payload) && isRecord(payload.error) && typeof payload.error.message === 'string'
      ? payload.error.message
      : `The API returned status ${response.status}.`
    throw new ApiError(message, response.status)
  }
  return payload as T
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null
}

export type PerformanceStage = { count: number; average_ms: number; p50_ms: number; p95_ms: number; p99_ms: number }
export type PerformancePopulation = {
  experiment_id: string | null
  variant: 'control' | 'treatment' | null
  population: 'selection' | 'no_ad' | 'replay' | 'impression' | 'click' | 'error' | 'other'
  attribution: 'assigned' | 'outside_experiment' | 'unknown' | null
  count: number
  average_ms: number
  p50_ms: number
  p95_ms: number
  p99_ms: number
  error_codes: Record<string, number>
  retrieval_modes: Record<string, number>
  fallback_reasons: Record<string, number>
  stages: Record<string, PerformanceStage>
}
export type PerformanceMetrics = {
  as_of: string
  window_start: string
  window_end: string
  covered_from: string
  process_started_at: string
  retention_seconds: number
  coverage_complete: boolean
  coverage_scope: 'process_local_rolling_window'
  dropped_in_window: number
  sample_count: number
  retained_bytes: number
  max_records: number
  max_bytes: number
  latency_unit: 'milliseconds'
  populations: PerformancePopulation[]
  cache: { scope: 'process_lifetime'; hits: number; misses: number; invalid_payloads: number; read_errors: number; write_errors: number; invalidation_errors: number; hit_ratio: number | null; bypasses: Record<string, number> }
  cache_health: 'disabled' | 'ready' | 'degraded'
  capabilities: { retrieval: 'hnsw' | 'flat' | 'exact_fallback'; retrieval_failure: string | null; ranking_v1: boolean; ranking_v2: boolean; ctr_model_id: string | null }
  database_readiness_path: '/health/ready'
}

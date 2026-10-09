import { ApiError, type PerformanceMetrics, type PerformancePopulation } from './api'
import { usePolling } from './usePolling'

const count = new Intl.NumberFormat()
const bytes = (value: number) => value < 1024 * 1024 ? `${(value / 1024).toFixed(0)} KB` : `${(value / 1024 / 1024).toFixed(1)} MB`
const date = (value: string) => new Date(value).toLocaleTimeString()
const title = (value: string) => value.replaceAll('_', ' ').replace(/\b\w/g, (letter) => letter.toUpperCase())
function message(error: Error | null) { return error instanceof ApiError ? error.message : 'The API could not be reached.' }

function PopulationTable({ populations }: { populations: PerformancePopulation[] }) {
  const rows = [...populations].sort((a, b) => a.population.localeCompare(b.population) || (a.variant ?? '').localeCompare(b.variant ?? '') || (a.attribution ?? '').localeCompare(b.attribution ?? ''))
  if (rows.length === 0) return <p className="performance-empty">No observations have been retained in this process window yet.</p>
  return <div className="performance-table-scroll" role="region" aria-label="Rolling performance by response and event population" tabIndex={0}><table className="performance-table">
    <thead><tr><th scope="col">Population</th><th scope="col">Samples</th><th scope="col">Avg ms</th><th scope="col">p50 ms</th><th scope="col">p95 ms</th><th scope="col">p99 ms</th><th scope="col">Details</th></tr></thead>
    <tbody>{rows.map((item) => {
      const details = [
        ...Object.entries(item.error_codes).map(([key, value]) => `${key} ${count.format(value)}`),
        ...Object.entries(item.fallback_reasons).map(([key, value]) => `fallback ${key} ${count.format(value)}`),
      ]
      return <tr key={`${item.population}-${item.variant}-${item.attribution}`}><th scope="row">{title(item.population)}<small>{item.variant ?? item.attribution ?? 'all'}</small></th><td>{count.format(item.count)}</td><td>{item.average_ms.toFixed(2)}</td><td>{item.p50_ms.toFixed(2)}</td><td>{item.p95_ms.toFixed(2)}</td><td>{item.p99_ms.toFixed(2)}</td><td>{details.join(' · ') || '—'}</td></tr>
    })}</tbody>
  </table></div>
}

export function PerformancePage({ paused }: { paused: boolean }) {
  const metrics = usePolling<PerformanceMetrics>('/api/v1/metrics', paused)
  const readiness = usePolling<{ status: string; dependencies: { database: string; redis: string }; capabilities: PerformanceMetrics['capabilities'] }>('/health/ready', paused)
  if (!metrics.data) {
    if (metrics.error) return <div className="notice notice-error" role="alert"><strong>Performance metrics unavailable</strong><span>{message(metrics.error)}</span><button className="button button-quiet" onClick={() => void metrics.refresh()}>Try again</button></div>
    return <div className="loading-panel" role="status"><span className="loading-mark" /><div><strong>Loading performance window</strong><span>Reading process telemetry and dependency capabilities…</span></div></div>
  }
  const data = metrics.data
  const requests = data.populations.filter((item) => ['selection', 'no_ad', 'replay', 'error', 'other'].includes(item.population)).reduce((sum, item) => sum + item.count, 0)
  const failures = data.populations.filter((item) => item.population === 'error').reduce((sum, item) => sum + item.count, 0)
  const resetAt = date(data.process_started_at)
  return <div className="performance-page">
    {metrics.stale && <div className="notice notice-warning" role="status">Showing the last successful metrics snapshot. Latest refresh failed: {message(metrics.error)}</div>}
    <div className={`coverage-banner ${data.coverage_complete ? 'complete' : 'incomplete'}`} role="status"><span className="coverage-mark"/><div><strong>{data.coverage_complete ? 'Full rolling-window coverage' : 'Partial rolling-window coverage'}</strong><span>Observed {date(data.covered_from)}–{date(data.window_end)} · process started {resetAt} · {data.dropped_in_window === 0 ? 'no samples dropped' : `${count.format(data.dropped_in_window)} samples dropped`}</span></div><small>{count.format(data.sample_count)} retained</small></div>
    <div className="performance-summary">
      <article className="overview-metric"><span className="metric-label">REQUEST RESPONSES</span><strong className="metric-value">{count.format(requests)}</strong><small className="metric-caption">selected, replay, no-ad, error and other</small></article>
      <article className="overview-metric"><span className="metric-label">FAILURES</span><strong className="metric-value">{count.format(failures)}</strong><small className="metric-caption">retained error responses</small></article>
      <article className="overview-metric"><span className="metric-label">CLIENT EVENTS</span><strong className="metric-value">{count.format(data.populations.filter((item) => ['impression', 'click'].includes(item.population)).reduce((sum, item) => sum + item.count, 0))}</strong><small className="metric-caption">impressions and clicks, separate from responses</small></article>
      <article className="overview-metric"><span className="metric-label">WINDOW THROUGHPUT</span><strong className="metric-value">{(requests / Math.max(1, (Date.parse(data.window_end) - Date.parse(data.covered_from)) / 1000)).toFixed(2)}</strong><small className="metric-caption">response observations per second covered</small></article>
    </div>
    <section className="overview-panel performance-table-panel"><div className="panel-heading"><div><span className="eyebrow">ROLLING 15 MINUTES · {date(data.window_start)} TO {date(data.window_end)}</span><h2>Latency by population</h2></div><span className="panel-unit">MILLISECONDS</span></div><PopulationTable populations={data.populations}/><p className="chart-footnote">Percentiles use nearest rank over retained request observations. They are sample estimates, not histogram buckets or service level guarantees.</p></section>
    <div className="performance-lower">
      <section className="overview-panel capability-panel"><div className="panel-heading"><div><span className="eyebrow">CURRENT SERVICE CAPABILITIES</span><h2>Dependencies &amp; strategies</h2></div><span className={`health-pill ${readiness.data?.status === 'ready' ? 'healthy' : readiness.error ? 'degraded' : ''}`}>{readiness.data?.status ?? (readiness.error ? 'unavailable' : 'checking')}</span></div>
        <dl className="inventory-list"><div className="inventory-row"><dt>PostgreSQL</dt><dd>{readiness.data?.dependencies.database ?? '—'}</dd></div><div className="inventory-row"><dt>Redis / profile cache</dt><dd>{readiness.data?.dependencies.redis ?? data.cache_health}</dd></div><div className="inventory-row"><dt>Candidate retrieval</dt><dd>{data.capabilities.retrieval}</dd></div><div className="inventory-row"><dt>Ranking strategies</dt><dd>{[data.capabilities.ranking_v1 && 'V1', data.capabilities.ranking_v2 && 'V2'].filter(Boolean).join(' · ') || '—'}</dd></div><div className="inventory-row"><dt>CTR model</dt><dd title={data.capabilities.ctr_model_id ?? undefined}>{data.capabilities.ctr_model_id ? `${data.capabilities.ctr_model_id.slice(0, 12)}…` : 'Unavailable'}</dd></div></dl>
        {data.capabilities.retrieval_failure && <p className="performance-warning">Retrieval capability note: {data.capabilities.retrieval_failure}</p>}{readiness.error && <p className="performance-warning">Readiness check failed: {message(readiness.error)}</p>}
      </section>
      <section className="overview-panel cache-panel"><div className="panel-heading"><div><span className="eyebrow">PROFILE CACHE COUNTERS</span><h2>Process lifetime</h2></div><span className={`health-pill ${data.cache_health === 'ready' ? 'healthy' : 'degraded'}`}>{data.cache_health}</span></div>
        <dl className="inventory-list"><div className="inventory-row"><dt>Hits / misses</dt><dd>{count.format(data.cache.hits)} / {count.format(data.cache.misses)}</dd></div><div className="inventory-row"><dt>Hit share of cache accesses</dt><dd>{data.cache.hit_ratio === null ? '—' : `${(data.cache.hit_ratio * 100).toFixed(1)}%`}</dd></div><div className="inventory-row"><dt>Invalid payloads</dt><dd>{count.format(data.cache.invalid_payloads)}</dd></div><div className="inventory-row"><dt>Read / write / invalidation errors</dt><dd>{count.format(data.cache.read_errors)} / {count.format(data.cache.write_errors)} / {count.format(data.cache.invalidation_errors)}</dd></div><div className="inventory-row"><dt>Bypass reasons</dt><dd>{Object.entries(data.cache.bypasses).map(([key, value]) => `${key}: ${count.format(value)}`).join(' · ') || '—'}</dd></div></dl>
        <p className="chart-footnote">Cache counters reset with the process and cover cache accesses only. Hit share is not overall request success or a distributed service metric.</p>
      </section>
    </div>
    <p className="performance-footnote">Scope: this process retains at most {count.format(data.max_records)} records / {bytes(data.max_bytes)} for {data.retention_seconds}s ({data.coverage_scope}). History resets on process restart and may be incomplete after drops or before process start. Storage currently uses {bytes(data.retained_bytes)}. Database readiness is checked at <code>/health/ready</code>.</p>
  </div>
}

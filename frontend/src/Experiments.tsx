import { useState } from 'react'
import {
  ApiError,
  type ExperimentComparisonMetric,
  type ExperimentResults,
  type ExperimentSummary,
  type ExperimentVariantMetrics,
} from './api'
import { usePolling } from './usePolling'

const counts = new Intl.NumberFormat()
const money = new Intl.NumberFormat(undefined, { style: 'currency', currency: 'USD', minimumFractionDigits: 4, maximumFractionDigits: 4 })

function asNumber(value: string | number | null): number | null {
  if (value === null) return null
  const parsed = typeof value === 'number' ? value : Number(value)
  return Number.isFinite(parsed) ? parsed : null
}

function formatMetric(name: string, value: string | number | null): string {
  const parsed = asNumber(value)
  if (parsed === null) return '—'
  if (name === 'simulated_revenue' || name === 'revenue_per_exposed_user') return money.format(parsed)
  if (name === 'ctr') return `${(parsed * 100).toFixed(2)}%`
  if (name === 'relative_lift_percent') return `${parsed.toFixed(1)}%`
  return counts.format(parsed)
}

function formatDate(value: string | null) {
  return value ? new Date(value).toLocaleString() : '—'
}

function requestError(error: Error | null) {
  return error instanceof ApiError ? error.message : 'The API could not be reached.'
}

function StatePill({ status }: { status: ExperimentSummary['status'] }) {
  return <span className={`experiment-state state-${status}`}><i aria-hidden="true" />{status}</span>
}

function ExperimentList({
  experiments,
  selectedId,
  onSelect,
}: {
  experiments: ExperimentSummary[]
  selectedId: string | null
  onSelect: (id: string) => void
}) {
  if (experiments.length === 0) {
    return <section className="experiment-empty"><span className="empty-dataset-icon" aria-hidden="true">⇄</span><div className="eyebrow">NO EXPERIMENTS</div><h2>Experiment summaries will appear here</h2><p>Experiments are created and operated through the documented API or CLI. This dashboard is read-only.</p></section>
  }
  return <section className="experiment-list" aria-label="Experiments">
    {experiments.map((experiment) => (
      <button
        key={experiment.id}
        type="button"
        className={selectedId === experiment.id ? 'experiment-list-item selected' : 'experiment-list-item'}
        onClick={() => onSelect(experiment.id)}
        aria-pressed={selectedId === experiment.id}
        aria-label={`View results for ${experiment.name}, ${experiment.status}`}
      >
        <span className="experiment-list-main"><strong>{experiment.name}</strong><small>{experiment.control_strategy} <span>vs</span> {experiment.treatment_strategy}</small></span>
        <span className="experiment-list-meta"><StatePill status={experiment.status} /><small>{(experiment.control_basis_points / 100).toFixed(0)}% control</small></span>
      </button>
    ))}
  </section>
}

function VariantSummary({ name, metrics }: { name: 'control' | 'treatment'; metrics: ExperimentVariantMetrics }) {
  return <article className={`variant-card variant-${name}`}>
    <div className="variant-title"><div><span className="eyebrow">{name === 'control' ? 'REFERENCE' : 'ALTERNATIVE'}</span><h3>{name === 'control' ? 'Control' : 'Treatment'}</h3></div><span className={`variant-tag ${name}`}>{name.toUpperCase()}</span></div>
    <div className="variant-primary"><div><span>Observed CTR</span><strong>{metrics.ctr === null ? '—' : formatMetric('ctr', metrics.ctr)}</strong></div><div><span>Simulated revenue</span><strong>{formatMetric('simulated_revenue', metrics.simulated_revenue)}</strong></div></div>
    <div className="variant-counts">
      <span><strong>{counts.format(metrics.attempts)}</strong> outcomes</span>
      <span><strong>{counts.format(metrics.recommendations)}</strong> recommendations</span>
      <span><strong>{counts.format(metrics.exposed_users)}</strong> exposed users</span>
      <span><strong>{counts.format(metrics.impressions)}</strong> impressions</span>
      <span><strong>{counts.format(metrics.clicks)}</strong> clicks</span>
      <span><strong>{formatMetric('revenue_per_exposed_user', metrics.revenue_per_exposed_user)}</strong> / exposed user</span>
    </div>
    <div className="variant-fallbacks"><span>Exact retrieval fallbacks</span><strong>{counts.format(metrics.fallbacks.reduce((sum, item) => sum + item.count, 0))}</strong></div>
  </article>
}

const metricRows: { key: string; label: string; unit: string }[] = [
  { key: 'attempts', label: 'Durable request outcomes', unit: 'count' },
  { key: 'attempted_users', label: 'Attempted users', unit: 'users' },
  { key: 'no_ad_outcomes', label: 'No-ad outcomes', unit: 'count' },
  { key: 'recommendations', label: 'Recommendations', unit: 'count' },
  { key: 'exposed_users', label: 'Exposed users', unit: 'users' },
  { key: 'impressions', label: 'Accepted impressions', unit: 'count' },
  { key: 'clicks', label: 'Accepted clicks', unit: 'count' },
  { key: 'ctr', label: 'Observed CTR', unit: 'clicks / impressions' },
  { key: 'simulated_revenue', label: 'Simulated revenue', unit: 'simulated USD' },
  { key: 'revenue_per_exposed_user', label: 'Revenue per exposed user', unit: 'simulated USD / user' },
]

function ComparisonTable({ results }: { results: ExperimentResults }) {
  return <section className="overview-panel comparison-panel" aria-labelledby="comparison-title">
    <div className="panel-heading"><div><span className="eyebrow">FULL RECOMMENDATION COHORT</span><h2 id="comparison-title">Variant comparison</h2></div><span className="panel-unit">DESCRIPTIVE · SYNTHETIC</span></div>
    <div className="comparison-scroll" role="region" aria-label="Experiment cohort comparison table" tabIndex={0}>
      <table className="comparison-table">
        <thead><tr><th scope="col">Metric</th><th scope="col">Control</th><th scope="col">Treatment</th><th scope="col">Difference</th><th scope="col">Relative lift</th></tr></thead>
        <tbody>{metricRows.map((row) => {
          const metric = results.comparison[row.key] as ExperimentComparisonMetric | undefined
          const lift = metric?.relative_lift_percent ?? null
          return <tr key={row.key}>
            <th scope="row"><span>{row.label}</span><small>{row.unit}</small></th>
            <td>{metric ? formatMetric(row.key, metric.control) : '—'}</td>
            <td>{metric ? formatMetric(row.key, metric.treatment) : '—'}</td>
            <td>{metric ? formatMetric(row.key, metric.absolute_difference) : '—'}</td>
            <td title={lift === null ? 'Undefined when control is zero or unavailable.' : undefined}>{formatMetric('relative_lift_percent', lift)}</td>
          </tr>
        })}</tbody>
      </table>
    </div>
    <p className="chart-footnote">Lift is undefined when the control denominator is zero. No significance test or winner is reported.</p>
  </section>
}

function Diagnostics({ results }: { results: ExperimentResults }) {
  const eventDiagnostics = results.latency_populations.filter((item) => ['error', 'no_ad', 'replay'].includes(item.population))
  const hasFallbacks = results.variants.control.fallbacks.length + results.variants.treatment.fallbacks.length > 0
  const unassignedErrors = results.telemetry.unknown_attribution_errors.reduce((sum, item) => sum + item.count, 0)
  return <section className="overview-panel diagnostics-panel" aria-labelledby="diagnostics-title">
    <div className="panel-heading"><div><span className="eyebrow">OBSERVED REQUEST DIAGNOSTICS</span><h2 id="diagnostics-title">Failures, replays &amp; fallback</h2></div><span className="panel-unit">PROCESS TELEMETRY</span></div>
    <div className="diagnostic-coverage"><span className={results.telemetry.coverage_complete ? 'coverage-mark complete' : 'coverage-mark'} aria-hidden="true" />
      <span>{results.telemetry.coverage_complete ? 'Telemetry coverage complete' : 'Telemetry coverage incomplete'}</span>
      <small>{results.telemetry.covered_from ? `Observed from ${formatDate(results.telemetry.covered_from)}` : 'No complete observation window'}</small>
    </div>
    {eventDiagnostics.length > 0 ? <div className="diagnostic-grid">
      {eventDiagnostics.map((item, index) => <article className="diagnostic-item" key={`${item.population}-${item.variant}-${index}`}>
        <div><strong>{item.population === 'error' ? 'Failed requests' : item.population === 'no_ad' ? 'No-ad outcomes' : 'Replays'}</strong><span>{item.variant ?? 'Unassigned'}</span></div>
        <b>{counts.format(item.count)}</b>
        {Object.keys(item.error_codes).length > 0 && <small>{Object.entries(item.error_codes).map(([code, count]) => `${code}: ${count}`).join(' · ')}</small>}
        {Object.keys(item.fallback_reasons).length > 0 && <small>{Object.entries(item.fallback_reasons).map(([reason, count]) => `${reason}: ${count}`).join(' · ')}</small>}
      </article>)}
    </div> : <p className="diagnostics-empty">No attributed failure, no-ad, or replay samples were observed in this telemetry window. This is not evidence of zero attempts outside its coverage.</p>}
    {hasFallbacks && <div className="fallback-summary"><strong>Exact retrieval fallback</strong>{(['control', 'treatment'] as const).map((variant) => <span key={variant}>{variant}: {results.variants[variant].fallbacks.map((item) => `${item.reason} ${counts.format(item.count)}`).join(', ') || '0'}</span>)}</div>}
    {unassignedErrors > 0 && <p className="unassigned-error">{counts.format(unassignedErrors)} process telemetry error samples have unknown attribution and are not assigned to either variant.</p>}
  </section>
}

function ExperimentDetail({ experiment, paused }: { experiment: ExperimentSummary; paused: boolean }) {
  const request = usePolling<ExperimentResults>(`/api/v1/experiments/${experiment.id}/results`, paused)
  if (!request.data) {
    if (request.error) return <div className="notice notice-error" role="alert"><strong>Results unavailable</strong><span>{requestError(request.error)}</span><button className="button button-quiet" onClick={() => void request.refresh()}>Try again</button></div>
    return <div className="loading-panel" role="status"><span className="loading-mark" /><div><strong>Loading cohort results</strong><span>Reading durable experiment records…</span></div></div>
  }
  const results = request.data
  return <div className="experiment-detail">
    {request.stale && <div className="notice notice-warning" role="status">Showing the last successful cohort summary. Latest refresh failed: {requestError(request.error)}</div>}
    <section className="cohort-context">
      <div><span className="eyebrow">RECOMMENDATION COHORT</span><strong>{formatDate(results.cohort_start)} <span>to</span> {formatDate(results.cohort_end_exclusive)}</strong><small>As of {formatDate(results.as_of)} · events arrive within {results.event_window_hours} hours of each recommendation</small></div>
      <span className={results.provisional ? 'maturity-pill provisional' : 'maturity-pill'}><i aria-hidden="true" />{results.provisional ? 'PROVISIONAL' : 'EVENT WINDOW CLOSED'}</span>
    </section>
    <div className="variant-grid"><VariantSummary name="control" metrics={results.variants.control} /><VariantSummary name="treatment" metrics={results.variants.treatment} /></div>
    <div className="experiment-config"><span><small>CONTROL</small><strong>{experiment.control_strategy}</strong></span><span><small>TREATMENT</small><strong>{experiment.treatment_strategy}</strong></span><span><small>RETRIEVAL</small><strong>{experiment.retrieval_mode}</strong></span><span><small>PINNED MODEL</small><strong title={experiment.model_id}>{experiment.model_id.slice(0, 12)}…</strong></span></div>
    <ComparisonTable results={results} />
    <Diagnostics results={results} />
    <p className="experiment-disclaimer">Synthetic descriptive results. A higher observed value is not a statistical winner or rollout recommendation.</p>
  </div>
}

export function ExperimentsPage({ paused }: { paused: boolean }) {
  const request = usePolling<ExperimentSummary[]>('/api/v1/experiments', paused)
  const [selectedId, setSelectedId] = useState<string | null>(null)

  if (!request.data) {
    if (request.error) return <div className="notice notice-error" role="alert"><strong>Experiments unavailable</strong><span>{requestError(request.error)}</span><button className="button button-quiet" onClick={() => void request.refresh()}>Try again</button></div>
    return <div className="loading-panel" role="status"><span className="loading-mark" /><div><strong>Loading experiments</strong><span>Reading saved experiment configurations…</span></div></div>
  }
  const activeId = request.data.some((item) => item.id === selectedId) ? selectedId : request.data[0]?.id ?? null
  return <div className="experiments-page">
    {request.stale && <div className="notice notice-warning" role="status">Showing the last successful experiment list. Latest refresh failed: {requestError(request.error)}</div>}
    <div className="experiments-layout">
      <div className="experiment-navigation"><div className="list-heading"><div><span className="eyebrow">SAVED CONFIGURATIONS</span><h2>Experiments</h2></div><span className="list-count">{counts.format(request.data.length)}</span></div><ExperimentList experiments={request.data} selectedId={activeId} onSelect={setSelectedId} /></div>
      <div className="experiment-results-pane" aria-live="polite">
        {activeId ? <ExperimentDetail key={activeId} experiment={request.data.find((item) => item.id === activeId)!} paused={paused} /> : request.data.length === 0 ? <ExperimentList experiments={[]} selectedId={null} onSelect={setSelectedId} /> : null}
      </div>
    </div>
  </div>
}

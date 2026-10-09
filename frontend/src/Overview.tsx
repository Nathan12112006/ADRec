import type { AnalyticsOverview } from './api'
import { ApiError } from './api'
import { usePolling } from './usePolling'

type OverviewProps = { data: AnalyticsOverview }

const countFormat = new Intl.NumberFormat(undefined, { maximumFractionDigits: 0 })
const currencyFormat = new Intl.NumberFormat(undefined, {
  style: 'currency',
  currency: 'USD',
  minimumFractionDigits: 4,
  maximumFractionDigits: 4,
})

function formatCurrency(value: string) {
  const amount = Number(value)
  return Number.isFinite(amount) ? currencyFormat.format(amount) : '—'
}

function MetricCard({
  label,
  value,
  caption,
  icon,
  tone,
}: {
  label: string
  value: string
  caption: string
  icon: string
  tone: string
}) {
  return (
    <article className="overview-metric">
      <div className="metric-card-top"><span>{label}</span><span className={`metric-icon ${tone}`} aria-hidden="true">{icon}</span></div>
      <strong className="metric-value">{value}</strong>
      <span className="metric-caption">{caption}</span>
    </article>
  )
}

function EventBars({ impressions, clicks }: { impressions: number; clicks: number }) {
  const max = Math.max(impressions, clicks)
  const rows = [
    { label: 'Accepted impressions', value: impressions, tone: 'impression' },
    { label: 'Accepted clicks', value: clicks, tone: 'click' },
  ]
  return (
    <section className="overview-panel event-panel" aria-labelledby="event-title">
      <div className="panel-heading">
        <div><span className="eyebrow">LIFECYCLE EVENTS</span><h2 id="event-title">Confirmed activity</h2></div>
        <span className="panel-unit">COUNT</span>
      </div>
      <div className="event-bars" role="img" aria-label={`Accepted impressions: ${countFormat.format(impressions)}. Accepted clicks: ${countFormat.format(clicks)}.`}>
        {rows.map((row) => (
          <div className="event-row" key={row.label}>
            <div className="event-label"><span>{row.label}</span><strong>{countFormat.format(row.value)}</strong></div>
            <div className="bar-track"><div className={`bar-fill ${row.tone}`} style={{ width: max === 0 ? '0%' : `${(row.value / max) * 100}%` }} /></div>
          </div>
        ))}
      </div>
      <p className="chart-footnote">Deduplicated client-confirmed events; historical training activity is excluded.</p>
    </section>
  )
}

function InventoryPanel({ data }: OverviewProps) {
  const rows = [
    { label: 'Synthetic users', value: data.users },
    { label: 'Active advertisers', value: data.active_advertisers, context: `${countFormat.format(data.advertisers)} total` },
    { label: 'Active ads', value: data.active_ads, context: `${countFormat.format(data.ads)} total` },
    { label: 'Recommendations', value: data.recommendations },
    { label: 'Durable request outcomes', value: data.request_outcomes, context: `${countFormat.format(data.no_ad_outcomes)} no-ad` },
    { label: 'Exposed users', value: data.exposed_users },
  ]
  return (
    <section className="overview-panel inventory-panel" aria-labelledby="inventory-title">
      <div className="panel-heading">
        <div><span className="eyebrow">CURRENT DATASET</span><h2 id="inventory-title">Inventory &amp; reach</h2></div>
        <span className="panel-unit">LIVE RECORDS</span>
      </div>
      <dl className="inventory-list">
        {rows.map((row) => (
          <div className="inventory-row" key={row.label}>
            <dt>{row.label}</dt><dd>{countFormat.format(row.value)}{row.context && <small>{row.context}</small>}</dd>
          </div>
        ))}
      </dl>
    </section>
  )
}

export function Overview({ data }: OverviewProps) {
  if (data.availability === 'empty') {
    return (
      <section className="empty-dataset" aria-labelledby="empty-dataset-title">
        <span className="empty-dataset-icon" aria-hidden="true">◈</span>
        <div className="eyebrow">NO DATASET PREPARED</div>
        <h2 id="empty-dataset-title">Your workspace is ready</h2>
        <p>Prepare a synthetic dataset to see inventory and live recommendation activity. No data is different from an API failure.</p>
        <div className="empty-details"><span>Users <strong>0</strong></span><span>Impressions <strong>0</strong></span><span>Clicks <strong>0</strong></span></div>
      </section>
    )
  }

  const ctr = data.observed_ctr === null
    ? '—'
    : `${(Number(data.observed_ctr) * 100).toFixed(1)}%`
  const eventWindow = data.provisional
    ? `Open for ${data.event_window_hours}h after each recommendation`
    : `Closed through ${new Date(data.event_windows_closed_through).toLocaleDateString()}`
  const datasetId = data.dataset_id ?? 'Unknown dataset'

  return (
    <div className="overview-view">
      <div className="dataset-context">
        <div className="dataset-identity"><span className="dataset-glyph" aria-hidden="true">◈</span><div><span className="eyebrow">DATASET WINDOW</span><strong title={datasetId}>{datasetId}</strong></div></div>
        <div className="dataset-meta"><span className="window-label">LIFETIME · AS OF {new Date(data.as_of).toLocaleString()}</span><span className={data.provisional ? 'maturity-pill provisional' : 'maturity-pill'}><i aria-hidden="true" />{data.provisional ? 'PROVISIONAL' : 'EVENT WINDOW CLOSED'}</span></div>
      </div>

      <section className="overview-metrics" aria-label="Live outcome metrics">
        <MetricCard label="Impressions" value={countFormat.format(data.impressions)} caption="Accepted display confirmations" icon="▤" tone="mint" />
        <MetricCard label="Clicks" value={countFormat.format(data.clicks)} caption="Deduplicated accepted clicks" icon="↗" tone="blue" />
        <MetricCard label="Observed CTR" value={ctr} caption={data.observed_ctr === null ? 'Unavailable · no impressions yet' : 'Clicks divided by impressions'} icon="％" tone="amber" />
        <MetricCard label="Simulated revenue" value={formatCurrency(data.simulated_revenue)} caption="Captured bid credit · simulated USD" icon="$" tone="violet" />
      </section>

      <div className="overview-details">
        <EventBars impressions={data.impressions} clicks={data.clicks} />
        <InventoryPanel data={data} />
      </div>
      <div className="overview-footnote"><span className="status-dot" /> Snapshot coverage: durable PostgreSQL records <span>·</span> {eventWindow}</div>
    </div>
  )
}

export function OverviewPage({ paused }: { paused: boolean }) {
  const request = usePolling<AnalyticsOverview>('/api/v1/analytics/overview', paused)
  const error = request.error instanceof ApiError
    ? request.error.message
    : 'The API could not be reached. Check that the backend is running.'
  if (!request.data) {
    if (request.error) {
      return <div className="notice notice-error" role="alert"><strong>Overview unavailable</strong><span>{error}</span><button className="button button-quiet" onClick={() => void request.refresh()}>Try again</button></div>
    }
    return <div className="loading-panel" role="status" aria-live="polite"><span className="loading-mark" /><div><strong>Loading overview</strong><span>Reading the current dataset summary…</span></div></div>
  }
  return <>
    {request.stale && <div className="notice notice-warning" role="status">Showing the last successful summary. Latest refresh failed: {error}</div>}
    <Overview data={request.data} />
  </>
}

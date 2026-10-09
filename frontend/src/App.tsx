import { useEffect, useState } from 'react'
import { ExperimentsPage } from './Experiments'
import { OverviewPage } from './Overview'
import { PerformancePage } from './Performance'
import { POLLING_REFRESH_EVENT } from './usePolling'
import './App.css'

type View = 'overview' | 'experiments' | 'performance'

const views: { id: View; label: string; index: string }[] = [
  { id: 'overview', label: 'Overview', index: '01' },
  { id: 'experiments', label: 'Experiments', index: '02' },
  { id: 'performance', label: 'Performance', index: '03' },
]

function currentView(): View {
  const value = window.location.hash.replace('#', '')
  return views.some((view) => view.id === value) ? (value as View) : 'overview'
}

function App() {
  const [view, setView] = useState<View>(currentView)
  const [paused, setPaused] = useState(false)

  useEffect(() => {
    const changeView = () => setView(currentView())
    window.addEventListener('hashchange', changeView)
    return () => window.removeEventListener('hashchange', changeView)
  }, [])

  const active = views.find((item) => item.id === view)!
  const pageCopy = {
    overview: ['System overview', 'A clear view of live synthetic inventory and outcomes.'],
    experiments: ['Experiment workspace', 'Compare assigned variants against durable exposure and event data.'],
    performance: ['Performance signals', 'Inspect service health, cache behavior and request telemetry.'],
  } satisfies Record<View, [string, string]>

  return (
    <div className="app-shell">
      <aside className="sidebar" aria-label="Main navigation">
        <a className="brand" href="#overview" aria-label="AdFlow dashboard home">
          <span className="brand-mark" aria-hidden="true">A</span>
          <span><strong>AdFlow</strong><small>DECISION SYSTEMS</small></span>
        </a>
        <div className="nav-caption">WORKSPACE</div>
        <nav className="primary-nav">
          {views.map((item) => (
            <a
              key={item.id}
              href={`#${item.id}`}
              className={view === item.id ? 'nav-link active' : 'nav-link'}
              aria-current={view === item.id ? 'page' : undefined}
            >
              <span className="nav-index">{item.index}</span>
              <span>{item.label}</span>
              {item.id === view && <span className="nav-dot" aria-hidden="true" />}
            </a>
          ))}
        </nav>
        <div className="sidebar-note">
          <span className="eyebrow">DATA MODE</span>
          <strong>Synthetic environment</strong>
          <p>All outcomes and revenue are simulated.</p>
        </div>
        <div className="sidebar-footer"><span className="status-dot" /> Read-only dashboard</div>
      </aside>

      <main className="main-shell">
        <header className="topbar">
          <div className="breadcrumb"><span>Workspace</span><span className="slash">/</span><strong>{active.label}</strong></div>
          <div className="topbar-tools">
            <span className="live-indicator"><span className="status-dot" /> API SUMMARIES</span>
            <span className="updated-at">5 SECOND POLL</span>
            <button className="button button-quiet" onClick={() => window.dispatchEvent(new Event(POLLING_REFRESH_EVENT))}>
              <span aria-hidden="true" className="refresh-icon">↻</span>
              Refresh
            </button>
            <button className="button button-pause" onClick={() => setPaused((value) => !value)} aria-pressed={paused}>
              <span aria-hidden="true">{paused ? '▶' : 'Ⅱ'}</span>
              {paused ? 'Resume' : 'Pause updates'}
            </button>
          </div>
        </header>

        <div className="page-content">
          <section className="page-heading">
            <div>
              <div className="eyebrow">ADFLOW / {active.index}</div>
              <h1>{pageCopy[view][0]}</h1>
              <p>{pageCopy[view][1]}</p>
            </div>
            <div className="as-of"><span>REFRESH POLICY</span><strong>Every 5 seconds</strong><small>{paused ? 'Polling paused' : 'Visible page only'}</small></div>
          </section>

          {view === 'overview' && <OverviewPage paused={paused} />}
          {view === 'experiments' && <ExperimentsPage paused={paused} />}
          {view === 'performance' && <PerformancePage paused={paused} />}
        </div>
      </main>
    </div>
  )
}

export default App

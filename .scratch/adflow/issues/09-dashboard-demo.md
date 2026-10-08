# What is the smallest dashboard that demonstrates the complete system?

Status: resolved
Type: grilling
Labels: wayfinder:grilling
Parent: [AdFlow — Full-project decision map](../map.md)
Assignee: Nathan (with Codex)
Blocked by: 07, 08

## Question

Choose the minimum overview, experiment comparison, and performance views, required backend aggregates, refresh behavior, loading/error/empty states, and simulator controls or commands. Make synthetic traffic, simulated revenue, insufficient evidence, and measurement windows clear. Decide whether advertiser reporting or conversion views add enough value to include; otherwise retain them as optional.

## Comments

The round notes below are chronological history. The final contract is under Answer.

### Confirmed dashboard scope

- Nathan accepted three views: Overview (inventory/events/CTR/simulated revenue), Experiments (list/details with errors/fallbacks/provisional status), and Performance (latency/throughput/cache/dependency status).
- Backend APIs calculate aggregates; the frontend consumes typed summaries rather than reconstructing metrics from downloaded events. Live telemetry and reproducible benchmark results remain distinct.
- Nathan accepted a read-only dashboard with CLI/API simulator and experiment-management operations; defer browser controls for those actions.
- Nathan accepted deferring advertiser reporting and conversion tracking/views from the core release.
- Refresh behavior, measurement windows, unavailable/stale states, and completion checks remain open.

Claimed at Nathan's request on 2026-10-07. Beginning a live discussion of minimal dashboard views, API aggregates, simulator operation, and honest loading/error/measurement states. Existing experiment and cache reporting contracts remain binding.

Created during map charting. Resolve through a live discussion using grilling and domain-modeling. Consult the preferred-stack brief; investigate factual uncertainties against primary sources when needed.

### Final confirmation

Nathan accepted five-second polling with pause/manual refresh and hidden-page suspension, explicit per-view windows/as-of timestamps, visible stale/unavailable states, and all completion checks. All ticket questions are settled.

## Answer

Resolved with Nathan on 2026-10-07. This defines a minimal dashboard; no frontend implementation, mockup, or browser validation is claimed.

### Required views and scope

Build a read-only React/TypeScript/Vite dashboard with three primary views and experiment detail navigation:

| View | Required content |
| --- | --- |
| Overview | Current dataset users/ads/active advertisers, accepted live impressions/clicks, observed CTR, simulated revenue |
| Experiments | Experiment list, state, control/treatment strategies, and detail comparison with counts, exposed users, CTR/revenue, defined lift, errors/fallbacks, and provisional status |
| Performance | Recommendation latency, throughput, cache hit/miss/error/bypass metrics, and dependency/model/index capability status |

Use a professional minimal engineering-dashboard style: clear navigation, readable cards/tables, a few charts where they aid comparison, responsive layout, and limited animation. Do not add raw-event browsing or administrative workflows merely to fill the interface.

Defer advertiser reporting and conversion tracking/views from the core release. The experiment ticket already defers significance tests and automatic winners; never add a winner badge that implies statistical evidence. Simulator and experiment create/start/stop operations remain documented CLI/API actions, not browser controls. Dashboard interaction is navigation, refresh, and inspection.

### API summaries and ownership

Compute aggregates on the backend; the browser must not download all events to recreate metrics. Provide GET /api/v1/analytics/overview for current-dataset inventory/live totals and GET /api/v1/metrics for live performance/cache/capability summaries, alongside the agreed experiment list/results APIs.

Use typed response contracts with dataset identity, measurement/cohort boundaries, as-of timestamp, sample counts, and availability/provisional/degraded indicators where applicable. Server-side experiment definitions remain canonical; do not reimplement denominators or assignment in React. Return ratio/lift values and their defining counts so the UI can explain them. Formatting percentages/currency is presentation, not a new metric formula.

Historical training artifacts never contribute to overview or experiment live event counts. Recommendations, impressions, clicks, attempts, and exposed users remain distinct. Simulated revenue is displayed as simulated dollars; predicted CTR, observed CTR, overlap score, cosine similarity, and expected-value score are not interchangeable.

Preserve experiment fallback/error breakdowns and the separation of successful new-selection latency from replay/failure/no-ad paths. Version/context details can be shown in experiment details without overwhelming the overview. Benchmark reports remain separate saved artifacts, not fabricated live chart series.

### Windows and refresh

- Overview: live totals associated with the current dataset, with clear scope rather than unlabeled lifetime totals across unrelated dataset replacements.
- Experiment detail: the experiment's full recommendation cohort, retaining later accepted events and its maturity rules from the experiment ticket.
- Performance: rolling 15-minute telemetry window. Show actual coverage/collection start when less than 15 minutes is available, and disclose missing/reset/process coverage.
- All views show as-of times. Do not imply that independently refreshed summaries form one atomic global snapshot.

Poll visible views every five seconds by default. Provide pause and manual refresh, prevent overlapping requests, and suspend automatic polling while the page is hidden. Resume without building a backlog of missed polls. Clean up requests/timers on navigation. Refresh failures must not trigger unbounded tight retries.

### Empty, loading, stale, and unavailable states

Show a loading state before the first successful response. A successful empty dataset/experiment result is distinct from a failed request. If refresh fails after a successful load, retain the last values with a visible stale/error label and last-success time; do not present them as fresh.

Render undefined ratios and unavailable measurements as a dash with a concise reason. A real count of zero is zero, not unavailable. Do not convert null telemetry to zero latency, perfect availability, or zero errors. Keep separate sections' error/availability states when only one API fails.

Label synthetic outcomes, simulated revenue, provisional cohorts, degraded Redis/index operation, and unavailable CTR capability clearly. Generic readiness is not proof that V2 or ANN is available. Charts/tables must carry their window, units, and sample/context labels. Raw V1 and V2 scores must not be compared as if they shared units.

### Completion and handoff

- Connect the three views and experiment details to real backend responses; pass TypeScript and production build checks.
- Run the documented simulator/experiment walkthrough and reconcile displayed values with API summaries and accepted events. Verify offline training history remains excluded.
- Verify denominators, score units, sample counts, percentage/lift formatting, zero-denominator states, cohort windows, as-of times, and provisional/fallback labels.
- Check initial loading, no traffic/no experiments, successful empty results, partial API failure, stale retained data, unavailable telemetry, and degraded dependency/model/index states.
- Check polling interval, pause/manual refresh, hidden-page suspension, no overlapping refreshes, and navigation cleanup.
- Verify responsive layouts, readable tables/charts, keyboard navigation, visible focus, labeled controls, and statuses conveyed by text rather than color alone.
- Document the demo commands and capture screenshots only from actual implemented states. No UI or benchmark success is established by this planning decision.

The benchmark ticket owns telemetry collection/aggregation and final measurement methodology; the delivery ticket owns final screenshots and setup/documentation gates. No additional decision ticket is required.

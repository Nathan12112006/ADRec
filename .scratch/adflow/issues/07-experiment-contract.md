# What experiment contract makes comparisons interpretable?

Status: resolved
Type: grilling
Labels: wayfinder:grilling
Parent: [AdFlow — Full-project decision map](../map.md)
Assignee: Nathan (with Codex)
Blocked by: 01, 06

## Question

Define stable assignment and hashing inputs, assignment unit, traffic split, exposure recording, algorithm/model/config versions, and rules for starting, stopping, or changing an experiment. Define denominators for users, impressions, clicks, CTR, simulated revenue, and latency. Decide fallback attribution, cohort exclusions, and minimum reporting needed to avoid misleading comparisons. Statistical significance is optional and synthetic results must remain labeled.

## Comments

The round notes below are chronological history. The final contract is under Answer.

### Confirmed metrics and reporting choices

- Nathan accepted exposed users as distinct users with a confirmed impression; impressions/clicks are accepted deduplicated events; CTR is clicks/impressions; simulated revenue is accepted-click captured bids; revenue per exposed user is revenue/exposed users. Include recommendation counts and attempted-user diagnostics; zero-denominator ratios are null.
- Report failures and retrieval fallback by assigned variant. Include fallback traffic in main results and provide a separate breakdown. Model failures stay 503, not substituted V1; failed attempts are not impressions. Mark telemetry incomplete when an outage prevents reliable diagnostics.
- Reporting cohorts use recommendation creation time, retaining later accepted events with their original recommendation cohort. Include as-of time and provisional status until event windows close.
- Report average/P50/P95/P99 latency and sample counts for successful new selections separately from replay and failure latency.
- Nathan accepted descriptive counts, absolute differences, and defined relative lift, with synthetic/provisional labels. Defer significance tests and automatic winner declarations.
- Management operations, activation validation, and completion checks remain open.

### Confirmed assignment and lifecycle choices

- Nathan accepted deterministic synthetic-user assignment using user ID and stable experiment ID/salt, with a default 50/50 control/treatment split. Repeated requests keep the same group; a new experiment may assign differently.
- Traffic split, ranking versions, CTR-model version, and retrieval configuration become immutable on start. Changing these requires a new experiment rather than mixing treatments in one result.
- Nathan accepted at most one active ranking experiment; outside it, serve the configured default strategy. Overlapping experiments and audience targeting are deferred.
- Stopping prevents new opportunities from entering the experiment but does not change attribution of existing recommendations or close their 24-hour event windows. Results remain provisional until those windows close.
- Metric denominators, failures/fallback reporting, reporting cohorts, latency, and statistical scope remain open.

Claimed at Nathan's request on 2026-10-07. Lifecycle and ranking decisions are resolved. Beginning a live discussion of deterministic assignment, experiment configuration, attribution, and metric definitions.

Created during map charting. Resolve through a live discussion using grilling and domain-modeling. Consult the preferred-stack brief; investigate factual uncertainties against primary sources when needed.

### Final confirmation

Nathan accepted API management with draft -> running -> stopped and no resume, activation validation including the pinned model, rejection of a second active experiment, and all completion checks. All ticket questions are settled.

## Answer

Resolved with Nathan on 2026-10-07. This defines an experimentation contract, not implemented experiments or statistically established results.

### Assignment and frozen configuration

- Assign synthetic users, not individual requests. Use a documented stable digest/bucket mapping over canonical user ID, immutable experiment ID, and stored experiment salt. Default allocation is 50/50; repeat requests retain assignment across processes/restarts. Avoid a process-dependent hash or mutable experiment name as identity.
- Store assignment algorithm/version and salt with the experiment. A new experiment may assign the same user differently. A deterministic split is not a guarantee of exactly equal observed user or impression counts.
- At start, freeze allocation, control/treatment ranking versions, CTR-model/feature version, and shared retrieval configuration/candidate limit. A change requires a new experiment, not an edit to a running treatment.
- Record actual retrieval mode/version and fallback diagnostics with selections. Fixed retrieval configuration does not conceal current-catalog fallback or runtime failures. Do not hot-swap a different model into the treatment while retaining the same experiment identity.
- Allow at most one running ranking experiment, with database-backed concurrency enforcement. Outside it, use the configured default strategy. Overlapping experiments and audience targeting are deferred.

### Management and activation

Provide POST /api/v1/experiments for draft creation, POST /api/v1/experiments/{id}/start, POST /api/v1/experiments/{id}/stop, GET /api/v1/experiments for listing, and GET /api/v1/experiments/{id}/results. No admin UI is required initially.

Lifecycle is draft -> running -> stopped. A stopped experiment cannot resume; create a new experiment for another run. Validate transitions atomically, reject invalid transitions/second concurrent starts as conflicts, and retain experiment records for historical attribution. Unknown IDs return 404; malformed configuration uses the API's validation response. Running configuration is immutable.

Starting requires valid allocation and supported ranking/retrieval settings plus availability and compatibility of the pinned CTR model. Exact retrieval fallback remains allowed by the retrieval contract; a valid configuration must not be confused with a promise that every approximate-index artifact is currently usable. Later loss of the CTR model returns visible treatment 503 errors rather than changing treatment to V1.

### Attribution and stopping

Persist experiment ID, assigned variant, executed strategy/version, and model/feature/retrieval context with the durable recommendation. Client impressions/clicks reference recommendation_id; derive attribution from that record, never a client-supplied variant or the currently active experiment.

Stopping prevents new opportunities from entering the experiment. Existing recommendations keep their original attribution and can accept events within their creation-based 24-hour window. Request-key replay retains the already saved selection even after stopping or starting another experiment.

Selection and experiment lifecycle operations must define a consistent transaction boundary so racing start/stop requests cannot save ambiguous treatment attribution. A retry with a saved outcome replays that outcome; an uncommitted failed attempt supplies no successful recommendation to replay. Keep failed-attempt diagnostics distinct from accepted selections.

### Metric definitions

Report per variant:

| Metric | Definition |
| --- | --- |
| Recommendations | Distinct durable selections attributed to the variant; replays do not add selections |
| Exposed users | Distinct users with at least one accepted impression in the cohort |
| Impressions | Accepted, deduplicated client display confirmations for cohort recommendations |
| Clicks | Accepted, deduplicated clicks for those impressions |
| CTR | Clicks / impressions |
| Simulated revenue | Sum of captured bid credits from first accepted clicks |
| Revenue per exposed user | Simulated revenue / exposed users |

Return a null ratio with its counts when its denominator is zero. Report attempted-user, no-ad, request-attempt, replay, failure, and fallback diagnostics separately; attempted traffic and exposed users are different populations. No-ad outcomes and errors do not become impressions or nonclick examples.

Show raw counts, absolute differences, and relative lift where defined. Relative lift is (treatment - control) / control, expressed as a percentage; return null when the control value is zero or unavailable. Do not compare averages of V1 and V2's incompatible raw ranking scores.

### Cohorts, maturity, and failures

Reporting cohorts use recommendation creation time. Accepted later impressions/clicks remain attached to that cohort even if they arrive after the reporting interval or experiment stop. Use one as-of cutoff for consistent counts; deduplicate and join events to recommendations rather than grouping clicks independently by arrival date.

Return cohort boundaries, as-of time, and provisional status. Recent cohorts remain provisional until the applicable recommendation event windows close. A whole running experiment generally remains provisional as new recommendations enter it. After stopping and expiration of its last recommendation window, event outcome counts can settle; later duplicate retries still must not add counts. A short demo need not wait 24 hours but must display provisional results.

Keep retrieval-fallback traffic in the main results, with a separate breakdown. Do not retrospectively exclude poor treatment outcomes or silently remove errors to make lift look better. CTR-model failures stay 503 and are attributed diagnostically to the intended variant when known. Event outcome metrics describe the exposed population, not an intention-to-treat effectiveness estimate; show exposure and failure differences alongside them.

Report failures without fabricating durable events. During an outage, telemetry may be incomplete; expose that limitation rather than presenting missing samples as zero errors. If durable results cannot be read, return an unavailable/error response rather than invented empty experiment results.

### Latency and descriptive scope

For successful new selections, report average, P50, P95, P99, and sample count for server recommendation latency. Report replays and failed-request latency separately; distinguish no-ad outcomes too so their faster path does not improve successful-selection timing. Include measurement windows/availability and do not average variant percentiles to derive combined percentiles.

Defer significance tests, confidence-based winner declarations, and automatic rollout. Results are descriptive and synthetic. Unequal exposure, repeated users, recent outcomes, fallback use, failures, and missing telemetry remain visible; none establish real-world advertising effectiveness. Conversions remain optional and are not a required metric in this initial contract.

### Completion and handoff

- Test stable assignment across repeated requests/process restarts, configured allocation boundaries, and persistence of the assignment version/salt. Do not assert an exact 50/50 count for an arbitrary finite sample.
- Test draft/start/stop transitions, concurrent starts, immutable configuration, activation failures, and attribution/replay after stop or a subsequent experiment starts.
- Test event deduplication, all metric denominators, zero denominators/control lift, late-event cohorts, as-of/maturity flags, and event/count reconciliation.
- Test CTR failures without V1 substitution, fallback inclusion/breakdowns, separate latency populations, and telemetry-unavailable behavior.
- Demonstrate both variants through the API simulator and reconcile results with accepted live events; offline historical training data never enters results.
- Explain assignment versus exposure, immutable treatment, late attribution, and descriptive-result limitations. Initial aggregation can read PostgreSQL records; measure its cost before adding cached aggregates. Assignment hashing is constant work for bounded identifiers; result queries scale with selected records unless indexes/aggregates reduce the work. The cache and benchmark tickets own further optimization decisions.

No new decision ticket is needed. Caching/failure behavior, dashboard presentation, benchmark methodology, and final optional-feature cuts remain with existing tickets. No experiments or tests were executed during this planning resolution.

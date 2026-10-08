# How will synthetic data and simulated traffic provide honest evidence?

Status: resolved
Type: grilling
Labels: wayfinder:grilling
Parent: [AdFlow — Full-project decision map](../map.md)
Assignee: Nathan (with Codex)
Blocked by: 01

## Question

Define reproducible seeds, configurable small and full datasets, user/ad distributions, click generation, and simulator behavior. Separate historical training data from live experiment traffic. Decide how to avoid circular evaluation that merely rewards a generator's formula, what a synthetic ranking comparison can establish, and what it cannot. Specify consistency rules for impressions and clicks, temporal data splits, and the demo's startup/runtime expectations.

## Comments

The round notes below are chronological history. The final contract is under Answer.

### Confirmed dataset and evidence choices

- Nathan accepted development defaults of 100 users, 20 advertisers, and 1,000 ads, plus an optional full dataset of 10,000 users, 100 advertisers, and 100,000 ads.
- Historical training volume is expressed as 1 million impressions plus their clicks, with all counts configurable; it is not 1 million ambiguous mixed event rows.
- Nathan accepted probabilistic click outcomes based on interest overlap, category preference, device, and a small hidden user/ad preference component. Bid and experiment variant do not directly affect click probability.
- Historical impressions use randomized exposure to eligible ads instead of exposure solely to current ranking winners.
- Nathan accepted no guaranteed ranking improvement: the outcome generator is independent of ranking predictions, evaluation uses unseen outcomes, and simulator rules must not be tuned just to make Ranking V2 win.
- Synthetic outcomes establish behavior within the simulated world; actual software performance is measured separately through load tests.
- Reproducibility, temporal splits, historical/live separation, and live simulator behavior remain under discussion.

Claimed at Nathan's request on 2026-10-07. The event lifecycle and Phase 1 decisions are resolved. Beginning a live discussion of reproducible datasets, simulated outcomes, and traffic behavior.

Created during map charting. Resolve through a live discussion using grilling and domain-modeling. Consult the preferred-stack brief; investigate factual uncertainties against primary sources when needed.

### Final confirmation

Nathan accepted seed/version/configuration manifests, separate random streams, fresh live run IDs, chronological 70/15/15 splits, API-driven live simulation, and separate edge-case scenarios. For Q7, Nathan answered no to historical training data appearing in dashboard experiment results, agreeing with the recommended separation.

## Answer

Resolved with Nathan on 2026-10-07. This defines synthetic-data and traffic behavior; no datasets, training results, or simulator have been produced yet.

### Dataset sizes and scope

| Profile | Users | Advertisers | Ads | Historical impressions |
| --- | ---: | ---: | ---: | ---: |
| Development seed | 100 | 20 | 1,000 | 0 |
| Optional full dataset | 10,000 | 100 | 100,000 | 1,000,000 |

All counts are configurable. Historical clicks are additional outcomes associated with those impressions, not part of an ambiguous mixed-event target. The small seed remains the default; full historical generation is an explicit operation, not a prerequisite for starting the demo.

Create coherent fictional profiles using the brief's interest vocabulary, categories, age groups, countries, and devices. Ads have valid advertisers, category/interest relationships, bids, and active flags. Ensure ordinary data contains enough active inventory to exercise the normal path; edge fixtures separately cover no-interest users, zero bids, and inactive inventory. Distribution parameters belong in the generator configuration and manifest rather than undocumented constants. Describe these distributions as designed synthetic assumptions, not measured population statistics.

### Independent outcome generator

- Produce a probability of click from interest overlap, category preference, device, and a small hidden user/ad preference component; sample a binary outcome rather than making matches always click.
- Higher relevance should increase click tendency in aggregate while retaining uncertainty. Bid and experiment variant do not directly determine click probability.
- Generator logic must not call ranking scores or learned CTR predictions. Hidden preferences and true generating probabilities are not model input features. Preserve the generator version and parameters so its behavior can be explained.
- Use the same frozen outcome rules for comparable historical/live scenarios. Do not change those rules after inspecting test or experiment outcomes simply to make a favored ranking strategy win.
- Exact coefficients and distributions are documented, versioned implementation parameters; sanity-check them with observed synthetic click rates and matched/unmatched comparisons. Those checks validate the designed world, not external realism.

### Historical exposure and evaluation separation

- Generate varied historical exposure by randomized selection among eligible ads rather than replaying only ranking winners. Record the exposure policy in the dataset manifest; do not imply that this policy matches the live ranking policy.
- Every historical impression has one associated binary click label. Preserve user/ad references and impression identity; any explicit click record refers to its impression and cannot precede it. Each impression contributes at most one click.
- Order impressions by simulated time and split into 70% training, 15% validation, and 15% final testing. Keep impression and label in the same split. Use deterministic tie handling and record split boundaries.
- Fit preprocessing/model parameters on training data, choose models/settings using validation data, and reserve final testing for the reported evaluation. Historical aggregate features, if selected in the CTR ticket, may use only information available before the impression; do not read its label or future clicks.
- Synthetic train/test evaluation still shares designed world assumptions. Unseen outcomes and hidden preferences reduce trivial leakage but do not establish effectiveness for real users or eliminate every simulation bias.
- Save historical data as separate versioned training artifacts, linked to the profile/ad dataset they describe. Do not insert it into live recommendation/event tables or dashboard experiment aggregates. Offline history is not backdated through live APIs.

### Reproducibility and provenance

- Record seed, generator version, complete configuration, entity counts, simulated time range, and split definitions in a manifest. Use separate reproducible random streams for profile generation, exposure, and outcome sampling.
- Repeating the same historical inputs and generator version must reproduce the dataset. Produce data in bounded batches rather than constructing a million impressions plus all events in memory.
- A live run records its configuration, dataset/model/experiment context when available, seed, and a fresh run ID. Each opportunity has a stable identifier within the run, used to derive its request key; network retries retain that key.
- For live outcome sampling, use stable per-opportunity randomness so request completion order does not arbitrarily change the random draw assigned to an opportunity. A fresh run ID distinguishes new database activity from replay of a prior run.
- Live reruns are reproducible in configuration and sampling policy, not guaranteed identical in latency, scheduling, selected inventory, or experiment outcomes if system state changes. Record the actual run results and state instead of claiming byte-identical live behavior.

### Live simulator contract

- Default normal demonstration: two minutes targeting five new ad opportunities per second, with rate and duration configurable. This is a requested traffic rate, not a verified throughput guarantee.
- For each opportunity, request a recommendation; after receiving a selected ad, confirm display through the impression endpoint. Once confirmation succeeds, sample the click using the independent rule and submit it if sampled positive.
- Follow the lifecycle ticket for request-key replay, event deduplication, ordering, and 24-hour eligibility. Retry transient failures with bounded attempts, keeping the opportunity identity unchanged. Stop or report an opportunity as incomplete when retries are exhausted.
- A no-ad result produces neither impression nor click. An unknown user or permanent validation failure is reported as an error rather than silently converted into a negative click label. Failed event submissions must be visible in the run summary.
- Derive attribution from the returned recommendation ID and server record; never submit an invented experiment variant. Only accepted API events contribute to live experiment metrics.
- Report attempted opportunities, successful selections, no-ad outcomes, accepted impressions/clicks, retries, failures, and actual achieved rate. Label all behavioral outcomes and revenue as synthetic/simulated.

### Edge scenarios and evidence limits

Keep normal demo traffic separate from explicit scenarios for duplicate deliveries, request/event retries, missing interests, and no eligible inventory. Test expiration with a controlled clock and database failures in isolated tests instead of contaminating a normal experiment run.

Ranking experiments may show improvement, no difference, or regression. Report observed results honestly without promising a target lift or tuning the generator to force an outcome. Simulated results demonstrate behavior inside these assumptions, not real-world advertising effectiveness. Load tests measure actual software latency, throughput, errors, and bottlenecks separately.

The small default should support a quick walkthrough. Do not promise a hardware-independent generation duration for the full dataset; record its actual duration and resource use when implemented. Defaults must not auto-generate large history or overwrite live event records.

### Handoff and checks

- Phase 1 implements only the already agreed small entity seed and lifecycle APIs. Historical labels and the traffic simulator arrive in the later model/experiment/demo work as needed.
- Verify repeatable historical generation, valid references, eligibility, complete impression labels, chronological splits, hidden-input exclusion, and absence of future-data leakage in any aggregate features.
- Verify live request IDs do not collide across runs, retries do not inflate counts, event ordering is respected, failed deliveries are reported, and offline history never enters dashboard experiment totals.
- The CTR ticket owns the model/feature/evaluation details; the experiment ticket owns cohort and metric definitions; the dashboard ticket owns presentation; the benchmark ticket owns measured load-test methodology.
- No additional decision ticket is needed. Those existing tickets cover the follow-on decisions exposed here.

# Ranking phase gate

Verified on 2026-10-08 from `56497fff7ca4ac6b566b4052e8d2c5ce6d028d83`.
Dependencies 23 and 25 are done. No production code, schema, dependency version,
ranking formula or model artifact was changed. This gate adds reproducible evidence
and explanations, and improves the reused HTTP smoke's startup diagnostics/wait.

## Algorithm and accounting

V1 orders distinct user/ad target-interest overlap descending, decimal bid
descending, then ad ID ascending. Its count score has no monetary unit and its
predicted CTR/model metadata are null; it needs no model. Retrieval similarity is
not substituted for overlap.

V2 predicts the ordered candidate batch once per selection attempt and scores
`predicted_ctr * bid`: probability times simulated dollars per accepted click gives
expected simulated dollars per impression. For example, 0.10 * bid1 gives score0.10,
outranking 0.02 * bid3 = 0.06. Equal expected values use overlap, bid, then ID.
Decimal products retain the float probability's string representation without
display rounding determining ties. Zero-bid ads remain eligible. Empty pools do
not invoke inference; nonempty unusable models fail typed 503 without substitution.

The workflow selects the first ranked entry directly, locks/revalidates the winner
and advertiser, and saves one coherent bid/score/context snapshot. Changed metadata
retries the transaction, at most three attempts, rather than pairing a new bid with
an old score. Request-key replay precedes retrieval/model use. The first accepted
click credits that snapshot's bid once; expected value is never a charging amount.
Code-path audit of `ranking/strategies.py`, `services/recommendations.py` and
`services/events.py` confirms no second auction, blend, normalization, second-price
or quality-multiplier layer. Model preprocessing remains the existing feature
pipeline, distinct from prohibited cross-strategy score normalization.

For C candidates, scoring/ordered-result storage is O(C), plus interest-set costs;
full deterministic sorting is O(C log C). A maximum-only selector could be O(C),
but this interface returns the order. Dense prediction/features add O(C*F) work and
batch storage for F encoded features. This gate does not claim latency or speedup.

## Separate component measurements

[Measurement script](measure-components.py) calls the public strategies and uses
cProfile's cumulative production `_order` time to isolate sorting/key construction
and tuple conversion from scoring/inference. It does not replace production sorting
or call a private ranking function as its entry point. Separate unprofiled calls to
the public CTR adapter report feature construction and batch inference/output
validation. [Raw timings](component-timings.json) retain every sample.

Windows CPython3.10.11, AMD64 Family23 Model104, 16 logical CPUs; one caller/native
thread, 10 warmups per size and 50 measurements per component. Inputs are the first
frozen user and first 1/50/500 ads, same full native model as the comparison.

| Candidates | Feature median/P95 ms | Inference median/P95 ms | V1 profiled sort median/P95 ms | V2 profiled sort median/P95 ms |
| ---: | ---: | ---: | ---: | ---: |
| 1 | 0.063150/0.111600 | 5.081650/7.419200 | 0.004900/0.017100 | 0.012450/0.024700 |
| 50 | 0.331950/0.524800 | 5.247950/6.794200 | 0.095250/0.187500 | 0.120900/0.203200 |
| 500 | 2.854650/4.606800 | 5.769350/8.597300 | 1.072850/1.804500 | 1.403600/2.446100 |

Sorting includes profiler overhead. Its values are not an uninstrumented relative
latency comparison with the separately collected CTR timings. Model loading,
retrieval, database and HTTP are excluded; other desktop work may run. These are
component observations, not a speedup, saturation result or request-latency target.
Spec review identified the initially missing sorting measurement; this evidence
resolves that gap without production instrumentation or a new test seam.

## Identical candidate pools and sampled outcomes

[Comparison script](compare-strategies.py) loads frozen ticket 18 source snapshots
and the validated ticket 23 full native bundle. [Raw report](comparison.json) saves
the exact ordered candidate IDs and context hash for every user, both selected ads,
scores with their meanings, sampled outcomes and before/after input checksums.

- Dataset `b26ddfe8-cac2-5631-9a8f-d136bb6e1e1c`, history
  `2ed92061-8b66-59b4-8a1b-509f340d47d0`.
- Model `1597174fe75a23b1b7c5b0be58ab3ded6a63b542a3ed9408d3247e70bc1d1055`,
  model version `ctr-logistic-v1`, features `ctr-features-v1`, pipeline SHA-256
  `62cf0485bcaa21b8e8ffe210d3493c239a0d2a9ca246749bd49ecfe03299f46a`.
- Seed26 selects 200 frozen users and 500 eligible frozen ads per user without
  replacement. Both strategies receive the same objects/order per user; hashes
  remain unchanged. This declares offline pools, without invoking or comparing
  FAISS/live retrieval. Retrieval regression and prior retrieval-gate evidence
  remain separate. There is no candidate-generation treatment difference.
- The original `click-world-v1` configuration/seed18 supplies independent behavior
  probabilities, never model predictions as labels. Hidden preferences and bids
  are not supplied as new model features. Each user gets 100 sampled opportunities
  using the same `ticket26/user/opportunity` uniform draw for both selected ads.
  Repeated opportunities reuse the selected ad. No live database events are written
  by this comparison, and no inspected final-test tuning occurs.

| Strategy | Sampled impressions | Sampled clicks | Sampled observed CTR | Sampled simulated revenue | Revenue per impression |
| --- | ---: | ---: | ---: | ---: | ---: |
| V1 | 20000 | 797 | 0.03985 | 3931.5300 | 0.1965765 |
| V2 | 20000 | 941 | 0.04705 | 4619.3400 | 0.230967 |

Both select the same ad for 103 users and different ads for 97. For the first
disagreement, user4525504318142619012: V1 picks ad6927797085137952666, overlap1,
bid4.9800; V2 picks ad2446694264783862630, overlap1, bid4.9000,
predicted CTR0.04024434163419006, expected score0.197197274007531294000.
The paired samples give 2/6 clicks and 9.9600/29.4000 simulated revenue respectively.
Raw scores are not averaged or compared across strategies.

These are finite offline synthetic samples over the same entity population and
behavior assumptions used for training, not real observed experiment evidence.
Opportunities repeated within users are not independent users. The sample counts
do not establish causal lift, unseen-population generalization, statistical winner,
real-user effectiveness, actual revenue or future guaranteed improvement.

## Actual responses and lifecycle

[Native response examples](response-examples.json) were captured by
[response-examples.py](response-examples.py) through TestClient HTTP/ASGI with real
startup, PostgreSQL and retained model dependencies, without dependency overrides.
Both decisions use one unchanged music/cars two-ad pool and user context. V1 needs
no model, chooses the overlap1 music ad at bid0, emits integer score1 and null CTR.
V2 chooses cars at bid100, emits predicted CTR0.017334713604441356 and decimal score
`1.7334713604441356000000`. Their captured click credits are `0.0000` / `100.0000`.
After both ads change to bid999/inactive, replay remains identical under configured
V2 with no model; duplicates return the original single click credit. This native
ASGI check is not a socket/load benchmark. The first example attempt used an invalid
retrieval topic `unknown`; replacing the fixture with supported `cars` made the
complete check pass. No application change or test-data deletion was needed.

[Docker socket HTTP smoke](docker-http-smoke.json) reuses ticket 25's script and
retained isolated Docker PostgreSQL container/database. It explicitly prepares its
own 10,000-exposure fixture model in CPython3.12.15 and verifies recommendation,
replay after bid/deactivation changes, impression, duplicate click and captured-bid
credit. The initial Docker run failed readiness with connection refused; the original
utility did not retain startup logs, so the cause is not established. The reused
utility now allows 600 attempts with 0.1 seconds between polls and reports server
logs on failure.
The complete rerun passed: predicted CTR `0.05647824691200216`, expected score
`0.056478246912002160000`, original bid and single click credit `1.0000`.
Container model `9c2f8ff8bbf9f410bde944c512548fc7fde1c6a854b62d718372ab26de15a2e2`;
rebuilt image `sha256:9d5ca319e999288790764e976f6205ea1c3113e876963fcdd96a3cfb38879ab6`.
Native CPython is 3.10.11; native/container model identities need not match.

## Check coverage

Existing agreed public seams are sufficient; no new tests or production feature
were introduced. Focused ranking/baseline/CTR adapter and PostgreSQL ranked workflow,
recommendation, events, retrieval serving, lifecycle/resilience and model-availability
checks: **162 passed in 52.25s**. These cover formulas, batch alignment, no V1 model,
all tie levels, zero/all-zero/no-interest/empty pools, invalid numeric data, model
failure 503, metadata edits and bounded retry, saved-result replay and deduplication.

Full PostgreSQL-enabled regression in isolated `adflow_ticket26_test`:
**583 passed in 179.91s**. Strict mypy **94 source files clean**; Ruff lint/format
pass; Alembic **no new upgrade operations**; wheel/sdist build and offline lock check
(65 packages) pass. Docker configuration/build and evidence lint/format pass.
[Commands](commands.md) preserve setup/configuration and scope.

## Human checkpoint

Offered [ticket 60](../../issues/60-learning-ranking.md): explain V1/V2 units,
lower-bid winners, deterministic ties, no second auction, model failure and captured
bid; then direct a small candidate/probability change and verify ties/failure.
It stays open. No human explanation, modification or understanding is certified.
Phase 5's technical dependency unlocks when this gate is marked done after review.

Local PostgreSQL and the isolated Docker verification PostgreSQL were stopped
cleanly after checks. All verification databases, Docker data/container/network,
original frozen artifacts and durable history remain retained.

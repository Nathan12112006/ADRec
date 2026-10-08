# How will two ranking strategies choose winners without redundant scoring?

Status: resolved
Type: grilling
Labels: wayfinder:grilling
Parent: [AdFlow — Full-project decision map](../map.md)
Assignee: Nathan (with Codex)
Blocked by: 04, 05

## Question

Define exact relevance and CTR-based ranking formulas, bid units, normalization if any, tie breaking, zero bids, and predicted_ctr response semantics for the baseline. Decide whether final selection is simply the highest strategy score or requires a separate auction stage. Keep simulated accounting consistent with the event contract. Blended scoring is optional; decide it only if it earns its cost.

## Comments

The round notes below are chronological history. The final decision is under Answer.

### Confirmed ranking and selection choices

- Nathan accepted V1 retaining the Phase 1 ordering: shared-interest count descending, bid descending, ad ID ascending, applied to the retrieved candidate set once retrieval is introduced.
- Nathan accepted V2 score = predicted CTR multiplied by bid, with bid expressed as simulated dollars per click and score as expected simulated dollars per impression.
- Nathan accepted selecting the highest-ranked candidate directly, without a second blended scoring or auction-pricing stage. Actual accepted-click accounting stays at the bid captured for the recommendation.
- Both strategies use the same retrieval configuration and candidate limit within a ranking experiment; record retrieval version/mode and make fallbacks visible.
- Tie rules, zero bids, response fields, and completion checks remain open.

Claimed at Nathan's request on 2026-10-07. Retrieval and CTR decisions are resolved. Beginning a live discussion of baseline/CTR scoring, selection, and simulated economics.

Created during map charting. Resolve through a live discussion using grilling and domain-modeling. Consult the preferred-stack brief; investigate factual uncertainties against primary sources when needed.

### Final confirmation

Nathan accepted all remaining recommendations: deterministic V2 ties, zero-bid eligibility and invalid-bid rejection, explicit score/version response fields with null baseline CTR, and ranking completion checks. All ticket questions are settled.

## Answer

Resolved with Nathan on 2026-10-07. This defines ranking behavior; no ranking implementation or experiment results are claimed.

### Shared contract and candidate pool

Use interchangeable ranking strategies over the retrieved candidate set. Within a ranking experiment, both strategies share retrieval configuration and candidate limit; record actual retrieval mode/version and fallback reason. Keep retrieval fixed so the treatment changes ranking rather than also changing candidate generation. The experiment ticket owns the immutable experiment configuration.

The ranking interface takes a user and candidates, and returns scored candidates with a deterministic order and strategy/version metadata. Winner selection takes the highest-ranked eligible candidate directly; do not run another scoring stage afterward. The recommendation service still owns eligibility revalidation and atomic attribution persistence.

An empty candidate set follows the existing no-ad outcome contract; it does not cause a model call. A nonempty V2 request requires the usable model defined in the CTR ticket. The empty-interest retrieval fallback remains bid-ordered, but whichever ranking strategy is selected subsequently applies its own scoring to that candidate set.

### Ranking V1: interest overlap

Order by:

1. Distinct interests shared by the user and ad target interests, descending.
2. Bid, descending.
3. Ad ID, ascending.

Its primary score is shared-interest count, preserving the Phase 1 baseline rule. No normalization or combination of monetary and overlap units is needed. Do not silently replace this count with retrieval cosine similarity. With no overlaps, bid and ID determine order. Run no CTR inference for V1; return predicted_ctr as null and model/feature versions as absent/null.

### Ranking V2: expected simulated value

```text
score = predicted_ctr * bid
```

Bid is simulated dollars per click. The score is estimated simulated dollars per impression. For example, 0.10 * $1.00 = $0.10 outranks 0.02 * $3.00 = $0.06. Neither the highest bid nor highest predicted CTR alone necessarily wins.

Compute predicted probabilities once for the full ordered candidate batch using one model/feature version. Order by expected-value score descending, then shared-interest count descending, bid descending, and ad ID ascending. Identical inputs, candidate membership, probabilities, and configuration yield deterministic ordering. Retrieval's permitted boundary ties mean identical global candidate membership is not guaranteed across index modes.

Use finite probabilities in [0,1] and finite nonnegative bids; reject negative/nonfinite bid inputs as invalid data. Never silently coerce an invalid bid or model output to zero. Keep captured bid and actual click accounting decimal-based. Define and test score numeric representation/serialization consistently so sorting does not depend on display rounding.

Zero-bid ads remain eligible. Their V2 score and credited simulated revenue are zero. If every expected score is zero, the same tie rules choose a winner; zero score alone does not mean no eligible inventory.

### Selection and simulated accounting

There is no second auction/blended-score pass, second-price calculation, quality multiplier, or separate charging rule. Blended scoring and auction pricing are deferred beyond the agreed core.

Save the selected ad, score meaning/value, bid snapshot, strategy/version, retrieval diagnostics, and model/feature versions when applicable as one coherent selection. If eligibility or bid metadata changes during selection, revalidation must not persist an old score paired with a different bid. The saved fields describe the same decision; transaction/retry implementation must preserve this invariant.

The event-lifecycle ticket remains the canonical accounting contract: the first accepted click credits the bid captured for that recommendation once. Expected-value score is a ranking estimate, not the amount credited. Later bid changes or deactivation do not rewrite an existing recommendation's attribution or accounting. Request-key replay returns its saved selection rather than rescoring with a new model, bid, strategy, or experiment.

CTR-required requests with a missing/corrupt/incompatible model return 503 as already agreed. V1 remains available. No silent V1 substitution inside V2 and no invented baseline CTR.

### Responses and diagnostics

Expose selected ad and recommendation identity, strategy/version, score, score meaning, retrieval mode/version, and model/feature versions when applicable. Include predicted CTR for V2; explicitly null for V1. Similarity, overlap count, predicted probability, and expected value are different quantities; do not label them interchangeably.

V1's count and V2's expected monetary value are not comparable raw scores. Dashboard and experiment comparisons must use observed metrics, not cross-strategy score averages. Log sufficient selection diagnostics to explain a result without doing extra inference merely for V1 display fields.

### Completion and interview explanation

- Test both ordering rules, the lower-bid/higher-value example, deterministic ties, zero bids, all-zero scores, no-interest users, empty candidates, and invalid numeric inputs.
- Verify V1 does not require or invoke the CTR model, V2 invokes the batch predictor once, candidate/probability order stays aligned, and unusable models produce the agreed 503.
- Verify saved bid, score, and attribution describe one selection; changed metadata cannot yield mismatched accounting. Verify replay preserves the saved result and accepted-click deduplication preserves one revenue credit.
- Compare strategies over the same declared candidate sets; report selected-ad and observed outcome differences without promising CTR/revenue lift.
- Explain that V1 prioritizes overlap while V2 prioritizes model-estimated simulated revenue. V2 may select a lower-CTR ad if its bid compensates. Neither rule guarantees better observed CTR or actual revenue.
- For C candidates, interest sets and feature construction add their own costs; V2 dense prediction is O(C*F) for F encoded features. Scoring is O(C), a full deterministic sort is O(C log C), and selecting only a maximum can be O(C). Storing scores/ordered results costs O(C) beyond the feature batch. Keep inference and sorting outside API handlers and measure them separately.

No new decision ticket is needed. Experiment configuration/metrics, cache consistency, and final performance methodology remain owned by their existing tickets. Implementation stays outside this planning session.

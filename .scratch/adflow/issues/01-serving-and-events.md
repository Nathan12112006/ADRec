# What constitutes a served ad and a valid attributed click?

Status: resolved
Type: grilling
Labels: wayfinder:grilling
Parent: [AdFlow — Full-project decision map](../map.md)
Assignee: Nathan (with Codex)
Blocked by:

## Question

Define the recommendation, impression, and click lifecycle and the API contracts needed to connect them. Is an impression a successful selection, a response delivered, or a client display acknowledgement? How does a click identify its originating recommendation and experiment? Decide duplicate handling, retry semantics, invalid-event rejection, no-ad behavior, and simulated revenue accounting. Include concrete timeout/retry and stale-click scenarios. Keep conversions optional.

## Comments

The round notes below are chronological discussion history; the final contract is under Answer.

### Confirmed lifecycle choices

- Nathan chose client display confirmation as the impression definition.
- Nathan accepted request-key idempotency: retries with the same key return the same recommendation; a new key represents a new ad opportunity.
- Nathan accepted recommendation_id attribution for impressions and clicks, with user/ad and experiment attribution retained on the server.
- Nathan accepted simulated cost-per-click accounting: credit the bid captured at recommendation creation once per accepted recommendation click.
- Duplicate, expiration, ordering, and failure behavior remain under discussion; this ticket is not resolved.

Claimed for a live decision session on the recommendation, impression, and click lifecycle.

### Confirmed event and failure choices

- Duplicate impressions/clicks succeed without adding counts: at most one impression and one billable click per recommendation.
- A first click before its impression returns a retryable conflict; confirm the impression before retrying the click.
- First impressions/clicks must arrive within 24 hours of recommendation creation, judged by server receipt time. Previously accepted events are safe to retry after expiration.
- An expired recommendation request key reports expiration rather than creating a fresh recommendation.
- No eligible ads returns HTTP 204 with no recommendation/impression; an unknown user returns 404.
- A failed durable recommendation/event write returns 503; successful ad responses require the attribution record to be saved first.
- API method, no-fill retry behavior, and historical attribution after ad changes remain under discussion.

Created during map charting. Resolve through a live discussion using grilling and domain-modeling. Consult the preferred-stack brief; investigate factual uncertainties against primary sources when needed.

### Final confirmation

Nathan accepted POST recommendation creation, replayable no-ad outcomes, and preservation of historical attribution after bid or eligibility changes. All questions in this ticket are settled.

## Answer

Resolved with Nathan on 2026-10-07. This contract supersedes the original brief's GET recommendation endpoint, automatic server-side impressions, and user/ad-only click payload.

### Recommendation and replay

- Use POST /api/v1/recommendations with body {"user_id": 1001} and a required Idempotency-Key header.
- A new key identifies a new ad opportunity. Atomically save its selected recommendation and request-key association before returning HTTP 200. Include recommendation_id and retain the user, ad, bid at selection, creation time, and experiment attribution when applicable.
- Reusing the same key and user within 24 hours replays the same recommendation ID and selection; do not rerank or use the current bid/experiment. Reusing the key for a different user returns 409 Conflict.
- After 24 hours, key reuse returns 410 Gone rather than creating a fresh opportunity. The client must use a fresh key for a new opportunity.
- For an existing user with no eligible ads, return 204 No Content. Save a small request outcome for idempotent replay, but create no recommendation or impression. Reuse of this key returns 204 during its 24-hour window even if ads subsequently become available; after expiration it returns 410.
- An unknown user returns 404. Required-field and malformed-payload validation follows the API validation conventions settled in the Phase 1 ticket.

### Display and click events

- Use POST /api/v1/events/impression and POST /api/v1/events/click, each referencing recommendation_id. Derive user, ad, and experiment attribution from the stored recommendation, not client claims.
- Selection and response delivery are not impressions. A client display confirmation records the impression; the simulator must follow the same lifecycle.
- Count at most one impression and one billable click per recommendation. First acceptance and duplicate delivery return 200; a duplicate changes neither counts nor simulated revenue.
- A first click requires a recorded impression. If absent, return 409 with a reason that allows the client to confirm the impression and retry the click; do not record the rejected click.
- First events are eligible only while server receipt time is strictly before creation time plus 24 hours. Use server-recorded timestamps for this lifecycle rather than client backdating.
- A previously accepted event remains safe to retry after expiration and returns success without another count. Check for an accepted duplicate before rejecting a new expired event. A first event at or after expiration returns 410. An unknown recommendation returns 404.
- Eligibility is assessed at selection. Later bid changes or deactivation do not invalidate an existing recommendation's events within its window; they affect future selections.

### Accounting and durability

- On the first accepted click, credit the captured bid once as simulated cost-per-click revenue. A captured bid of $1.25 yields $1.25, regardless of subsequent bid changes. This is not an auction clearing price or real payment.
- Persist event acceptance and its accounting effect atomically. Database uniqueness/transaction guarantees must preserve request replay and event deduplication under concurrent retries; application-only prechecks are insufficient.
- If PostgreSQL is unavailable or a required durable write cannot complete, return 503. Do not report an unsaved recommendation/event as successful. A response timeout after a successful commit can safely be retried with the same key or recommendation ID.
- Example: selection commits but the response is lost; retry returns the saved selection. Duplicate display confirmations add one impression in total. A click accepted twice adds one click and one revenue credit. A first click after the 24-hour window is rejected; replaying an earlier accepted click still succeeds.

### Consequences and handoff

- Client acknowledgement avoids counting lost responses as displays, at the cost of one extra client event and possible undercounting when acknowledgements are lost. Clients must retry acknowledgement delivery.
- Request/event identity makes retries safe but requires persisted keys, unique event identity, and immutable attribution snapshots. Retention and cleanup must preserve these guarantees; choose their implementation in the Phase 1/delivery decisions rather than silently recycling keys.
- Recommendation storage and event writes grow with ad opportunities and accepted interactions. The Phase 1 ticket chooses storage/indexing and transaction details; benchmark work measures their cost.
- Phase 1 must exercise: response loss/replay, concurrent retries, duplicate events, click-before-impression recovery, expiration boundaries, no-ad replay, key/user mismatch, changed bid/inactive ad, unknown identities, and database failure.
- Conversions remain optional. Experiment lifecycle, full metric definitions, and historical dataset generation belong to their existing tickets. No additional decision tickets were exposed by this resolution.

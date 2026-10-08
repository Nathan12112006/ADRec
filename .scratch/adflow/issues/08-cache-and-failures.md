# What should Redis cache and how will dependency failures behave?

Status: resolved
Type: grilling
Labels: wayfinder:grilling
Parent: [AdFlow — Full-project decision map](../map.md)
Assignee: Nathan (with Codex)
Blocked by: 02, 04, 07

## Question

Choose useful cached data, keys, TTLs, invalidation/version rules, hit/miss accounting, and the smallest acceptable consistency contract. Evaluate whether recommendation caching changes impressions or experiments. Define behavior under Redis failure, stale metadata/indexes, missing model, PostgreSQL failure, and slow dependencies. Specify recovery expectations and focused failure tests.

## Comments

The round notes below are chronological history. The final decision is under Answer.

### Confirmed initial cache choices

- Nathan accepted caching only user profiles initially. Recommendation outcomes, event deduplication, experiment configuration/results, and current ad eligibility stay in PostgreSQL.
- Nathan accepted brief profile staleness with a configurable 60-second default TTL, invalidation after application-controlled profile database commits, and new cache namespaces on dataset replacement. Bid/eligibility checks retain database rules.
- Redis access/write failures bypass the optional cache and use PostgreSQL, with bounded Redis waits. PostgreSQL remains required for durable recommendations/events.
- Nathan accepted separate usable-hit, miss, error, and bypass counters. Hit ratio is hits/(hits+misses), null with no samples; errors/bypasses are not disguised as misses.
- Expiration implementation, consistency limitations, timeout/recovery settings, health behavior, and completion checks remain open.

Claimed at Nathan's request on 2026-10-07. Starting a live discussion of cache scope, consistency, expiration, dependency failures, and recovery. Prior lifecycle, retrieval, model, and experiment contracts remain binding.

Created during map charting. Resolve through a live discussion using grilling and domain-modeling. Consult the preferred-stack brief; investigate factual uncertainties against primary sources when needed.

### Final confirmation

Nathan accepted eventual consistency with a maximum 60-second TTL and downward jitter, validated versioned JSON keys, short explicit Redis timeouts without request-path retries, disposable bounded-memory Redis with degraded-but-ready behavior, and focused failure/benchmark checks. All ticket questions are settled.

## Answer

Resolved with Nathan on 2026-10-07. [Redis cache options for AdFlow](../research/redis-cache-options.md) contains primary-source findings. Its suggested tuning values are proposals; the confirmed settings below take precedence, including the 60-second rather than 300-second TTL. No cache implementation or speedup is claimed.

### Scope and authority

Cache only synthetic-user profiles needed for retrieval/ranking. PostgreSQL remains the source of truth. Do not initially cache recommendation outcomes, idempotency keys, event deduplication/accounting, experiment configuration/results, or current ad eligibility/bids. Do not cache missing users.

A profile cache hit never permits returning a recommendation without saving its durable attribution record. Bid and eligibility rechecks follow the existing selection contract. Apply the same cache policy to both experiment variants; no silent variant-specific freshness policy.

### Cache-aside lookup and keys

Use a dataset- and schema-versioned key such as adflow:{dataset_version}:profile:v1:{user_id}. Store a typed JSON envelope with matching schema version, user ID, and required profile fields. Validate decoding, identity, and schema before declaring a usable hit.

- Usable hit: return the profile without renewing its expiry.
- Ordinary miss: read PostgreSQL and best-effort populate Redis after a valid profile is found.
- Malformed/mismatched payload: report invalid-payload diagnostics, best-effort evict it, and reload PostgreSQL rather than trusting it.
- Redis read failure: bypass further Redis operations for that request, read PostgreSQL, and skip cache population.
- Redis population/write failure after a database read: keep using the valid database profile; do not fail an otherwise valid operation because cache population failed.
- Unknown user: follow the existing 404 contract and create no negative-cache entry.

Install value and expiration together using SET with EX/PX; do not risk a value without expiry through separate SET/EXPIRE calls. Catch expected Redis failures in the cache adapter rather than masking unrelated application defects.

### Freshness and invalidation

Default maximum TTL is 60 seconds, configurable. Add small downward jitter without exceeding that configured maximum, and do not slide expiry on hits. Cache entries are allowed to be briefly stale.

For an application-controlled profile change, commit PostgreSQL first, then best-effort invalidate the profile key. Invalidation can race with an earlier read filling the cache afterward. TTL bounds residence after population, not strict freshness measured from a database update. Do not advertise a guaranteed 60-second update-to-visibility bound.

Pause traffic and switch the dataset namespace consistently across serving processes during dataset replacement/reseeding. Old namespace entries expire unused; do not flush unrelated keys. Out-of-band SQL changes require explicit invalidation/namespace management or acceptance of the same staleness limitation. Live profile-edit APIs are deferred; invalidation rules still apply to scripts that change profiles.

### Waits, resource use, and recovery

Reuse one synchronous Redis client/connection pool per serving process. Bound pool size and fail fast on pool exhaustion rather than blocking indefinitely. Configure zero automatic request-path Redis retries.

Initial configurable connection and socket timeouts are each 100 ms. Pin redis-py and verify explicit settings; do not rely on conflicting documented defaults. These socket limits are not a complete wall-clock request deadline: connection establishment, operations, and scheduling can add waits. Measure the degraded path rather than promising a 100 ms total overhead.

Configure PostgreSQL pool/connect/query waits separately and keep them bounded. Required database read/write failures and timeouts return the existing 503, without unsaved recommendations or accepted events. A cache does not enable offline serving when PostgreSQL is unavailable.

Use disposable Redis with a starting configurable maxmemory of 128 MB, allkeys-lru eviction, and persistence disabled. Leave process/container memory headroom beyond the dataset limit. Restart/eviction causes misses and normal repopulation; the cache need not recover old contents. No distributed locks, cache replicas, or persistent cache backups initially. Concurrent misses may duplicate database reads; measure that cost before adding stampede coordination.

After Redis becomes available, later requests can naturally use it again. Do not add hidden long retry loops or mutate durable request/event state during cache recovery. Changes to timeout/pool/memory tuning require documented measurement, not a new source-of-truth role for Redis.

### Dependency behavior and health

| Condition | Behavior |
| --- | --- |
| Redis unavailable, slow, exhausted, or rejecting writes | Bypass/read PostgreSQL; report cache degradation; valid durable work can succeed |
| PostgreSQL unavailable or required operation times out | Return 503; do not invent an empty dataset or successful event |
| Missing/stale/corrupt/incompatible retrieval index | Existing exact-current-eligible-inventory fallback, visibly marked |
| Missing/corrupt/incompatible CTR model for nonempty V2 ranking | Existing 503; V1 remains available, with no silent treatment substitution |
| No eligible ads | Existing durable replayable no-ad outcome and 204; not a dependency failure |

Liveness is independent of dependencies. PostgreSQL readiness remains required; Redis failure reports degraded cache status but does not make an otherwise database-ready application unready. Report model/index capabilities separately so generic readiness does not imply that every ranking strategy or ANN mode is usable.

### Cache metrics

Count usable hits, ordinary misses, invalid payloads, cache read/write errors, and bypasses separately. Hit ratio is hits/(hits+misses), null when there are no eligible samples. Never count a read timeout or malformed payload as an ordinary miss.

Operation/error counters are diagnostics, not mutually exclusive request outcomes: an ordinary miss can be followed by a population-write error. Identify bypass reason (disabled, read failure, pool exhaustion, etc.) and measurement window/process coverage. Keep metrics observable without requiring Redis to store its own failure counters. Do not present a missing telemetry window as zero errors.

### Completion checks and tradeoffs

- Test usable hits, ordinary misses, expiry/no renewal, configured TTL maximum/jitter, invalid JSON/schema/identity, unknown users, and dataset namespace isolation.
- Test Redis read/write failures, explicit timeouts, pool exhaustion, restart/eviction recovery, concurrent misses, and the documented commit/invalidation race.
- Verify cache failure does not duplicate recommendations, impressions, clicks, or accounting, and does not bypass required PostgreSQL persistence. Verify readiness/degraded capability reporting.
- Compare cache enabled versus disabled with identical declared traffic, database/index/model state, and hardware. Separate cold/warm behavior and report errors, hit ratio, database work, and latency. No speedup is required; retain a slower result honestly.
- Explain cache-aside, eventual consistency, and why saved recommendations/events remain durable. Redis lookup avoids some profile reads but adds network/serialization work; memory grows with cached profile count/payload and pool resources. Duplicate misses and exact retrieval fallback can shift load back to PostgreSQL. Measure before introducing coordination or more cached entities.

No new decision ticket is needed. Dashboard availability presentation and final measurement windows/workloads belong to the dashboard and benchmark tickets; final deployment/retention choices remain in delivery. No implementation/tests/benchmarks ran during this resolution.

# HTTP load-test evidence options

Research date: 2026-10-07. Supports ticket 10; this records facts and implications, not user decisions or measured results. No benchmark was run. Read the project domain and issue-tracker instructions; no `docs/adr/` directory exists.

## Concurrency and workload

Locust creates a scenario instance per simulated user, running tasks in a greenlet. Wait time applies after a task, not after every HTTP call. `constant_pacing` and `constant_throughput` limit task iterations; they cannot guarantee offered throughput when tasks take longer than their interval. Therefore 10/100/500 Locust users mean concurrent actors, not requests per second or simultaneous requests. With sequential requests each actor has at most one outstanding HTTP request; many actors may be waiting. [Writing a locustfile](https://docs.locust.io/en/2.46.6/writing-a-locustfile.html), [wait-time API](https://docs.locust.io/en/latest/api.html)

Application implications (not Locust requirements): distinguish a recommendation-only workload, using a fresh request key per new opportunity, from a lifecycle workload that requests a recommendation, confirms an impression, then optionally submits its click. Report opportunities/second and HTTP requests/second separately: a successful lifecycle normally makes two requests plus a probabilistic click request. Keep replay, no-ad, and deliberate failure scenarios identifiable. Locust user count and distinct synthetic profile count are separate parameters. A fixed-user closed loop naturally slows its arrival rate as responses slow; it does not establish capacity at a fixed external arrival rate.

## Timing the measurement interval

`--headless`, `--users`, and `--spawn-rate` support scripted runs. `--run-time` starts at test start, including ramp-up. Shutdown normally interrupts tasks immediately; `--stop-timeout` permits bounded completion. Thus ramp, warmup, measurement, and drain need explicit boundaries, and partial lifecycles at shutdown must be reported. [Headless runs](https://docs.locust.io/en/stable/running-without-web-ui.html)

`--reset-stats` resets after spawning completes, not after an additional steady-state warmup; distributed runs need it on both master and workers. Resetting Locust statistics does not reset AdFlow database/cache state. A warmup procedure must specify its actual boundary and coordinate any server counters used in the report. [Configuration](https://docs.locust.io/en/stable/configuration.html)

## Client behavior and validation

`HttpUser` uses Requests; `FastHttpUser` uses geventhttpclient and reduces generator CPU overhead. It does not intrinsically reduce application response time. Both permit sequential user scenarios; additional greenlets are needed for concurrent requests within one user. Keep client type and connection reuse consistent between comparisons. [HTTP-client guidance](https://docs.locust.io/en/stable/increase-performance.html)

Use stable request names to group dynamic recommendation/event URLs. `catch_response` can mark a 2xx response failed when its payload violates the contract. Default HTTP success alone cannot establish a valid recommendation. For `HttpUser`, the measured interval wraps the HTTP call, before later application validation; ordinary nonstreaming calls read the response body, while streaming changes that scope. This is client-observed HTTP duration, not a pure server pipeline timer. [HTTP client source](https://docs.locust.io/en/2.46.6/_modules/locust/clients.html)

Requests has no timeout unless explicitly configured; its timeout is not a complete-response wall-clock deadline. [Requests timeouts](https://requests.readthedocs.io/en/latest/user/quickstart/#timeouts) FastHttpUser has separate connection/network timeout settings and retry/TLS settings; the inspected source defaults to 60-second connection/network limits, zero retries, and disabled TLS verification. Explicitly configure and record relevant settings rather than assume client equivalence. [Fast HTTP source](https://docs.locust.io/en/2.46.6/_modules/locust/contrib/fasthttp.html)

Project implications: count transport, timeout, HTTP, and semantic errors; separate new selections, no-ad results, replays, and failed attempts. A success-only latency claim needs separate instrumentation, because a generic endpoint group can mix outcomes. Keep client HTTP time, server request time, and retrieval/filtering/ranking/database component times distinct. A lifecycle task timer includes multiple HTTP calls and simulator work, so label it separately.

## Percentiles and exports

The inspected Locust statistics source uses rounded response-time histogram buckets for percentile calculations, not raw samples. CSV history mixes current rates with cumulative counts/averages; its percentile choice calls `_percentile_fields(..., use_current=self.full_history)`, so scope differs with the full-history setting. Current-percentile windows default to roughly ten seconds. Preserve full-run summaries and history with explicit scope; do not average interval P95s into a full-run P95 or describe CSV history as per-request raw data. This is version-sensitive: pin the installed version and inspect its export schema. [Statistics source](https://docs.locust.io/en/stable/_modules/locust/stats.html)

CLI options export CSV and HTML and allow an error exit code; configuration may be overridden by environment variables and command arguments. Preserve resolved settings, not just a command that silently inherits local configuration. [Configuration and precedence](https://docs.locust.io/en/stable/configuration.html)

Proposed provenance fields for discussion: application commit, dataset manifest/seed/counts, model/index versions, retrieval/ranking/cache modes, run ID, fresh-key policy, user/profile distribution, wait/pacing rules, click generator configuration, spawn schedule, warmup/measurement/drain timestamps, actual achieved users, software versions, client timeouts/retries, machine topology/resources, Docker limits, server workers/threads, database pools, logs, exports, generator/server CPU and memory. These are project reporting suggestions rather than guarantees supplied by Locust.

## Generator limits and honest scope

Locust supports master/worker generation; the master does not run users. One process cannot use all CPU cores, and generator CPU exhaustion emits warnings. `--processes` uses fork and is unavailable on Windows, so local Windows execution needs separate workers or a compatible Linux environment for that convenience option. [Distributed generation](https://docs.locust.io/en/stable/running-distributed.html)

gevent greenlets cooperate on one OS thread: CPU-intensive work or blocking operations that bypass its event loop can prevent other users from running. Avoid rebuilding profiles or computing expensive outcome rules in every hot-path iteration; measure generator utilization even when using FastHttpUser. [gevent scheduling](https://www.gevent.org/intro.html#cooperative-multitasking)

Project implications: colocated load generation competes with the server for resources and must be disclosed. Separate placement improves isolation but adds network effects. Falling achieved RPS, rising latency/errors, generator warnings, resource exhaustion, or failure to attain requested users must remain visible. An incomplete 500-user run is evidence of a limitation, not a successful 500-user capacity claim. Exact duration, repetition count, placement, and acceptance gates remain ticket decisions.

from typing import Any

from app.simulator import traffic
from app.simulator.traffic import UserProfile, opportunity_key, simulate


def test_run_scoped_keys_are_stable_but_distinct_between_runs() -> None:
    assert opportunity_key("00000000-0000-0000-0000-000000000001", 4) == opportunity_key(
        "00000000-0000-0000-0000-000000000001", 4
    )
    assert opportunity_key("run-a", 4) != opportunity_key("run-b", 4)


def _run(
    scenario: str, response: dict[str, Any] | None = None
) -> tuple[dict[str, Any], list[tuple[Any, ...]]]:
    clock = [0.0]
    calls: list[tuple[Any, ...]] = []

    def now() -> float:
        return clock[0]

    def sleep(seconds: float) -> None:
        clock[0] += seconds

    def send(*args: Any, **kwargs: Any) -> tuple[int, dict[str, Any] | None, int]:
        calls.append((args, kwargs))
        path = args[1]
        if path.endswith("recommendations"):
            return (200, response, 0) if response is not None else (204, None, 0)
        return 200, {"event_type": path.rsplit("/", 1)[-1]}, 0

    result = simulate(
        base_url="http://example.test",
        users=(UserProfile(1, (), (), "desktop"),),
        duration_seconds=0.21,
        rate_per_second=10,
        scenario=scenario,
        run_id="00000000-0000-0000-0000-000000000001",
        now=now,
        sleep=sleep,
        send=send,
    )
    return result, calls


def test_no_ad_is_reported_without_an_impression_or_click() -> None:
    summary, calls = _run("no-ad")
    assert summary["attempts"] == 3
    assert summary["no_ad"] == 3
    assert summary["accepted_impressions"] == 0
    assert summary["accepted_clicks"] == 0
    assert all(args[1].endswith("recommendations") for args, _ in calls)


def test_empty_interest_scenario_runs_request_lifecycle() -> None:
    summary, calls = _run("no-interest")
    assert summary["attempts"] == 3
    assert all(args[1].endswith("recommendations") for args, _ in calls)


def test_duplicate_scenario_reuses_recommendation_identity_and_separates_counts() -> None:
    selected = {
        "recommendation_id": "rec-1",
        "experiment_variant": "control",
        "selection": {"id": 2, "category": "technology", "interests": ["technology"]},
    }
    summary, calls = _run("duplicates", selected)
    assert summary["selections"] == summary["accepted_impressions"]
    assert summary["backend_assigned_variants"] == {"control": 3}
    event_payloads = [kwargs.get("key") for args, kwargs in calls if "/events/" in args[1]]
    assert event_payloads == [None] * len(event_payloads)
    recommendation_keys = [
        kwargs["key"] for args, kwargs in calls if args[1].endswith("recommendations")
    ]
    assert len(set(recommendation_keys)) == 3


def test_transient_retry_preserves_request_identity(monkeypatch: Any) -> None:
    requests: list[tuple[Any, ...]] = []
    responses = iter([(429, None), (200, {"ok": True})])

    def request(*args: Any, **kwargs: Any) -> tuple[int, dict[str, Any] | None]:
        requests.append((args, kwargs))
        return next(responses)

    monkeypatch.setattr(traffic, "_request", request)
    status, payload, retries = traffic.request_with_retries(
        "http://example.test",
        "/api/v1/recommendations",
        {"user_id": 1},
        key="adflow/run/0",
        sleep=lambda _: None,
    )
    assert (status, payload, retries) == (200, {"ok": True}, 1)
    assert requests[0] == requests[1]

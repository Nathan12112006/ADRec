"""Live traffic lifecycle and bounded HTTP retries."""

from __future__ import annotations

import json
import time
from collections import Counter
from dataclasses import dataclass, field
from random import Random
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from uuid import UUID, uuid4

from app.history.outcomes import OutcomeAd, OutcomeConfig, OutcomeGenerator, OutcomeUser

RETRYABLE_STATUS = {408, 429, 500, 502, 503, 504}


@dataclass(frozen=True)
class UserProfile:
    id: int
    interests: tuple[str, ...]
    category_preferences: tuple[str, ...]
    device: str

    def outcome_user(self) -> OutcomeUser:
        return OutcomeUser(
            id=self.id,
            interests=self.interests,
            category_preferences=self.category_preferences,
            device=self.device,
        )


@dataclass
class RunSummary:
    run_id: str
    seed: int
    scenario: str
    requested_rate_per_second: float
    requested_duration_seconds: float
    started_at: float
    attempts: int = 0
    selections: int = 0
    no_ad: int = 0
    impressions: int = 0
    clicks: int = 0
    duplicates_sent: int = 0
    retries: int = 0
    failures: Counter[str] = field(default_factory=Counter)
    variants: Counter[str] = field(default_factory=Counter)
    completed_at: float | None = None

    def as_dict(self) -> dict[str, Any]:
        elapsed = max(0.0, (self.completed_at or time.monotonic()) - self.started_at)
        return {
            "run_id": self.run_id,
            "seed": self.seed,
            "scenario": self.scenario,
            "synthetic": True,
            "source": "live API traffic; separate from offline historical exposures",
            "requested_rate_per_second": self.requested_rate_per_second,
            "requested_duration_seconds": self.requested_duration_seconds,
            "elapsed_seconds": round(elapsed, 3),
            "attempts": self.attempts,
            "achieved_opportunities_per_second": round(self.attempts / elapsed, 3)
            if elapsed
            else 0,
            "completion_fraction": round(min(1.0, elapsed / self.requested_duration_seconds), 3)
            if self.requested_duration_seconds
            else 1.0,
            "selections": self.selections,
            "no_ad": self.no_ad,
            "accepted_impressions": self.impressions,
            "accepted_clicks": self.clicks,
            "duplicate_event_requests": self.duplicates_sent,
            "retries": self.retries,
            "failures_by_code": dict(sorted(self.failures.items())),
            "backend_assigned_variants": dict(sorted(self.variants.items())),
        }


def opportunity_key(run_id: str, index: int) -> str:
    """Stable within a run and globally fresh because each run uses a fresh UUID."""
    return f"adflow/{run_id}/{index}"


def _request(
    base_url: str, path: str, payload: dict[str, Any], *, key: str | None = None
) -> tuple[int, dict[str, Any] | None]:
    headers = {"Content-Type": "application/json"}
    if key is not None:
        headers["Idempotency-Key"] = key
    request = Request(
        base_url.rstrip("/") + path,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    with urlopen(request, timeout=5) as response:
        body = response.read()
        return response.status, json.loads(body) if body else None


def request_with_retries(
    base_url: str,
    path: str,
    payload: dict[str, Any],
    *,
    key: str | None = None,
    max_retries: int = 3,
    sleep: Any = time.sleep,
) -> tuple[int, dict[str, Any] | None, int]:
    """Retry only transient delivery failures, preserving opportunity/event identity."""
    for attempt in range(max_retries + 1):
        try:
            status, body = _request(base_url, path, payload, key=key)
            if status not in RETRYABLE_STATUS or attempt == max_retries:
                return status, body, attempt
        except HTTPError as error:
            if error.code not in RETRYABLE_STATUS or attempt == max_retries:
                try:
                    detail = json.loads(error.read())
                except (ValueError, OSError):
                    detail = None
                return error.code, detail, attempt
        except (URLError, TimeoutError, OSError):
            if attempt == max_retries:
                return 0, None, attempt
        sleep(min(0.1 * 2**attempt, 0.8))
    raise AssertionError("unreachable")


def simulate(
    *,
    base_url: str,
    users: tuple[UserProfile, ...],
    duration_seconds: float = 120,
    rate_per_second: float = 5,
    seed: int = 42,
    scenario: str = "normal",
    run_id: str | None = None,
    max_retries: int = 3,
    sleep: Any = time.sleep,
    now: Any = time.monotonic,
    send: Any = request_with_retries,
) -> dict[str, Any]:
    """Generate sequential opportunities on a paced schedule and report accepted events."""
    if duration_seconds <= 0 or rate_per_second <= 0:
        raise ValueError("duration and rate must be positive")
    if not users:
        raise ValueError("no synthetic users are available")
    if scenario not in {"normal", "duplicates", "no-interest", "no-ad"}:
        raise ValueError("unknown scenario")
    identity = run_id or str(uuid4())
    UUID(identity)
    started = now()
    summary = RunSummary(identity, seed, scenario, rate_per_second, duration_seconds, started)
    rng = Random(seed)
    outcomes = OutcomeGenerator(OutcomeConfig(), seed=seed)
    deadline = started + duration_seconds
    index = 0
    while now() < deadline:
        due = started + index / rate_per_second
        if now() < due:
            sleep(due - now())
        if now() >= deadline:
            break
        profile = users[rng.randrange(len(users))]
        key = opportunity_key(identity, index)
        summary.attempts += 1
        index += 1
        status, response, retries = send(
            base_url,
            "/api/v1/recommendations",
            {"user_id": profile.id},
            key=key,
            max_retries=max_retries,
            sleep=sleep,
        )
        summary.retries += retries
        if status == 204:
            summary.no_ad += 1
            continue
        if status != 200 or response is None:
            detail = (response or {}).get("error", {})
            summary.failures[str(detail.get("code", f"http_{status}"))] += 1
            continue
        summary.selections += 1
        variant = response.get("experiment_variant")
        if variant:
            summary.variants[variant] += 1
        recommendation_id = response["recommendation_id"]
        event = {"recommendation_id": recommendation_id}
        event_status, event_response, event_retries = send(
            base_url,
            "/api/v1/events/impression",
            event,
            max_retries=max_retries,
            sleep=sleep,
        )
        summary.retries += event_retries
        if event_status != 200 or event_response is None:
            detail = (event_response or {}).get("error", {})
            summary.failures[str(detail.get("code", f"http_{event_status}"))] += 1
            continue
        summary.impressions += 1
        if scenario == "duplicates":
            send(base_url, "/api/v1/events/impression", event, max_retries=max_retries, sleep=sleep)
            summary.duplicates_sent += 1
        selection = response["selection"]
        ad = OutcomeAd(
            id=selection["id"],
            category=selection["category"],
            interests=tuple(selection["interests"]),
        )
        if outcomes.sample(profile.outcome_user(), ad, opportunity=f"{identity}/{index - 1}"):
            click_status, click_response, click_retries = send(
                base_url,
                "/api/v1/events/click",
                event,
                max_retries=max_retries,
                sleep=sleep,
            )
            summary.retries += click_retries
            if click_status == 200 and click_response is not None:
                summary.clicks += 1
                if scenario == "duplicates":
                    send(
                        base_url,
                        "/api/v1/events/click",
                        event,
                        max_retries=max_retries,
                        sleep=sleep,
                    )
                    summary.duplicates_sent += 1
            else:
                detail = (click_response or {}).get("error", {})
                summary.failures[str(detail.get("code", f"http_{click_status}"))] += 1
    summary.completed_at = now()
    return summary.as_dict()

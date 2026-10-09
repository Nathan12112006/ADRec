"""Shared closed-loop workloads for Locust's single-worker reference setup."""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from itertools import count
from random import Random
from typing import Any
from urllib.error import URLError
from urllib.request import urlopen
from uuid import uuid4

from locust import HttpUser, events
from locust.exception import StopUser
from requests.exceptions import Timeout
from sqlalchemy import select

from app.core.config import ConfigurationError, load_settings
from app.db.session import Database
from app.history.outcomes import OutcomeAd, OutcomeConfig, OutcomeGenerator, OutcomeUser
from app.models.records import Dataset, User

RETRYABLE_STATUSES = {408, 429, 500, 502, 503, 504}
_user_slot = count()


@dataclass(frozen=True)
class LoadProfile:
    id: int
    interests: tuple[str, ...]
    category_preferences: tuple[str, ...]
    age_group: str
    device: str

    def outcome_user(self) -> OutcomeUser:
        return OutcomeUser(
            id=self.id,
            interests=self.interests,
            category_preferences=self.category_preferences,
            device=self.device,
        )


@dataclass(frozen=True)
class LoadConfig:
    seed: int
    user_selection: str
    hot_user_count: int
    max_retries: int
    request_timeout_seconds: float


@dataclass
class RunCounters:
    run_id: str
    dataset_id: str
    started_at: datetime
    workload: str
    seed: int
    user_selection: str
    profile_count: int
    hot_user_count: int
    configured_users: int
    spawn_rate: float
    max_retries: int
    request_timeout_seconds: float
    opportunities_started: int = 0
    opportunities_completed: int = 0
    selections: int = 0
    no_ad_outcomes: int = 0
    accepted_impressions: int = 0
    accepted_clicks: int = 0
    client_retry_attempts: int = 0
    backend_replays: int = 0
    transport_errors: int = 0
    timeouts: int = 0
    http_errors: Counter[str] = field(default_factory=Counter)
    application_error_codes: Counter[str] = field(default_factory=Counter)
    semantic_errors: Counter[str] = field(default_factory=Counter)
    profile_samples: Counter[int] = field(default_factory=Counter)
    failed_opportunities: int = 0
    incomplete_opportunities: int = 0

    def as_dict(self, *, finished_at: datetime) -> dict[str, Any]:
        return {
            "type": "adflow_locust_summary",
            "scope": "whole_locust_run_including_warmup_measurement_and_drain",
            "run_id": self.run_id,
            "workload": self.workload,
            "dataset_id": self.dataset_id,
            "synthetic": True,
            "seed": self.seed,
            "user_selection": self.user_selection,
            "profile_population": self.profile_count,
            "hot_user_count": self.hot_user_count,
            "configured_locust_users": self.configured_users,
            "spawn_rate_users_per_second": self.spawn_rate,
            "max_retries": self.max_retries,
            "request_timeout_seconds": self.request_timeout_seconds,
            "started_at": self.started_at.isoformat(),
            "finished_at": finished_at.isoformat(),
            "opportunities_started": self.opportunities_started,
            "opportunities_completed": self.opportunities_completed,
            "selections": self.selections,
            "no_ad_outcomes": self.no_ad_outcomes,
            "accepted_impressions": self.accepted_impressions,
            "accepted_clicks": self.accepted_clicks,
            "failed_opportunities": self.failed_opportunities,
            "incomplete_opportunities": self.incomplete_opportunities,
            "client_retry_attempts": self.client_retry_attempts,
            "backend_confirmed_replays": self.backend_replays,
            "errors": {
                "transport": self.transport_errors,
                "timeouts": self.timeouts,
                "http_by_status": dict(sorted(self.http_errors.items())),
                "application_by_code": dict(sorted(self.application_error_codes.items())),
                "semantic_by_reason": dict(sorted(self.semantic_errors.items())),
            },
            "distinct_profiles_sampled": len(self.profile_samples),
        }


_config: LoadConfig | None = None
_profiles: tuple[LoadProfile, ...] = ()
_hot_profiles: tuple[LoadProfile, ...] = ()
_counters: RunCounters | None = None


def _settings_profiles() -> tuple[str, tuple[LoadProfile, ...]]:
    settings = load_settings()
    database = Database(settings)
    try:
        with database.session() as session:
            dataset = session.scalar(
                select(Dataset).order_by(Dataset.created_at.desc(), Dataset.id.desc()).limit(1)
            )
            if dataset is None:
                raise ValueError("the application database has no prepared dataset")
            profiles = tuple(
                LoadProfile(
                    id=row.id,
                    interests=tuple(row.interests),
                    category_preferences=tuple(row.category_preferences),
                    age_group=row.age_group,
                    device=row.device,
                )
                for row in session.scalars(
                    select(User).where(User.dataset_id == dataset.id).order_by(User.id)
                )
            )
        if not profiles:
            raise ValueError("the newest dataset has no synthetic users")
        return str(dataset.id), profiles
    finally:
        database.dispose()


@events.init_command_line_parser.add_listener
def add_adflow_options(parser: Any) -> None:
    parser.add_argument(
        "--adflow-seed", type=int, default=42, help="seed for reproducible user/outcome selection"
    )
    parser.add_argument(
        "--adflow-run-id", type=str, default=None, help="optional run UUID supplied by the runner"
    )
    parser.add_argument(
        "--adflow-user-selection",
        choices=("uniform", "hot"),
        default="uniform",
        help="sample all current-dataset profiles uniformly or use a fixed hot-user set",
    )
    parser.add_argument(
        "--adflow-hot-user-count",
        type=int,
        default=1,
        help="number of lowest-ID profiles in the deterministic hot set",
    )
    parser.add_argument(
        "--adflow-max-retries",
        type=int,
        default=0,
        help="bounded retries after transport/timeout or selected transient HTTP errors",
    )
    parser.add_argument(
        "--adflow-request-timeout-seconds",
        type=float,
        default=5.0,
        help="finite timeout for each HTTP attempt",
    )


@events.test_start.add_listener
def start_adflow_run(environment: Any, **_: Any) -> None:
    global _config, _profiles, _hot_profiles, _counters
    options = environment.parsed_options
    if options.adflow_max_retries < 0 or options.adflow_max_retries > 8:
        raise ValueError("--adflow-max-retries must be between 0 and 8")
    if options.adflow_request_timeout_seconds <= 0:
        raise ValueError("--adflow-request-timeout-seconds must be positive")
    try:
        dataset_id, profiles = _settings_profiles()
    except (ConfigurationError, OSError, ValueError) as error:
        if environment.runner is not None:
            environment.runner.quit()
        raise RuntimeError(
            f"could not load AdFlow profiles from the application database: {error}"
        ) from error

    hot_count = options.adflow_hot_user_count
    if hot_count < 1 or hot_count > len(profiles):
        raise ValueError("--adflow-hot-user-count must fit the current dataset user population")
    _config = LoadConfig(
        seed=options.adflow_seed,
        user_selection=options.adflow_user_selection,
        hot_user_count=hot_count,
        max_retries=options.adflow_max_retries,
        request_timeout_seconds=options.adflow_request_timeout_seconds,
    )
    _profiles = profiles
    _hot_profiles = profiles[:hot_count]
    run_id = str(options.adflow_run_id or uuid4())
    _counters = RunCounters(
        run_id=run_id,
        dataset_id=dataset_id,
        started_at=datetime.now(timezone.utc),
        workload=str(getattr(environment.user_classes[0], "workload_name", "unknown")),
        seed=_config.seed,
        user_selection=_config.user_selection,
        profile_count=len(profiles),
        hot_user_count=hot_count if _config.user_selection == "hot" else 0,
        configured_users=int(options.num_users),
        spawn_rate=float(options.spawn_rate),
        max_retries=_config.max_retries,
        request_timeout_seconds=_config.request_timeout_seconds,
    )
    print(
        json.dumps(
            {
                "type": "adflow_locust_start",
                "run_id": run_id,
                "dataset_id": dataset_id,
                "profile_population": len(profiles),
                "user_selection": _config.user_selection,
                "hot_user_count": _counters.hot_user_count,
                "configured_locust_users": _counters.configured_users,
                "spawn_rate_users_per_second": _counters.spawn_rate,
                "note": (
                    "Locust user count is concurrency, not achieved requests "
                    "or opportunities per second."
                ),
            },
            sort_keys=True,
        ),
        flush=True,
    )


@events.test_stop.add_listener
def finish_adflow_run(environment: Any, **_: Any) -> None:
    if _counters is None:
        return
    _counters.incomplete_opportunities = max(
        0, _counters.opportunities_started - _counters.opportunities_completed
    )
    print(json.dumps(_counters.as_dict(finished_at=datetime.now(timezone.utc)), sort_keys=True))


@dataclass(frozen=True)
class _RequestResult:
    status: int
    body: dict[str, Any] | None
    retryable: bool
    valid: bool


class AdFlowHttpUser(HttpUser):
    """Common per-user profile selection, idempotency and semantic response handling."""

    abstract = True
    wait_time = lambda self: 0.0  # noqa: E731  # Locust's zero wait creates closed-loop load.
    workload_name = "abstract"

    def on_start(self) -> None:
        if _config is None or _counters is None or not _profiles:
            raise StopUser()
        self._slot = next(_user_slot)
        self._random = Random(_config.seed + self._slot)
        population = _hot_profiles if _config.user_selection == "hot" else _profiles
        self._profile = self._random.choice(population)
        self._sequence = 0
        self._outcomes = OutcomeGenerator(OutcomeConfig(), seed=_config.seed)

    def run_opportunity(self, *, lifecycle: bool) -> None:
        assert _counters is not None and _config is not None
        sequence = self._sequence
        self._sequence += 1
        opportunity_key = (
            f"adflow-locust/{_counters.run_id}/{self.workload_name}/{self._slot}/{sequence}"
        )
        _counters.opportunities_started += 1
        _counters.profile_samples[self._profile.id] += 1
        recommendation = self._recommend(opportunity_key)
        if recommendation.status == 204 and recommendation.valid:
            _counters.no_ad_outcomes += 1
            _counters.opportunities_completed += 1
            return
        if not recommendation.valid or recommendation.body is None:
            _counters.failed_opportunities += 1
            _counters.opportunities_completed += 1
            return

        _counters.selections += 1
        if recommendation.body["replayed"]:
            _counters.backend_replays += 1
        if lifecycle:
            self._run_lifecycle(recommendation.body, opportunity_key)
        _counters.opportunities_completed += 1

    def _recommend(self, key: str) -> _RequestResult:
        assert _config is not None and _counters is not None

        def validate(body: dict[str, Any]) -> str | None:
            selection = body.get("selection")
            if body.get("user_id") != self._profile.id:
                return "recommendation_user_mismatch"
            if not isinstance(body.get("replayed"), bool):
                return "recommendation_missing_replayed_flag"
            if not isinstance(body.get("recommendation_id"), str):
                return "recommendation_missing_id"
            if not isinstance(selection, dict):
                return "recommendation_missing_selection"
            if not isinstance(selection.get("id"), int) or selection["id"] <= 0:
                return "recommendation_invalid_ad_id"
            if not isinstance(selection.get("category"), str):
                return "recommendation_missing_category"
            if not isinstance(selection.get("interests"), list):
                return "recommendation_invalid_interests"
            return None

        result = self._request(
            "POST",
            "/api/v1/recommendations",
            {"user_id": self._profile.id},
            name="Recommendation",
            key=key,
            expected_statuses={200, 204},
            accepts_no_ad=True,
            validator=validate,
        )
        return result

    def _run_lifecycle(self, recommendation: dict[str, Any], opportunity_key: str) -> None:
        assert _counters is not None
        recommendation_id = recommendation["recommendation_id"]
        event_body = {"recommendation_id": recommendation_id}

        def validate_impression(body: dict[str, Any]) -> str | None:
            return self._validate_event(body, recommendation_id, "impression")

        impression = self._request(
            "POST",
            "/api/v1/events/impression",
            event_body,
            name="Impression",
            expected_statuses={200},
            validator=validate_impression,
        )
        if not impression.valid or impression.body is None:
            _counters.failed_opportunities += 1
            return
        _counters.accepted_impressions += 1

        selection = recommendation["selection"]
        ad = OutcomeAd(
            id=selection["id"],
            category=selection["category"],
            interests=tuple(selection["interests"]),
        )
        outcome_key = f"{_config.seed}/{self.workload_name}/{self._slot}/{self._sequence - 1}"
        if self._outcomes.sample(self._profile.outcome_user(), ad, opportunity=outcome_key):

            def validate_click(body: dict[str, Any]) -> str | None:
                return self._validate_event(body, recommendation_id, "click")

            click = self._request(
                "POST",
                "/api/v1/events/click",
                event_body,
                name="Click",
                expected_statuses={200},
                validator=validate_click,
            )
            if click.valid:
                _counters.accepted_clicks += 1
            else:
                _counters.failed_opportunities += 1

    @staticmethod
    def _validate_event(
        body: dict[str, Any], recommendation_id: str, event_type: str
    ) -> str | None:
        if body.get("recommendation_id") != recommendation_id:
            return "event_recommendation_mismatch"
        if body.get("event_type") != event_type:
            return "event_type_mismatch"
        if not isinstance(body.get("user_id"), int) or not isinstance(body.get("ad_id"), int):
            return "event_missing_identity"
        return None

    def _request(
        self,
        method: str,
        path: str,
        payload: dict[str, Any],
        *,
        name: str,
        expected_statuses: set[int],
        validator: Any,
        key: str | None = None,
        accepts_no_ad: bool = False,
    ) -> _RequestResult:
        assert _config is not None and _counters is not None
        for attempt in range(_config.max_retries + 1):
            retry = attempt > 0
            headers = {"Idempotency-Key": key} if key is not None else None
            with self.client.request(
                method,
                path,
                json=payload,
                headers=headers,
                name=f"{name}/retry" if retry else name,
                catch_response=True,
                timeout=_config.request_timeout_seconds,
            ) as response:
                status = int(response.status_code or 0)
                body = _json_body(response)
                retryable = False
                valid = False
                if status == 0:
                    error = getattr(response, "error", None)
                    is_timeout = (
                        isinstance(error, Timeout) or "timeout" in type(error).__name__.lower()
                    )
                    if is_timeout:
                        _counters.timeouts += 1
                    else:
                        _counters.transport_errors += 1
                    response.failure("request timeout" if is_timeout else "transport error")
                    retryable = True
                elif status in expected_statuses:
                    if status == 204 and accepts_no_ad:
                        response.success()
                        valid = True
                    elif body is None:
                        _counters.semantic_errors["invalid_json"] += 1
                        response.failure("response was not a JSON object")
                    else:
                        reason = validator(body)
                        if reason is not None:
                            _counters.semantic_errors[reason] += 1
                            response.failure(reason)
                        else:
                            if name == "Recommendation":
                                population = "replay" if body["replayed"] else "new"
                                response.request_meta["name"] = (
                                    f"Recommendation/{population}_retry"
                                    if retry
                                    else f"Recommendation/{population}"
                                )
                            response.success()
                            valid = True
                else:
                    code = body.get("error", {}).get("code") if body else None
                    _counters.http_errors[str(status)] += 1
                    if code is not None:
                        _counters.application_error_codes[str(code)] += 1
                    response.failure(f"HTTP {status}" + (f" ({code})" if code else ""))
                    retryable = status in RETRYABLE_STATUSES

            if valid:
                return _RequestResult(status, body, False, True)
            if retryable and retry:
                _counters.client_retry_attempts += 1
            if not retryable or attempt >= _config.max_retries:
                return _RequestResult(status, body, retryable, False)
        return _RequestResult(0, None, False, False)


def _json_body(response: Any) -> dict[str, Any] | None:
    if response.status_code == 204:
        return None
    try:
        body = response.json()
    except (ValueError, json.JSONDecodeError):
        return None
    return body if isinstance(body, dict) else None


def _capture_backend_replay_counts(environment: Any) -> dict[str, int]:
    """Read process-local telemetry once after a run; not a run-isolated count."""
    host = getattr(environment, "host", None)
    if not host:
        return {}
    try:
        with urlopen(host.rstrip("/") + "/api/v1/metrics", timeout=2) as response:
            metrics = json.load(response)
    except (OSError, URLError, ValueError):
        return {}
    return {
        str(population.get("attribution") or "none"): int(population["count"])
        for population in metrics.get("populations", [])
        if population.get("population") == "replay"
    }


def snapshot_counters() -> dict[str, Any] | None:
    """Return a timestamped copy of run counters for controller phase boundaries."""
    if _counters is None:
        return None
    return _counters.as_dict(finished_at=datetime.now(timezone.utc))


@events.test_stop.add_listener
def include_backend_replay_population(environment: Any, **_: Any) -> None:
    """Emit replay telemetry separately; it is process-window scoped, not run scoped."""
    if _counters is None:
        return
    _counters.incomplete_opportunities = max(
        0, _counters.opportunities_started - _counters.opportunities_completed
    )
    replay_populations = _capture_backend_replay_counts(environment)
    print(
        json.dumps(
            {
                "type": "adflow_backend_replay_population",
                "scope": "process_local_rolling_window_not_run_isolated",
                "count_by_attribution": replay_populations,
            },
            sort_keys=True,
        ),
        flush=True,
    )

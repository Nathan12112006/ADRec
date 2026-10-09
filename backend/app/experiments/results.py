"""Cohort-aligned descriptive results from durable experiment records."""

from collections.abc import Callable
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import case, distinct, func, select, text
from sqlalchemy.orm import Session

from app.core.clock import utc_now
from app.core.errors import WorkflowError
from app.models.records import Event, Experiment, Recommendation, RequestOutcome

METRICS = (
    "attempts",
    "attempted_users",
    "no_ad_outcomes",
    "recommendations",
    "exposed_users",
    "impressions",
    "clicks",
    "simulated_revenue",
    "ctr",
    "revenue_per_exposed_user",
)


def _ratio(numerator: int | Decimal, denominator: int) -> Decimal | None:
    return Decimal(numerator) / Decimal(denominator) if denominator else None


def _comparison(control: dict[str, Any], treatment: dict[str, Any]) -> dict[str, dict[str, Any]]:
    comparison: dict[str, dict[str, Any]] = {}
    for name in METRICS:
        left, right = control[name], treatment[name]
        difference = right - left if left is not None and right is not None else None
        relative_lift = (
            Decimal(difference) / Decimal(left) * Decimal(100)
            if difference is not None and left not in (None, 0)
            else None
        )
        comparison[name] = {
            "control": left,
            "treatment": right,
            "absolute_difference": difference,
            "relative_lift_percent": relative_lift,
        }
    return comparison


def experiment_results(
    session: Session,
    experiment_id: UUID,
    *,
    start_at: datetime | None = None,
    end_at: datetime | None = None,
    as_of: datetime | None = None,
    clock: Callable[[], datetime] = utc_now,
    telemetry: dict[str, Any] | None = None,
) -> dict[str, Any]:
    as_of = as_of or clock()
    with session.begin():
        session.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ"))
        experiment = session.get(Experiment, experiment_id)
        if experiment is None:
            raise WorkflowError(404, "experiment_not_found", "Experiment was not found")
        effective_start = start_at or experiment.started_at or experiment.created_at
        requested_end = end_at or as_of
        effective_end = min(requested_end, as_of)
        if (
            effective_start.tzinfo is None
            or effective_end.tzinfo is None
            or effective_start >= effective_end
        ):
            raise WorkflowError(
                422, "invalid_cohort_window", "Cohort window must be an increasing UTC interval"
            )

        cohort_filter = (
            Recommendation.experiment_id == experiment_id,
            Recommendation.created_at >= effective_start,
            Recommendation.created_at < effective_end,
        )
        request_filter = (
            RequestOutcome.experiment_id == experiment_id,
            RequestOutcome.created_at >= effective_start,
            RequestOutcome.created_at < effective_end,
        )
        attempts_rows = session.execute(
            select(
                RequestOutcome.experiment_variant,
                func.count().label("attempts"),
                func.count(distinct(RequestOutcome.user_id)).label("attempted_users"),
                func.count(case((RequestOutcome.recommendation_id.is_(None), 1))).label(
                    "no_ad_outcomes"
                ),
            )
            .where(*request_filter)
            .group_by(RequestOutcome.experiment_variant)
        ).mappings()
        attempts = {row["experiment_variant"]: row for row in attempts_rows}

        rec_rows = session.execute(
            select(
                Recommendation.experiment_variant,
                func.count(distinct(Recommendation.id)).label("recommendations"),
                func.count(
                    distinct(
                        case(
                            (Event.event_type == "impression", Recommendation.user_id),
                            else_=None,
                        )
                    )
                ).label("exposed_users"),
                func.count(case((Event.event_type == "impression", 1))).label("impressions"),
                func.count(case((Event.event_type == "click", 1))).label("clicks"),
                func.coalesce(
                    func.sum(case((Event.event_type == "click", Event.simulated_revenue), else_=0)),
                    Decimal(0),
                ).label("simulated_revenue"),
            )
            .outerjoin(
                Event,
                (Event.recommendation_id == Recommendation.id) & (Event.created_at <= as_of),
            )
            .where(*cohort_filter)
            .group_by(Recommendation.experiment_variant)
        ).mappings()
        recommendations = {row["experiment_variant"]: row for row in rec_rows}

        fallback_rows = session.execute(
            select(Recommendation.experiment_variant, Recommendation.selected_ad).where(
                *cohort_filter
            )
        ).mappings()
        fallback_breakdown: dict[str, list[dict[str, Any]]] = {"control": [], "treatment": []}
        fallback_counts: dict[tuple[str, str], int] = {}
        for row in fallback_rows:
            retrieval = row["selected_ad"].get("retrieval") or {}
            if retrieval.get("mode") == "exact_fallback":
                variant = row["experiment_variant"]
                reason = retrieval.get("fallback_reason") or "unspecified"
                fallback_counts[(variant, reason)] = fallback_counts.get((variant, reason), 0) + 1
        for (variant, reason), count in sorted(fallback_counts.items()):
            fallback_breakdown[variant].append(
                {"mode": "exact_fallback", "reason": reason, "count": count}
            )

        variants: dict[str, dict[str, Any]] = {}
        for variant in ("control", "treatment"):
            attempt = attempts.get(variant)
            rec = recommendations.get(variant)
            values: dict[str, Any] = {
                "attempts": int(attempt["attempts"]) if attempt else 0,
                "attempted_users": int(attempt["attempted_users"]) if attempt else 0,
                "no_ad_outcomes": int(attempt["no_ad_outcomes"]) if attempt else 0,
                "recommendations": int(rec["recommendations"]) if rec else 0,
                "exposed_users": int(rec["exposed_users"]) if rec else 0,
                "impressions": int(rec["impressions"]) if rec else 0,
                "clicks": int(rec["clicks"]) if rec else 0,
                "simulated_revenue": rec["simulated_revenue"] if rec else Decimal(0),
                "fallbacks": fallback_breakdown[variant],
            }
            values["ctr"] = _ratio(values["clicks"], values["impressions"])
            values["revenue_per_exposed_user"] = _ratio(
                values["simulated_revenue"], values["exposed_users"]
            )
            variants[variant] = values

        latest = session.scalar(select(func.max(Recommendation.created_at)).where(*cohort_filter))
        provisional = experiment.status == "running" or (
            latest is not None and latest + timedelta(hours=24) > as_of
        )

    telemetry_snapshot = telemetry or {
        "window_start": None,
        "window_end": None,
        "covered_from": None,
        "process_started_at": None,
        "coverage_complete": False,
        "dropped_in_window": None,
        "populations": [],
    }
    relevant = [
        item
        for item in telemetry_snapshot.get("populations", [])
        if item.get("experiment_id") == str(experiment_id)
    ]
    latency = [
        item
        for item in relevant
        if item.get("population") in {"selection", "no_ad", "replay", "error"}
    ]
    unknown_errors = [
        item
        for item in telemetry_snapshot.get("populations", [])
        if item.get("population") == "error" and item.get("attribution") == "unknown"
    ]
    return {
        "experiment_id": str(experiment_id),
        "experiment_status": experiment.status,
        "synthetic": True,
        "statistical_test": None,
        "cohort_start": effective_start,
        "cohort_end_exclusive": effective_end,
        "as_of": as_of,
        "provisional": provisional,
        "event_window_hours": 24,
        "event_windows_closed_through": as_of - timedelta(hours=24),
        "variants": variants,
        "comparison": _comparison(variants["control"], variants["treatment"]),
        "latency_populations": latency,
        "telemetry": {
            "window_start": telemetry_snapshot.get("window_start"),
            "window_end": telemetry_snapshot.get("window_end"),
            "covered_from": telemetry_snapshot.get("covered_from"),
            "process_started_at": telemetry_snapshot.get("process_started_at"),
            "coverage_complete": telemetry_snapshot.get("coverage_complete", False),
            "dropped_in_window": telemetry_snapshot.get("dropped_in_window"),
            "unknown_attribution_errors": unknown_errors,
        },
    }

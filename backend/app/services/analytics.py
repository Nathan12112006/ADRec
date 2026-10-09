"""Repeatable-read live aggregates and dashboard performance summaries."""

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import case, distinct, func, select, text
from sqlalchemy.orm import Session

from app.cache.profiles import RedisProfileCache
from app.ctr.serving import CTRModel
from app.models.records import Ad, Advertiser, Dataset, Event, Recommendation, RequestOutcome, User
from app.retrieval.snapshots import ActiveSnapshot
from app.schemas.analytics import (
    AnalyticsOverviewResponse,
    CacheMetricsResponse,
    MetricsResponse,
    RuntimeCapabilities,
)


def analytics_overview(session: Session, *, as_of: datetime) -> AnalyticsOverviewResponse:
    """Summarize the newest dataset and its durable live records in one DB snapshot."""
    with session.begin():
        session.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ"))
        dataset = session.scalar(
            select(Dataset).order_by(Dataset.created_at.desc(), Dataset.id.desc()).limit(1)
        )
        if dataset is None:
            return AnalyticsOverviewResponse(
                dataset_id=None,
                dataset_created_at=None,
                as_of=as_of,
                availability="empty",
                window_start=None,
                window_end=as_of,
                coverage="empty_dataset",
                provisional=False,
                event_windows_closed_through=as_of,
                users=0,
                advertisers=0,
                active_advertisers=0,
                ads=0,
                active_ads=0,
                recommendations=0,
                request_outcomes=0,
                no_ad_outcomes=0,
                exposed_users=0,
                impressions=0,
                clicks=0,
                observed_ctr=None,
                simulated_revenue=Decimal(0),
            )

        dataset_id = dataset.id
        users = int(
            session.scalar(
                select(func.count()).select_from(User).where(User.dataset_id == dataset_id)
            )
            or 0
        )
        advertisers = session.execute(
            select(
                func.count(Advertiser.id),
                func.count(case((Advertiser.active.is_(True), 1))),
            ).where(Advertiser.dataset_id == dataset_id)
        ).one()
        ads = session.execute(
            select(func.count(Ad.id), func.count(case((Ad.active.is_(True), 1)))).where(
                Ad.dataset_id == dataset_id
            )
        ).one()
        recommendations = int(
            session.scalar(
                select(func.count())
                .select_from(Recommendation)
                .where(Recommendation.dataset_id == dataset_id)
            )
            or 0
        )
        latest_recommendation = session.scalar(
            select(func.max(Recommendation.created_at)).where(
                Recommendation.dataset_id == dataset_id
            )
        )
        outcomes = session.execute(
            select(
                func.count(RequestOutcome.request_key),
                func.count(case((RequestOutcome.recommendation_id.is_(None), 1))),
            )
            .join(User, User.id == RequestOutcome.user_id)
            .where(User.dataset_id == dataset_id)
        ).one()
        event_rows = session.execute(
            select(
                Event.event_type,
                func.count(Event.recommendation_id),
                func.count(
                    distinct(
                        case(
                            (Event.event_type == "impression", Recommendation.user_id),
                            else_=None,
                        )
                    )
                ),
                func.coalesce(func.sum(Event.simulated_revenue), Decimal(0)),
            )
            .join(Recommendation, Recommendation.id == Event.recommendation_id)
            .where(Recommendation.dataset_id == dataset_id, Event.created_at <= as_of)
            .group_by(Event.event_type)
        )
        events = {
            kind: (int(count), int(exposed), revenue)
            for kind, count, exposed, revenue in event_rows
        }
        impressions, exposed_users, _ = events.get("impression", (0, 0, Decimal(0)))
        clicks, _, click_revenue = events.get("click", (0, 0, Decimal(0)))

    return AnalyticsOverviewResponse(
        dataset_id=dataset_id,
        dataset_created_at=dataset.created_at,
        as_of=as_of,
        availability="available",
        window_start=dataset.created_at,
        window_end=as_of,
        coverage="durable_postgresql_snapshot",
        provisional=(
            latest_recommendation is not None
            and latest_recommendation + timedelta(hours=24) > as_of
        ),
        event_windows_closed_through=as_of - timedelta(hours=24),
        users=users,
        advertisers=int(advertisers[0]),
        active_advertisers=int(advertisers[1]),
        ads=int(ads[0]),
        active_ads=int(ads[1]),
        recommendations=recommendations,
        request_outcomes=int(outcomes[0]),
        no_ad_outcomes=int(outcomes[1]),
        exposed_users=exposed_users,
        impressions=impressions,
        clicks=clicks,
        observed_ctr=Decimal(clicks) / Decimal(impressions) if impressions else None,
        simulated_revenue=click_revenue,
    )


def runtime_capabilities(snapshots: ActiveSnapshot, model: CTRModel) -> RuntimeCapabilities:
    state = snapshots.status()
    snapshot = state.snapshot
    retrieval = (
        "hnsw"
        if snapshot is not None and snapshot.manifest.hnsw is not None
        else "flat"
        if snapshot is not None
        else "exact_fallback"
    )
    return RuntimeCapabilities(
        retrieval=retrieval,
        retrieval_failure=state.failure_reason,
        ranking_v1=True,
        ranking_v2=model.model_id is not None,
        ctr_model_id=model.model_id,
    )


def metrics_summary(
    *,
    as_of: datetime,
    telemetry: dict[str, Any],
    profile_cache: RedisProfileCache,
    snapshots: ActiveSnapshot,
    model: CTRModel,
) -> MetricsResponse:
    """Return telemetry scope, cache lifetime counters and current capabilities."""
    return MetricsResponse(
        as_of=as_of,
        window_start=telemetry["window_start"],
        window_end=telemetry["window_end"],
        covered_from=telemetry["covered_from"],
        process_started_at=telemetry["process_started_at"],
        retention_seconds=telemetry["retention_seconds"],
        coverage_complete=telemetry["coverage_complete"],
        dropped_in_window=telemetry["dropped_in_window"],
        sample_count=telemetry["sample_count"],
        retained_bytes=telemetry["retained_bytes"],
        max_records=telemetry["max_records"],
        max_bytes=telemetry["max_bytes"],
        populations=telemetry["populations"],
        cache=CacheMetricsResponse.model_validate(profile_cache.metrics.snapshot()),
        cache_health=profile_cache.health(),
        capabilities=runtime_capabilities(snapshots, model),
    )

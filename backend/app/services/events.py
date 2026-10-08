"""Client-confirmed events and atomic simulated revenue accounting."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Literal
from uuid import UUID

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.clock import utc_now
from app.core.errors import WorkflowError
from app.models.records import Event, Recommendation

EventType = Literal["impression", "click"]


@dataclass(frozen=True)
class EventResult:
    recommendation_id: UUID
    event_type: EventType
    user_id: int
    ad_id: int
    created_at: datetime
    simulated_revenue: Decimal


def _record_event(
    session: Session,
    recommendation_id: UUID,
    event_type: EventType,
    *,
    clock: Callable[[], datetime] = utc_now,
) -> EventResult:
    """Accept a client acknowledgement; commit before reporting success."""
    received_at = clock()
    with session.begin():
        recommendation = session.get(Recommendation, recommendation_id)
        if recommendation is None:
            raise WorkflowError(404, "unknown_recommendation", "Recommendation was not found")
        event = session.get(Event, (recommendation_id, event_type))
        if event is None:
            if received_at >= recommendation.created_at + timedelta(hours=24):
                raise WorkflowError(410, "recommendation_expired", "Recommendation has expired")
            if (
                event_type == "click"
                and session.get(Event, (recommendation_id, "impression")) is None
            ):
                raise WorkflowError(
                    409, "impression_required", "Confirm the impression before retrying the click"
                )
            statement = (
                insert(Event)
                .values(
                    recommendation_id=recommendation_id,
                    event_type=event_type,
                    created_at=received_at,
                    simulated_revenue=recommendation.bid if event_type == "click" else Decimal("0"),
                )
                .on_conflict_do_nothing(index_elements=[Event.recommendation_id, Event.event_type])
            )
            session.execute(statement)
            # READ COMMITTED sees the committed winner after a conflicting insert waits.
            event = session.get(Event, (recommendation_id, event_type))
            assert event is not None
        result = EventResult(
            recommendation_id,
            event_type,
            recommendation.user_id,
            recommendation.ad_id,
            event.created_at,
            event.simulated_revenue,
        )
    return result


def record_event(
    session: Session,
    recommendation_id: UUID,
    event_type: EventType,
    *,
    clock: Callable[[], datetime] = utc_now,
) -> EventResult:
    """Commit acceptance and revenue together; report storage failure safely."""
    try:
        return _record_event(session, recommendation_id, event_type, clock=clock)
    except SQLAlchemyError:
        raise WorkflowError(503, "event_unavailable", "Event storage is unavailable") from None

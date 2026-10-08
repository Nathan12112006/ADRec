"""Read current eligible inventory; callers own transactions and revalidation."""

from collections.abc import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.records import Ad, Advertiser
from app.ranking import BaselineCandidate, select_baseline


def select_baseline_ad(session: Session, user_interests: Iterable[str]) -> BaselineCandidate | None:
    """Stream eligible ads into the pure selector without persisting an outcome."""
    statement = (
        select(Ad.id, Ad.interests, Ad.bid)
        .join(Advertiser, Ad.advertiser_id == Advertiser.id)
        .where(Ad.active.is_(True), Advertiser.active.is_(True))
        .execution_options(yield_per=1000)
    )
    with session.execute(statement) as rows:
        return select_baseline(
            user_interests,
            (BaselineCandidate(row.id, tuple(row.interests), row.bid) for row in rows),
        )

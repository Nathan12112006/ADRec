"""Application-controlled synthetic-user profile edits for internal maintenance tools."""

from sqlalchemy import select

from app.cache.profiles import CachedUserProfile, RedisProfileCache
from app.core.errors import WorkflowError
from app.db.session import Database
from app.models.records import User


def update_user_profile(
    database: Database,
    profile_cache: RedisProfileCache,
    profile: CachedUserProfile,
) -> CachedUserProfile:
    """Commit a profile update, then best-effort invalidate its dataset-scoped cache key.

    This service is for controlled internal tooling; no public profile-edit route is exposed.
    """
    with database.transaction() as session:
        user = session.scalar(
            select(User)
            .where(User.id == profile.user_id, User.dataset_id == profile.dataset_id)
            .with_for_update()
        )
        if user is None:
            raise WorkflowError(404, "unknown_user", "Synthetic user was not found")
        user.interests = list(profile.interests)
        user.category_preferences = list(profile.category_preferences)
        user.age_group = profile.age_group
        user.country = profile.country
        user.device = profile.device
        session.flush()
    profile_cache.invalidate(profile.dataset_id, profile.user_id)
    return profile

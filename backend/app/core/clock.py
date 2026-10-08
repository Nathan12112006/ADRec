"""Server UTC time shared by recommendation and event workflows."""

from datetime import datetime, timezone


def utc_now() -> datetime:
    return datetime.now(timezone.utc)

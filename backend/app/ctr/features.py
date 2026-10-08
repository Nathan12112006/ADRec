"""Allowlisted raw features shared by historical and serving contexts."""

from collections.abc import Mapping
from typing import Any, TypedDict

FEATURE_VERSION = "ctr-features-v1"
MISSING_CATEGORY = "__missing__"


class Features(TypedDict):
    shared_interest_count: int
    category_match: bool
    ad_category: str
    device_type: str
    age_group: str


def build_features(user: Mapping[str, Any], ad: Mapping[str, Any]) -> Features:
    shared = set(user.get("interests") or ()) & set(ad.get("interests") or ())
    return {
        "shared_interest_count": len(shared),
        "category_match": ad.get("category") in set(user.get("interests") or ()),
        "ad_category": ad.get("category") or MISSING_CATEGORY,
        "device_type": user.get("device") or MISSING_CATEGORY,
        "age_group": user.get("age_group") or MISSING_CATEGORY,
    }

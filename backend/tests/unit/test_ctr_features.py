from app.ctr.features import MISSING_CATEGORY, build_features


def test_features_count_distinct_interests_and_match_category() -> None:
    assert build_features(
        {"interests": ["music", "music", "sport"], "device": "mobile", "age_group": "25-34"},
        {"interests": ["music", "music"], "category": "sport", "bid": "999", "clicked": 1},
    ) == {
        "shared_interest_count": 1,
        "category_match": True,
        "ad_category": "sport",
        "device_type": "mobile",
        "age_group": "25-34",
    }


def test_empty_interests_missing_and_unseen_categoricals_keep_raw_feature_shape() -> None:
    assert build_features({}, {}) == {
        "shared_interest_count": 0,
        "category_match": False,
        "ad_category": MISSING_CATEGORY,
        "device_type": MISSING_CATEGORY,
        "age_group": MISSING_CATEGORY,
    }
    features = build_features(
        {"interests": [], "device": "future-device", "age_group": None},
        {"category": "future-category", "interests": ["music"]},
    )
    assert features["device_type"] == "future-device"
    assert features["ad_category"] == "future-category"
    assert features["shared_interest_count"] == 0
    assert features["category_match"] is False

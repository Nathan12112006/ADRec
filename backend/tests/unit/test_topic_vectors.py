import pytest

from app.core.topics import TOPICS
from app.retrieval.vectors import TopicVector, ad_vector, user_vector


def test_user_membership_is_normalized_in_the_versioned_topic_order() -> None:
    vector = user_vector(["gaming", "technology", "gaming"])
    assert vector is not None
    assert vector.values == pytest.approx((0.7071067812, 0.7071067812) + (0.0,) * 11)
    assert vector.vocabulary_version == "topics-v1"
    assert vector.vector_version == "binary-cosine-v1"


def test_ad_category_is_union_membership_without_extra_weight() -> None:
    user = user_vector(["technology"])
    ad = ad_vector(["technology", "gaming", "gaming"], category="gaming")
    assert user is not None
    assert ad.values == pytest.approx((0.7071067812, 0.7071067812) + (0.0,) * 11)
    assert user.similarity(ad) == pytest.approx(0.7071067812)


@pytest.mark.parametrize(
    "values",
    [
        (1.0,),
        (0.0,) * 13,
        (2.0,) + (0.0,) * 12,
        (-1.0,) + (0.0,) * 12,
        (float("nan"),) + (0.0,) * 12,
        (float("inf"),) + (0.0,) * 12,
        (0.6, 0.8) + (0.0,) * 11,
    ],
)
def test_loaded_vectors_reject_invalid_dimensions_values_or_membership(
    values: tuple[float, ...],
) -> None:
    with pytest.raises(ValueError):
        TopicVector(values=values)


@pytest.mark.parametrize("topics", [tuple(reversed(TOPICS)), TOPICS[:-1], TOPICS + ("random",)])
def test_loaded_vectors_reject_reordered_or_changed_vocabulary(topics: tuple[str, ...]) -> None:
    with pytest.raises(ValueError, match="vocabulary"):
        TopicVector(values=(1.0,) + (0.0,) * 12, topics=topics)


@pytest.mark.parametrize("interests", [["unknown"], ["technology", "unknown"], [""]])
def test_unknown_user_topics_are_errors_not_ignored_membership(interests: list[str]) -> None:
    with pytest.raises(ValueError, match="unknown topic"):
        user_vector(interests)


def test_empty_interest_user_has_no_cosine_query() -> None:
    assert user_vector([]) is None


@pytest.mark.parametrize("category", ["", "unknown"])
def test_invalid_ad_category_cannot_be_a_cosine_match(category: str) -> None:
    with pytest.raises(ValueError):
        ad_vector([], category=category)


def test_category_only_ad_is_valid_and_disjoint_topics_have_zero_similarity() -> None:
    ad = ad_vector([], category="technology")
    user = user_vector(["gaming"])
    assert user is not None
    assert user.similarity(ad) == 0
    assert ad.similarity(ad) == 1


@pytest.mark.parametrize("field", ["vocabulary_version", "vector_version"])
def test_loaded_vectors_reject_unknown_versions(field: str) -> None:
    with pytest.raises(ValueError):
        TopicVector.model_validate({"values": (1.0,) + (0.0,) * 12, field: "future-version"})


def test_float32_normalized_membership_can_be_loaded() -> None:
    vector = TopicVector(values=(0.7071067690849304, 0.7071067690849304) + (0.0,) * 11)
    assert vector.similarity(vector) == pytest.approx(1, abs=1e-6)


def test_identical_three_topic_vectors_have_a_valid_unit_cosine_score() -> None:
    vector = user_vector(["technology", "gaming", "fitness"])
    assert vector is not None
    assert vector.similarity(vector) == 1

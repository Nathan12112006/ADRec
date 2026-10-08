import pytest

from app.history.outcomes import OutcomeAd, OutcomeConfig, OutcomeGenerator, OutcomeUser


def test_neutral_context_has_known_probability_and_relevance_increases_tendency() -> None:
    generator = OutcomeGenerator(OutcomeConfig(intercept=0, hidden_scale=0), seed=18)
    user = OutcomeUser(id=1, interests=(), category_preferences=(), device="desktop")
    ad = OutcomeAd(id=2, category="technology", interests=("technology",))
    assert generator.probability(user, ad) == pytest.approx(0.5)
    relevant = user.model_copy(
        update={"interests": ("technology",), "category_preferences": ("technology",)}
    )
    assert 0.5 < generator.probability(relevant, ad) < 1


def test_click_draws_are_repeatable_per_opportunity_and_remain_probabilistic() -> None:
    generator = OutcomeGenerator(OutcomeConfig(intercept=0, hidden_scale=0), seed=18)
    user = OutcomeUser(id=1, interests=(), category_preferences=(), device="desktop")
    ad = OutcomeAd(id=2, category="technology", interests=())
    outcomes = [generator.sample(user, ad, opportunity=str(i)) for i in range(200)]
    assert set(outcomes) == {0, 1}
    assert outcomes == [generator.sample(user, ad, opportunity=str(i)) for i in range(200)]
    assert [
        generator.sample(user, ad, opportunity=str(i)) for i in reversed(range(200))
    ] == outcomes[::-1]


def test_device_signal_and_small_repeatable_hidden_preferences() -> None:
    user = OutcomeUser(id=1, interests=(), category_preferences=(), device="desktop")
    ad = OutcomeAd(id=2, category="technology", interests=())
    fixed = OutcomeGenerator(OutcomeConfig(intercept=0, hidden_scale=0), seed=18)
    assert fixed.probability(user.model_copy(update={"device": "mobile"}), ad) > 0.5
    assert fixed.probability(user.model_copy(update={"device": "tablet"}), ad) < 0.5
    hidden = OutcomeGenerator(OutcomeConfig(intercept=0), seed=18)
    probability = hidden.probability(user, ad)
    assert 0.425 < probability < 0.575
    assert probability == OutcomeGenerator(OutcomeConfig(intercept=0), seed=18).probability(
        user, ad
    )

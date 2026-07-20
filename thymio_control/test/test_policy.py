import pytest

from thymio_control.policies.ei import EiPolicy
from thymio_control.policies.tbr import TbrPolicy
from thymio_control.policies.alpha import AlphaPolicy


def test_focus_policy_clips_speed_and_steer_bounds():
    # Use separate instances — EMA retains state, so reusing one instance
    # would cause the second call to be influenced by the first.
    policy_low = EiPolicy()
    policy_high = EiPolicy()

    low = policy_low.compute_intents({"beta_alpha_theta": -10.0, "alpha_asym": -10.0})
    high = policy_high.compute_intents({"beta_alpha_theta": 10.0, "alpha_asym": 10.0})

    assert low["speed_intent"] == pytest.approx(0.0)
    assert high["speed_intent"] == pytest.approx(1.0)
    # steer is active in all three policies (Ei, Tbr, Alpha)
    assert 0.0 <= low["steer_intent"] <= 1.0
    assert 0.0 <= high["steer_intent"] <= 1.0


def test_focus_policy_steer_direction_matches_alpha_asym_sign():
    policy = EiPolicy()

    left_bias = policy.compute_intents({"beta_alpha_theta": 0.5, "alpha_asym": -0.1})
    right_bias = policy.compute_intents({"beta_alpha_theta": 0.5, "alpha_asym": 0.1})

    assert left_bias["steer_intent"] < 0.5
    assert right_bias["steer_intent"] > 0.5


def test_theta_beta_policy_ratio_controls_speed_inversely():
    policy = TbrPolicy()

    low_ratio = policy.compute_intents({"theta_beta": 0.5, "alpha_asym": 0.0})
    high_ratio = policy.compute_intents({"theta_beta": 2.5, "alpha_asym": 0.0})

    assert low_ratio["speed_intent"] > high_ratio["speed_intent"]
    assert 0.0 <= low_ratio["speed_intent"] <= 1.0
    assert 0.0 <= high_ratio["speed_intent"] <= 1.0


def test_theta_beta_policy_steer_responds_to_asymmetry():
    """TbrPolicy steer_intent follows alpha_asym (same mapping as EiPolicy)."""
    policy = TbrPolicy()

    left_bias = policy.compute_intents({"theta_beta": 1.0, "alpha_asym": -0.1})
    right_bias = policy.compute_intents({"theta_beta": 1.0, "alpha_asym": 0.1})

    assert left_bias["steer_intent"] < 0.5
    assert right_bias["steer_intent"] > 0.5


def test_alpha_only_policy_clips_bounds():
    policy = AlphaPolicy()

    low = policy.compute_intents({"alpha": -10.0})
    high = policy.compute_intents({"alpha": 100.0})

    assert low["speed_intent"] == pytest.approx(1.0)
    assert low["steer_intent"] == pytest.approx(0.5)
    assert high["speed_intent"] == pytest.approx(0.0)
    assert high["steer_intent"] == pytest.approx(0.5)


def test_alpha_only_policy_speed_inversely_proportional():
    policy = AlphaPolicy()

    low_alpha = policy.compute_intents({"alpha": 0.5})
    high_alpha = policy.compute_intents({"alpha": 7.0})

    assert low_alpha["speed_intent"] > high_alpha["speed_intent"]
    assert 0.0 <= low_alpha["speed_intent"] <= 1.0
    assert 0.0 <= high_alpha["speed_intent"] <= 1.0


def test_alpha_only_policy_steer_responds_to_asymmetry():
    """AlphaPolicy steer_intent follows alpha_asym (same mapping as EiPolicy)."""
    policy = AlphaPolicy()

    left_bias = policy.compute_intents({"alpha": 3.0, "alpha_asym": -0.1})
    right_bias = policy.compute_intents({"alpha": 3.0, "alpha_asym": 0.1})

    assert left_bias["steer_intent"] < 0.5
    assert right_bias["steer_intent"] > 0.5

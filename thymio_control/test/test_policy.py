import pytest

from thymio_control.eeg_control_pipeline import EiPolicy, TbrPolicy, AlphaPolicy


def test_focus_policy_clips_speed_and_steer_bounds():
    # Use separate instances — EMA retains state, so reusing one instance
    # would cause the second call to be influenced by the first.
    policy_low = EiPolicy()
    policy_high = EiPolicy()

    low = policy_low.compute_intents({"beta_alpha_theta": -10.0, "alpha_asym": -10.0})
    high = policy_high.compute_intents({"beta_alpha_theta": 10.0, "alpha_asym": 10.0})

    assert low["speed_intent"] == pytest.approx(0.0)
    assert high["speed_intent"] == pytest.approx(1.0)
    # steer is still steerable in EiPolicy (only TbrPolicy disables it)
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


def test_theta_beta_policy_steer_is_disabled():
    """TbrPolicy disables steering — steer_intent is always 0.5."""
    policy = TbrPolicy()

    for asym in (-100.0, -0.5, 0.0, 0.5, 100.0):
        result = policy.compute_intents({"theta_beta": 1.0, "alpha_asym": asym})
        assert result["steer_intent"] == pytest.approx(0.5), (
            f"Expected steer_intent=0.5 for alpha_asym={asym}, got {result['steer_intent']}"
        )


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


def test_alpha_only_policy_steer_is_disabled():
    policy = AlphaPolicy()

    result = policy.compute_intents({"alpha": 3.0})
    assert result["steer_intent"] == pytest.approx(0.5)

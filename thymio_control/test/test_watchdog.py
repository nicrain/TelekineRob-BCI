"""Unit tests for the pure watchdog decision function (no ROS required)."""

from thymio_control.watchdog import decide_watchdog_action


# --- Single device (stop_on_data_loss=False) — the original contract ---


def test_single_device_grace_window_replays():
    assert decide_watchdog_action(stale=False, connected=True, stop_on_data_loss=False) == "replay"


def test_single_device_grace_window_replays_even_if_flag_stale():
    assert decide_watchdog_action(stale=False, connected=False, stop_on_data_loss=False) == "replay"


def test_single_device_timeout_zeroes_once_then_stops():
    # past the window, first tick (was connected) → one zero
    assert decide_watchdog_action(stale=True, connected=True, stop_on_data_loss=False) == "zero"


def test_single_device_already_halted_stays_silent():
    # past the window, already disconnected → silent (NOT perpetual replay)
    assert decide_watchdog_action(stale=True, connected=False, stop_on_data_loss=False) == "halt"


# --- Dual device (stop_on_data_loss=True) — fully silent, fuser takes over ---


def test_dual_device_always_halt():
    assert decide_watchdog_action(stale=False, connected=True, stop_on_data_loss=True) == "halt"
    assert decide_watchdog_action(stale=True, connected=True, stop_on_data_loss=True) == "halt"
    assert decide_watchdog_action(stale=True, connected=False, stop_on_data_loss=True) == "halt"

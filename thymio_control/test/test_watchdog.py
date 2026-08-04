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


# --- Dual device (stop_on_data_loss=True) — replay during flow, halt on loss ---


def test_dual_device_replays_during_flow_halts_on_true_loss():
    # data still flowing (frame within grace) → keep publishing
    assert decide_watchdog_action(stale=False, connected=True, stop_on_data_loss=True) == "replay"
    # real loss (> watchdog since last frame) → silent, fuser takes over
    assert decide_watchdog_action(stale=True, connected=True, stop_on_data_loss=True) == "halt"
    assert decide_watchdog_action(stale=True, connected=False, stop_on_data_loss=True) == "halt"


def test_dual_mode_normal_flow_publishes_at_tick_rate():
    """N4: inter-frame ticks must replay, keeping the partial at ~20 Hz.

    Frames land every 10 ticks (hop=0.5 s, publish_hz=20). The 9 no-frame
    ticks in between are NOT loss — halting them would drop the partial to
    ~2 Hz, right at the fuser's 0.5 s freshness boundary, causing periodic
    zero-velocity stalling under real LSL jitter.
    """
    watchdog = 0.5
    tick = 0.05          # publish_hz = 20
    last_msg_ts = 0.0
    publishes = 0
    halts = 0

    for i in range(1, 21):   # 1.0 s of ticks at 20 Hz
        now = i * tick
        if i % 10 == 0:      # a new analysis frame lands (every 0.5 s)
            last_msg_ts = now   # last_msg_ts updates on data arrival
            publishes += 1      # the frame branch publishes
            continue
        action = decide_watchdog_action(
            stale=now - last_msg_ts > watchdog,
            connected=True,
            stop_on_data_loss=True,
        )
        if action == "replay":
            publishes += 1
        elif action == "halt":
            halts += 1
        else:
            raise AssertionError(f"unexpected action {action!r} during normal flow")

    assert halts == 0                      # no false "data loss" → no false log
    assert publishes >= 19                 # ~20 Hz continuous partial stream

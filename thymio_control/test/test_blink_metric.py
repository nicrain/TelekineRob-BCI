"""P44③: MetricBlinkDetector — TRANSIENT metric-blink detection.

The old absolute-threshold detector fired on every frame during rest-state
drift (persistently high alpha/tbr, low ei) → a false-blink loop. These tests
pin the transient criterion: a spike/drop vs the recent-baseline median, so a
sustained drift stops triggering and a real 2-frame blink still fires once.
"""
from thymio_control.processors.blink_metric import MetricBlinkDetector


def _primed(mode="up", **kw):
    det = MetricBlinkDetector(mode=mode, min_samples=15, **kw)
    for _ in range(30):
        det.update(1.0 if mode == "up" else 10.0)
    return det


def test_real_blink_confirmed_once():
    """A 2-frame up-spike confirms exactly ONE blink, then holds off."""
    det = _primed("up")                       # baseline ≈ 1
    assert det.update(4.0) is False           # frame 1: counter = 1
    assert det.in_progress is True
    assert det.update(4.0) is True            # frame 2: CONFIRMED
    assert det.in_progress is True            # holdoff active
    for _ in range(4):
        assert det.update(1.0) is False       # ignored during holdoff
    assert det.in_progress is False
    # back to baseline — another real blink still works later
    for _ in range(10):
        det.update(1.0)
    assert det.update(4.0) is False
    assert det.update(4.0) is True


def test_single_frame_spike_rejected():
    """confirm_frames=2 → an isolated artifact frame never confirms."""
    det = _primed("up")
    assert det.update(4.0) is False           # counter = 1
    assert det.update(1.0) is False           # falls back → counter reset
    assert det.in_progress is False
    assert det.update(4.0) is False           # another isolated spike
    assert det.update(1.0) is False
    assert det.update(4.0) is False


def test_fall_back_resets_counter():
    """Never 2 consecutive outside-range frames → never confirmed."""
    det = _primed("up")
    for _ in range(5):
        assert det.update(4.0) is False
        assert det.update(1.0) is False


def test_sustained_high_stops_after_baseline_catches_up():
    """The root cause: persistent rest alpha drift must NOT loop. Once the
    median window fills with the high level, `val > median*2` stops passing."""
    det = _primed("up")
    for _ in range(100):
        det.update(3.0)                       # sustained rest drift
    blinks = 0
    for _ in range(60):
        if det.update(3.0):
            blinks += 1
    assert blinks == 0


def test_ei_drop_detected_and_sustained_low_does_not_loop():
    """EI is inverted — a blink is a DROP below the baseline; a sustained low
    ei (rest drift) fills the median and stops triggering."""
    det = _primed("down")                     # baseline ≈ 10
    assert det.update(3.0) is False           # 3 < 10*0.5
    assert det.update(3.0) is True            # confirmed
    for _ in range(100):
        det.update(0.1)                       # sustained low ei
    blinks = 0
    for _ in range(60):
        if det.update(0.1):
            blinks += 1
    assert blinks == 0


def test_in_progress_flags():
    det = _primed("up")
    assert det.in_progress is False
    det.update(4.0)
    assert det.in_progress is True            # confirm counter accumulating
    det.update(4.0)
    assert det.in_progress is True            # holdoff
    for _ in range(4):
        det.update(1.0)
    assert det.in_progress is False


def test_reset_clears_state():
    det = _primed("up")
    det.update(4.0)
    det.reset()
    assert det.in_progress is False
    assert det.update(1.0) is False           # needs re-priming

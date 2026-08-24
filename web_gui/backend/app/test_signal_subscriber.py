"""Tests for RosBridge multi-topic frame aggregation (no ROS needed:
rclpy import fails gracefully in the daemon thread on this host)."""

import json
import time
from types import SimpleNamespace

from app.signal_subscriber import RosBridge


def _seed(bridge: RosBridge, topic: str, frame: dict, age_s: float = 0.0) -> None:
    with bridge._lock:
        bridge._latest[topic] = frame
        bridge._last_ts[topic] = time.monotonic() - age_s


def test_get_latest_frames_uses_role_field_over_topic_suffix():
    bridge = RosBridge()
    _seed(bridge, "/eeg_analysis/speed", {"role": "steering", "alpha": 0.1})

    frames = bridge.get_latest_frames()

    assert "steering" in frames      # frame's own role wins over the topic suffix
    assert "speed" not in frames
    bridge.stop()


def test_get_latest_frames_falls_back_to_topic_suffix():
    bridge = RosBridge()
    _seed(bridge, "/eeg_analysis/steering", {"alpha": 0.1})  # no role field
    _seed(bridge, "/eeg_analysis/speed", {"alpha": 0.2})

    frames = bridge.get_latest_frames()

    assert frames["steering"]["alpha"] == 0.1
    assert frames["speed"]["alpha"] == 0.2
    bridge.stop()


def test_get_latest_frames_excludes_stale_topics():
    bridge = RosBridge()
    _seed(bridge, "/eeg_analysis/speed", {"alpha": 0.1}, age_s=0.0)
    _seed(bridge, "/eeg_analysis/steering", {"alpha": 0.2}, age_s=1.0)  # > 0.5s

    frames = bridge.get_latest_frames()

    assert "speed" in frames
    assert "steering" not in frames
    bridge.stop()


def test_get_latest_frame_single_device_compat():
    bridge = RosBridge()
    _seed(bridge, "/eeg_analysis", {"role": "speed", "alpha": 0.3})

    frame = bridge.get_latest_frame()

    assert frame is not None
    assert frame["alpha"] == 0.3
    bridge.stop()


def test_get_latest_frame_none_when_only_suffixed_topics_have_data():
    bridge = RosBridge()
    _seed(bridge, "/eeg_analysis/speed", {"role": "speed", "alpha": 0.4})

    assert bridge.get_latest_frame() is None  # bare topic carries no data
    bridge.stop()


def test_on_analysis_preserves_role_from_node_json():
    """M3-1: a single-device steering frame on the bare topic must resolve to
    "steering". This feeds the real M2 analysis JSON through _on_analysis —
    no _seed injection — so the frame-building path that previously dropped
    the role field is exercised."""
    bridge = RosBridge()
    payload = {
        "ts": 123.0,
        "source": "lsl",
        "role": "steering",
        "metrics": {"alpha": 0.1, "theta": 0.2, "beta": 0.3},
        "features": {"theta_beta": 0.7},
        "intents": {"speed_intent": 0.5, "steer_intent": 0.5},
        "steer_direction": 1,
    }
    bridge._on_analysis("/eeg_analysis", SimpleNamespace(data=json.dumps(payload)))

    frames = bridge.get_latest_frames()

    assert "steering" in frames
    assert "speed" not in frames  # role field wins — not the speed backstop
    bridge.stop()

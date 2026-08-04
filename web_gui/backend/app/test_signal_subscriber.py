"""Tests for RosBridge multi-topic frame aggregation (no ROS needed:
rclpy import fails gracefully in the daemon thread on this host)."""

import time

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

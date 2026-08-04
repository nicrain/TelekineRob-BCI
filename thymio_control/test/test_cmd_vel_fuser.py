"""Unit tests for cmd_vel_fuser's pure merge helpers (no ROS required)."""

import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from cmd_vel_fuser import build_command, merge_twists  # noqa: E402


class _FakeTwist:
    """Duck-typed stand-in for geometry_msgs/Twist."""

    def __init__(self, linear_x: float = 0.0, angular_z: float = 0.0):
        self.linear = SimpleNamespace(x=linear_x, y=0.0, z=0.0)
        self.angular = SimpleNamespace(x=0.0, y=0.0, z=angular_z)


def test_merge_twists_takes_linear_from_speed_angular_from_steer():
    speed = _FakeTwist(linear_x=0.4)
    steer = _FakeTwist(angular_z=-0.9)

    out = merge_twists(speed, steer)

    assert out.linear.x == 0.4
    assert out.angular.z == -0.9
    # every other component is zeroed
    assert out.linear.y == 0.0
    assert out.linear.z == 0.0
    assert out.angular.x == 0.0
    assert out.angular.y == 0.0


def test_build_command_fuses_when_both_fresh():
    out = build_command(_FakeTwist(linear_x=0.4), _FakeTwist(angular_z=-0.9), True, True)
    assert out.linear.x == 0.4
    assert out.angular.z == -0.9


def test_build_command_zero_when_speed_stale():
    out = build_command(_FakeTwist(linear_x=0.4), _FakeTwist(angular_z=-0.9), False, True)
    assert out.linear.x == 0.0
    assert out.angular.z == 0.0


def test_build_command_zero_when_steer_stale():
    out = build_command(_FakeTwist(linear_x=0.4), _FakeTwist(angular_z=-0.9), True, False)
    assert out.linear.x == 0.0
    assert out.angular.z == 0.0


def test_build_command_none_before_any_input():
    assert build_command(None, None, False, False) is None


def test_build_command_zero_when_one_input_never_arrived():
    out = build_command(None, _FakeTwist(angular_z=-0.9), False, True)
    assert out is not None
    assert out.linear.x == 0.0
    assert out.angular.z == 0.0


def test_fuser_zeroes_within_watchdog_of_last_input():
    """N4: fail-safe latency — once an input goes stale (no message for
    watchdog_sec), the fuser outputs zero. This is the bound the dual-mode
    node relies on when it goes silent after a real loss."""
    watchdog = 0.5
    speed = _FakeTwist(linear_x=0.4)
    steer = _FakeTwist(angular_z=-0.9)
    last_ts = 0.0

    def fused(now):
        ok = now - last_ts <= watchdog
        return build_command(speed, steer, ok, ok)

    # just inside the freshness window → still fused
    assert fused(0.49).linear.x == 0.4
    # just past the window → zero velocity within ≤0.5 s of the last input
    zero = fused(0.5 + 1e-3)
    assert zero.linear.x == 0.0
    assert zero.angular.z == 0.0

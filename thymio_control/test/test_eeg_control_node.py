"""P47 (minimal): eeg_control_node constructs WITHOUT ROS — the acd64a5
regression was an __init__ ordering NameError (a param declaration referenced
policy_name before it was read), invisible to py_compile and to the
detector-only tests. Constructing the node under stubbed rclpy + msg modules
catches that whole class of bug, and asserts the blink detector receives the
calibration p50 (= calib_offset + calib_scale) as its baseline floor.
"""
import sys
import types
from pathlib import Path

import pytest

# eeg_control_node.py lives in the top-level thymio_control/scripts/ dir (not a
# submodule of the nested package), so put that dir on sys.path explicitly.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

_OVERRIDES: dict = {}          # param-name → forced value (per test)


class _FakeParam:
    def __init__(self, value):
        self.value = value


class _FakeLogger:
    def info(self, *a, **k): pass
    def warning(self, *a, **k): pass
    def error(self, *a, **k): pass


class _FakeNodeBase:
    def __init__(self, *a, **k):
        self._params = {}

    def declare_parameter(self, name, default=None):
        self._params[name] = _OVERRIDES.get(name, default)

    def get_parameter(self, name):
        return _FakeParam(self._params.get(name, None))

    def set_parameters(self, params):
        return []

    def create_publisher(self, *a, **k):
        return None

    def create_subscription(self, *a, **k):
        return None

    def create_timer(self, *a, **k):
        return None

    def get_logger(self):
        return _FakeLogger()


def _install_ros_stubs():
    """Register the ROS module names eeg_control_node imports at module top."""
    modules = {}

    rclpy = types.ModuleType("rclpy")
    rclpy_node = types.ModuleType("rclpy.node")
    rclpy_node.Node = _FakeNodeBase
    rclpy.parameter = types.ModuleType("rclpy.parameter")
    modules["rclpy"] = rclpy
    modules["rclpy.node"] = rclpy_node
    modules["rclpy.parameter"] = rclpy.parameter

    for modname in ("geometry_msgs", "sensor_msgs", "std_msgs"):
        top = types.ModuleType(modname)
        msg = types.ModuleType(f"{modname}.msg")
        top.msg = msg
        modules[modname] = top
        modules[f"{modname}.msg"] = msg

    # Twist / Range / String must be instantiable classes (node does Twist()).
    modules["geometry_msgs.msg"].Twist = type("Twist", (), {})
    modules["sensor_msgs.msg"].Range = type("Range", (), {})
    modules["std_msgs.msg"].String = type("String", (), {})

    for name, mod in modules.items():
        if name not in sys.modules:
            sys.modules[name] = mod


_install_ros_stubs()

import eeg_control_node  # noqa: E402  (after the stubs are in sys.modules)


@pytest.fixture(autouse=True)
def _reset(monkeypatch):
    _OVERRIDES.clear()
    monkeypatch.setattr(eeg_control_node, "build_adapter", lambda args: _FakeAdapter())
    yield
    _OVERRIDES.clear()


class _FakeAdapter:
    def start(self): pass
    def stop(self): pass


def _make_node(policy: str, offset=1.0, scale=2.0):
    _OVERRIDES.update({
        "policy": policy,
        "calib_offset": offset,
        "calib_scale": scale,
    })
    return eeg_control_node.EegControlNode()


def test_node_constructs_for_every_policy():
    """F1 (regression): no NameError — the P47 wiring reads policy_name first
    and the params are declared after."""
    for policy in ("tbr", "alpha", "ei"):
        node = _make_node(policy)
        assert node.policy is not None
        assert node._blink_detector is not None


def test_node_passes_calibration_p50_as_detector_floor():
    """P47: the blink detector gets clamp_ref = calib_offset + calib_scale
    (the calibration p50) — the minimal wiring, no extra params."""
    node = _make_node("tbr", offset=0.5, scale=1.5)
    assert node._blink_detector._clamp_ref == pytest.approx(2.0)  # p50
    assert node._blink_detector._mode == "up"

    # an ei node still receives p50, but the detector only applies the floor
    # in up mode, so a down detector keeps old behavior (scope: no ei clamp).
    node = _make_node("ei", offset=0.5, scale=1.5)
    assert node._blink_detector._clamp_ref == pytest.approx(2.0)
    assert node._blink_detector._mode == "down"
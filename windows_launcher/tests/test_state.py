"""State machine rules + status payload shape (pure)."""
from state import (
    DEVICE_CONNECTED,
    DEVICE_DISCONNECTED,
    SYSTEM_ERROR,
    SYSTEM_RUNNING,
    SYSTEM_STARTING,
    SYSTEM_STOPPED,
    LauncherState,
    can_connect_device,
    can_start_system,
    can_stop_system,
    status_payload,
)


def _state():
    return LauncherState(["headband", "hybrid", "thymio"])


def test_initial_states():
    s = _state()
    assert s.system == SYSTEM_STOPPED
    assert s.devices == {
        "headband": DEVICE_DISCONNECTED,
        "hybrid": DEVICE_DISCONNECTED,
        "thymio": DEVICE_DISCONNECTED,
    }


def test_can_start_only_from_stopped_or_error():
    s = _state()
    assert can_start_system(s) is True
    s.set_system(SYSTEM_RUNNING)
    assert can_start_system(s) is False
    s.set_system(SYSTEM_STARTING)
    assert can_start_system(s) is False
    s.set_system(SYSTEM_ERROR)
    assert can_start_system(s) is True


def test_can_connect_only_while_system_up():
    s = _state()
    assert can_connect_device(s) is False          # stopped
    s.set_system(SYSTEM_STARTING)
    assert can_connect_device(s) is True
    s.set_system(SYSTEM_RUNNING)
    assert can_connect_device(s) is True
    s.set_system(SYSTEM_ERROR)
    assert can_connect_device(s) is False


def test_can_stop_from_up_states():
    s = _state()
    assert can_stop_system(s) is False             # already stopped
    s.set_system(SYSTEM_RUNNING)
    assert can_stop_system(s) is True


def test_status_payload_shape():
    s = _state()
    s.set_system(SYSTEM_RUNNING, "系统已就绪")
    s.set_device("headband", DEVICE_CONNECTED, "已连接")
    payload = status_payload(s)
    assert payload["system"] == {"state": SYSTEM_RUNNING, "message": "系统已就绪"}
    assert payload["devices"]["headband"] == {"state": DEVICE_CONNECTED, "message": "已连接"}

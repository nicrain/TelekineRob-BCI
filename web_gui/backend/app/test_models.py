import pytest
from pydantic import ValidationError

from app.models import (
    AppConfig,
    DeviceFrame,
    EegConfig2,
    LaunchConfig,
    SystemStatus,
    WsFrame,
)


def test_eeg_config2_calibration_defaults():
    cfg = EegConfig2()
    assert cfg.role == "steering"
    assert cfg.calibrate is False
    assert cfg.calib_offset == 0.0
    assert cfg.calib_scale == 1.0


def test_eeg_config2_accepts_explicit_calibration():
    cfg = EegConfig2(calibrate=True, calib_offset=0.5, calib_scale=2.0)
    assert cfg.calibrate is True
    assert cfg.calib_offset == 0.5
    assert cfg.calib_scale == 2.0


def test_launch_config_run_eeg2_defaults_false():
    assert LaunchConfig().run_eeg2 is False


def test_appconfig_rejects_same_role_dual_device():
    with pytest.raises(ValidationError, match="roles to differ"):
        AppConfig(eeg={"role": "speed"}, eeg2={"role": "speed"})


def test_appconfig_accepts_distinct_roles():
    cfg = AppConfig(eeg={"role": "speed"}, eeg2={"role": "steering"})
    assert cfg.eeg2 is not None
    assert cfg.eeg.role != cfg.eeg2.role


def test_appconfig_default_has_no_eeg2():
    assert AppConfig().eeg2 is None


def test_wsframe_devices_schema():
    frame = WsFrame(
        status=SystemStatus(),
        devices={
            "speed": DeviceFrame(
                channels={"alpha": 0.1},
                features={"focus_index": 1.2},
                control={"speed_intent": 0.6},
                timestamp=1.0,
            ),
            "steering": DeviceFrame(
                channels={}, features={}, control={"steer_intent": 0.5}, timestamp=1.0
            ),
        },
        timestamp=2.0,
    )
    assert frame.devices["speed"].channels["alpha"] == 0.1
    assert frame.devices["steering"].control["steer_intent"] == 0.5
    assert frame.timestamp == 2.0
    assert frame.devices["speed"].timestamp == 1.0

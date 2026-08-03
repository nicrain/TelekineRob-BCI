from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


class LaunchConfig(BaseModel):
    use_sim: bool = True
    use_gui: bool = True
    run_eeg: bool = False
    run_eeg2: bool = False
    run_rviz: bool = False
    device: str = ""


class EegConfig(BaseModel):
    input: str = "lsl"
    role: Literal["speed", "steering"] = "speed"
    policy: Literal["ei", "tbr", "alpha"] = "tbr"
    calibrate: bool = False
    calib_offset: float = 0.0
    calib_scale: float = 1.0
    lsl_stream_type: str = "EEG"
    lsl_timeout: float = 8.0
    lsl_source_id: str = ""


class EegConfig2(BaseModel):
    input: str = "lsl"
    role: Literal["speed", "steering"] = "steering"
    policy: Literal["ei", "tbr", "alpha"] = "tbr"
    calibrate: bool = False
    calib_offset: float = 0.0
    calib_scale: float = 1.0
    lsl_stream_type: str = "EEG"
    lsl_timeout: float = 8.0
    lsl_source_id: str = ""


class MotionConfig(BaseModel):
    max_forward_speed: float = 0.2
    reverse_speed: float = -0.15
    turn_forward_speed: float = 0.1
    turn_angular_speed: float = 1.2
    steer_deadzone: float = 0.1
    line_mode: Literal["", "blackline", "whiteline"] = ""
    line_pivot_gain: float = 8.0
    line_spin_gain: float = 15.0


class AppConfig(BaseModel):
    launch: LaunchConfig = Field(default_factory=LaunchConfig)
    eeg: EegConfig = Field(default_factory=EegConfig)
    eeg2: EegConfig2 | None = None
    motion: MotionConfig = Field(default_factory=MotionConfig)

    @model_validator(mode="after")
    def _dual_roles_must_differ(self) -> AppConfig:
        if self.eeg2 is not None and self.eeg.role == self.eeg2.role:
            raise ValueError("dual-device mode requires eeg and eeg2 roles to differ")
        return self


class ConfigEnvelope(BaseModel):
    config: AppConfig
    source_files: dict[str, str]


class SystemStatus(BaseModel):
    mode: Literal["mock", "real"] = "mock"
    ros_available: bool = False
    thymio_connected: bool = False
    thymio_probe_detail: str = "Unknown"
    eeg_stream_alive: bool = False
    running: bool = False
    last_error: str | None = None


class CommandRequest(BaseModel):
    dry_run: bool = True


class CommandResult(BaseModel):
    accepted: bool
    dry_run: bool
    command: str
    detail: str


class DeviceFrame(BaseModel):
    channels: dict[str, float]
    features: dict[str, float]
    control: dict[str, float]
    timestamp: float


class WsFrame(BaseModel):
    status: SystemStatus
    devices: dict[str, DeviceFrame]
    timestamp: float | None = None


class ConfigPatch(BaseModel):
    patch: dict[str, Any]

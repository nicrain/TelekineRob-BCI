"""Unit tests for the calibration threshold + write-back (no ROS needed)."""

from pathlib import Path

import yaml

from thymio_control.calibration import (
    MIN_CALIB_SAMPLES,
    enough_samples,
    write_calib_result,
)


def test_min_threshold_50():
    assert MIN_CALIB_SAMPLES == 50


def test_enough_samples_50_passes_49_aborts():
    assert enough_samples(50) is True
    assert enough_samples(49) is False
    assert enough_samples(60) is True


def test_write_calib_result_success_writes_offset_scale(tmp_path: Path):
    cfg_file = tmp_path / "eeg_control_node.params.yaml"
    cfg_file.write_text(
        yaml.safe_dump({"/**": {"ros__parameters": {"calibrate": True}}})
    )

    ok = write_calib_result([tmp_path], "eeg_control_node.params.yaml", offset=1.5, scale=2.5)

    assert ok is True
    params = yaml.safe_load(cfg_file.read_text())["/**"]["ros__parameters"]
    assert params["calib_offset"] == 1.5
    assert params["calib_scale"] == 2.5
    assert params["calibrate"] is False


def test_write_calib_result_abort_writes_only_calibrate_false(tmp_path: Path):
    """n < 50 → abort, but calibrate=false is still written so the frontend
    poll un-hangs; offset/scale stay untouched."""
    cfg_file = tmp_path / "eeg_control_node.eeg2.params.yaml"
    cfg_file.write_text(
        yaml.safe_dump(
            {"/**": {"ros__parameters": {"calib_offset": 0.0, "calib_scale": 1.0, "calibrate": True}}}
        )
    )

    ok = write_calib_result([tmp_path], "eeg_control_node.eeg2.params.yaml")

    assert ok is True
    params = yaml.safe_load(cfg_file.read_text())["/**"]["ros__parameters"]
    assert params["calibrate"] is False
    assert params["calib_offset"] == 0.0  # unchanged on abort
    assert params["calib_scale"] == 1.0


def test_write_calib_result_writes_both_roots(tmp_path: Path):
    root_a = tmp_path / "a"
    root_b = tmp_path / "b"
    for root in (root_a, root_b):
        root.mkdir(parents=True)
        (root / "eeg_control_node.params.yaml").write_text(
            yaml.safe_dump({"/**": {"ros__parameters": {"calibrate": True}}})
        )

    ok = write_calib_result([root_a, root_b], "eeg_control_node.params.yaml", offset=0.3, scale=1.2)

    assert ok is True
    for root in (root_a, root_b):
        params = yaml.safe_load((root / "eeg_control_node.params.yaml").read_text())["/**"]["ros__parameters"]
        assert params["calibrate"] is False
        assert params["calib_offset"] == 0.3


def test_write_calib_result_never_raises_on_missing_file(tmp_path: Path):
    ok = write_calib_result([tmp_path], "does_not_exist.yaml", offset=1.0, scale=1.0)
    assert ok is False

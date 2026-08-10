"""Config load + template expansion (pure, no IO beyond reading files)."""
import json
from pathlib import Path

import pytest

from config import expand_config, load_config

REPO_CONFIG = Path(__file__).resolve().parents[1] / "config.json"


def test_load_real_config_has_all_sections():
    cfg = load_config(REPO_CONFIG)
    for section in ("service", "wsl", "sync", "web", "devices", "sidebar"):
        assert section in cfg


def test_template_expansion_resolves_cwd():
    """${sync.dst_root}\\gtec_bridge must expand to the configured root."""
    cfg = load_config(REPO_CONFIG)
    assert cfg["devices"]["headband"]["cwd"] == (
        cfg["sync"]["dst_root"] + "\\gtec_bridge"
    )


def test_backend_cmd_sources_ros2_absolutely():
    """② ${wsl.repo_path} expands to the absolute repo path in the ROS2
    colcon source — the bash -lc context has no ROS2 env otherwise."""
    cfg = load_config(REPO_CONFIG)
    cmd = cfg["web"]["backend_cmd"]
    assert "source /opt/ros/kilted/setup.bash" in cmd
    assert cfg["wsl"]["repo_path"] + "/install/setup.bash" in cmd
    assert "${wsl.repo_path}" not in cmd  # fully expanded


def test_missing_config_file_raises(tmp_path: Path):
    with pytest.raises(ValueError, match="config file not found"):
        load_config(tmp_path / "nope.json")


def test_invalid_json_raises(tmp_path: Path):
    bad = tmp_path / "config.json"
    bad.write_text("{ not json", encoding="utf-8")
    with pytest.raises(ValueError, match="parse failed"):
        load_config(bad)


def test_missing_section_raises(tmp_path: Path):
    bad = tmp_path / "config.json"
    bad.write_text(json.dumps({"service": {"port": 8020}}), encoding="utf-8")
    with pytest.raises(ValueError, match="missing required sections"):
        load_config(bad)


def test_unknown_template_ref_raises():
    with pytest.raises(ValueError, match="references a missing field"):
        expand_config({"a": {"b": "${nope.missing}"}})

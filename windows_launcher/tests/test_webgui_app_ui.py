"""Static regression for web_gui App.jsx UI features.

jsdom/vitest aren't installed and the frontend build is a user-side WSL2
task, so we pin markers in the shipped JSX statically (same pattern as
test_webgui_theme.py): P19 Sans-robot removal, P16 experiment-panel wiring,
P17 log-panel wiring.
"""
from pathlib import Path

APPJSX = Path(__file__).resolve().parents[2] / "web_gui" / "frontend" / "src" / "App.jsx"


def _app() -> str:
    return APPJSX.read_text(encoding="utf-8")


# --- P19: 'Sans robot' output mode removed --------------------------------

def test_no_sans_robot_output_mode():
    """P19: the broken 'Sans robot' (Waveforms only) output option is gone —
    output is only thymio / thymio_simu. role2's 'none' (= no second device)
    is a DIFFERENT thing and must not be touched."""
    src = _app()
    assert "Sans robot" not in src
    assert "Waveforms only" not in src
    # both remaining output modes are still offered
    assert "value: 'thymio'" in src
    assert "value: 'thymio_simu'" in src
    # role2 "None" (no second device) still exists — not the same concept
    assert "value: 'none',     label: 'None'" in src


def test_thymio_device_selector_kept():
    """P19: the real-robot device selector (outputMode === 'thymio') must
    still be wired now that 'none' is gone."""
    src = _app()
    assert "outputMode === 'thymio' ? thymioDevice : ''" in src  # buildPatch device
    assert "outputMode === 'thymio' && (" in src                  # device selector UI


# --- P16/E3: experiment-mode panel ----------------------------------------

def test_experiment_panel_wired_into_app():
    """P16/E3: the experiment panel is imported and rendered by App.jsx (in
    its own component file — the O5 incremental split)."""
    src = _app()
    assert "import ExperimentPanel from './ExperimentPanel';" in src
    assert "<ExperimentPanel />" in src


def test_experiment_panel_markers():
    """P16/E3: the panel polls the experiment state, configures the session,
    drives the trial sequence and shows the target + countdown."""
    panel = (APPJSX.parent / "ExperimentPanel.jsx").read_text(encoding="utf-8")
    for endpoint in (
        "/api/experiment/state",
        "/api/experiment/configure",
        "/api/experiment/protocol",
        "/api/experiment/start",
        "/api/experiment/pause",
        "/api/experiment/resume",
        "/api/experiment/reset",
    ):
        assert endpoint in panel, f"ExperimentPanel lost {endpoint}"
    # E3: target + countdown + rest-prompt UX markers
    assert "STATE_LABEL" in panel
    assert "DIR_LABEL" in panel
    assert "remaining" in panel
    assert "Get ready" in panel
    assert "Rest — next trial" in panel


def test_experiment_panel_metadata_autoconfig():
    """P20: metric/device_mode are read-only from the live config (no hand
    selects); electrode is conditional on has_hybrid; subject/session remain
    hand-filled."""
    panel = (APPJSX.parent / "ExperimentPanel.jsx").read_text(encoding="utf-8")
    # read-only actual config display
    assert "metric: {cfg ? cfg.metric : '…'}" in panel
    assert "roles: {(cfg ? cfg.roles : []).join(' / ') || '…'}" in panel
    # electrode only when a hybrid is present
    assert "cfg.has_hybrid && (" in panel
    assert 'value="dry"' in panel and 'value="wet"' in panel
    # hand-filled: subject + session only
    assert 'placeholder="Subject"' in panel
    assert 'placeholder="Sess #"' in panel
    # NO hand-filled metric / device_mode selects remain
    assert "METRIC_OPTIONS" not in panel
    assert "Single device" not in panel
    assert "Dual device" not in panel


# --- P17①: web GUI log panel ---------------------------------------------

def test_log_panel_wired_into_app():
    """P17①: the log panel is imported and rendered by App.jsx (own component
    file — the O5 incremental split)."""
    src = _app()
    assert "import LogPanel from './LogPanel';" in src
    assert "<LogPanel />" in src


def test_log_panel_markers():
    """P17①: the panel fetches /api/logs, collapses, refreshes, auto-polls."""
    panel = (APPJSX.parent / "LogPanel.jsx").read_text(encoding="utf-8")
    assert "/api/logs" in panel
    assert "Collapse" in panel and "Expand" in panel
    assert "Refresh" in panel
    assert "auto (2 s)" in panel

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
    assert "<ExperimentPanel config={experimentConfig} />" in src  # P21: live 01 prop


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
    """P20+P21: metric/device_mode/roles come from the LIVE App.jsx 01 config
    prop (no hand selects, no backend poll); electrode is conditional on
    has_hybrid; subject/session remain hand-filled."""
    panel = (APPJSX.parent / "ExperimentPanel.jsx").read_text(encoding="utf-8")
    # the panel consumes the config from PROPS, not the state poll
    assert "export default function ExperimentPanel({ config })" in panel
    assert "const cfg = config || {};" in panel
    # read-only actual config display (values from the prop)
    assert "cfg.metric || '…'" in panel
    assert "(cfg.roles || []).join(' / ') || '…'" in panel
    # electrode only when a hybrid is present
    assert "cfg.has_hybrid && (" in panel
    assert 'value="dry"' in panel and 'value="wet"' in panel
    # hand-filled: subject + session only
    assert "fieldLabelStyle" in panel
    assert 'placeholder="e.g. S01"' in panel
    # NO hand-filled metric / device_mode selects remain
    assert "METRIC_OPTIONS" not in panel
    assert "Single device" not in panel
    assert "Dual device" not in panel


def test_experiment_config_passed_as_live_prop():
    """P21①/②: App.jsx derives the experiment config from its live 01 state
    (has_hybrid from the DEVICE selection, covering a single-device hybrid)
    and passes it as a prop — editing 01 updates the panel instantly."""
    src = _app()
    assert "function experimentConfigFromApp(" in src
    assert "experimentConfigFromApp({" in src
    assert "eegBrand === 'gtec_hybrid' ? 'hybrid' : 'headband'" in src
    assert "has_hybrid: devices.some((d) => d.device === 'hybrid')" in src


def test_experiment_panel_layout_markers():
    """P21③: subject/session carry labels; the read-only config sits on the
    same row to the right; names (mono small) and values (body) use distinct
    fonts."""
    panel = (APPJSX.parent / "ExperimentPanel.jsx").read_text(encoding="utf-8")
    assert "fieldLabelStyle" in panel
    assert "Subject" in panel and "Session #" in panel
    assert "nameStyle" in panel and "valueStyle" in panel
    assert "fontFamily: 'var(--font-mono)'" in panel   # name style (mono small)


def _extract_function(src: str, name: str) -> str:
    """Brace-matched extraction of a top-level function (handles nested {}).

    The regex captures through the body's opening '{' (after the param list),
    so brace-matching starts at the FUNCTION BODY — not the destructuring
    braces inside the parameter list."""
    import re
    m = re.search(rf"function {name}\(.*?\) \{{", src, re.DOTALL)
    assert m, f"function {name} not found in App.jsx"
    start = m.start()
    depth = 0
    for j in range(m.end() - 1, len(src)):  # from the body '{'
        if src[j] == "{":
            depth += 1
        elif src[j] == "}":
            depth -= 1
            if depth == 0:
                return src[start:j + 1]
    raise AssertionError(f"unbalanced braces in {name}")


def test_experiment_config_from_app_node():
    """P21②: has_hybrid derives from the DEVICE selection — the three cases:
    single hybrid, dual-with-hybrid, and only-headband (no electrode)."""
    import subprocess

    fn = _extract_function(_app(), "experimentConfigFromApp")
    script = fn + """
const cases = [
  // single-device hybrid → has_hybrid true, single mode, 1 device
  [{ role1:'speed', role2:'steering', metric:'tbr', device1:'hybrid', device2:'', source1:'gtec_hybrid_black', source2:'', dualDevice:false },
   { metric:'tbr', device_mode:'single', roles:['speed'], has_hybrid:true, devCount:1 }],
  // dual with a hybrid → has_hybrid true, dual mode, 2 devices
  [{ role1:'speed', role2:'steering', metric:'ei', device1:'headband', device2:'hybrid', source1:'gtec_bci_core4', source2:'gtec_hybrid_black', dualDevice:true },
   { metric:'ei', device_mode:'dual', roles:['speed','steering'], has_hybrid:true, devCount:2 }],
  // only a headband → no hybrid, no electrode
  [{ role1:'speed', role2:'steering', metric:'alpha', device1:'headband', device2:'', source1:'gtec_bci_core4', source2:'', dualDevice:false },
   { metric:'alpha', device_mode:'single', roles:['speed'], has_hybrid:false, devCount:1 }],
];
for (const [inp, want] of cases) {
  const got = experimentConfigFromApp(inp);
  for (const k of ["metric","device_mode","roles","has_hybrid"]) {
    if (JSON.stringify(got[k]) !== JSON.stringify(want[k])) {
      console.error("FAIL", JSON.stringify(inp), k, "got", got[k], "want", want[k]); process.exit(1);
    }
  }
  if (got.devices.length !== want.devCount) {
    console.error("FAIL devCount", got.devices.length, want.devCount); process.exit(1);
  }
}
console.log("experimentConfigFromApp OK");
"""
    r = subprocess.run(["node", "-e", script], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    assert "OK" in r.stdout


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

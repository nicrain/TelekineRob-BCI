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
    assert "Break — next trial" in panel  # P28: between-trials rest is Break


# --- P28: experiment target-display UX -------------------------------------

def test_experiment_target_style_markers():
    """P28①②: the three target states are visually distinct and English only —
    Focus = blue (--f-info), Relax = green (--f-ok), Break = neutral gray +
    timer icon + 'next trial in Xs' countdown. No warning red, no Chinese."""
    panel = (APPJSX.parent / "ExperimentPanel.jsx").read_text(encoding="utf-8")
    # Focus / Relax label the per-row target STATE (replaces ATTENTION/REST)
    assert "STATE_LABEL = { attention: 'Focus', rest: 'Relax' }" in panel
    # color keyed by the STATE — Focus blue, Relax green
    assert "isFocus ? 'var(--f-info)' : 'var(--f-ok)'" in panel
    # Break: between-trials rest — timer icon + countdown, neutral gray
    assert "⏱ Break — next trial in {remaining}s" in panel
    # the old warning-red target color is gone; no Chinese labels anywhere
    assert "'var(--f-red)'" not in panel
    for zh in ("注意", "放松", "休息", "方向"):
        assert zh not in panel


def test_experiment_target_role_mapped_rows():
    """P28③: target rows are mapped per REAL device by role — speed → a_state,
    steering → b_state + b_direction — and labeled with the actual subject
    name; single device renders one row (whatever its role), dual renders two.
    The old hardcoded A:/B: lines are gone."""
    panel = (APPJSX.parent / "ExperimentPanel.jsx").read_text(encoding="utf-8")
    # rows come from the device list, not hardcoded lines
    assert "devices.map((d, i)" in panel
    assert "isSpeed ? target.a_state : target.b_state" in panel
    assert "DIR_LABEL[target.b_direction]" in panel
    # no hardcoded A:/B: target lines remain
    assert "A: {STATE_LABEL" not in panel
    assert "B: {STATE_LABEL" not in panel
    # subject name per row — single → subject, dual → subject / subject_b
    assert "i === 0 ? meta.subject : meta.subject_b" in panel
    assert "devices.length > 1" in panel and ": meta.subject" in panel


# --- P29: target table + smooth countdown + style tweaks -------------------

def test_experiment_target_countdown_smooth_node():
    """P29②: the countdown is a pure function over an ABSOLUTE phase-end
    timestamp and `now` — Math.max(0, Math.ceil((endTs-now)/1000)) — so a
    fixed ~200 ms tick changes the shown second exactly 1 s apart."""
    import subprocess
    panel = (APPJSX.parent / "ExperimentPanel.jsx").read_text(encoding="utf-8")
    # the panel ticks `now` every 200 ms and recomputes from end_ts_ms
    assert "setInterval(() => setNow(Date.now()), 200)" in panel
    assert "countdownSec(exp.end_ts_ms, now)" in panel
    assert "remaining_sec ?? 0" in panel  # fallback kept
    fn = _extract_function(panel, "countdownSec")
    script = fn + """
const cases = [
  [100000, 90000, 10],   // 10.0 s left → 10
  [100000, 97000, 3],    // 3.0 s left → 3
  [100000, 99999, 1],    // 1 ms left → still 1
  [100000, 100000, 0],   // exactly at the end → 0
  [100000, 105000, 0],   // past the end → clamped to 0
];
for (const [endTs, now, want] of cases) {
  const got = countdownSec(endTs, now);
  if (got !== want) { console.error("FAIL", endTs, now, "got", got, "want", want); process.exit(1); }
}
console.log("countdownSec OK");
"""
    r = subprocess.run(["node", "-e", script], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    assert "OK" in r.stdout


def test_experiment_target_subject_plain_color():
    """P29①: the subject NAME is plain text color (--f-text-primary), not an
    accent color; the Focus/Relax state color is kept on the Actions cell."""
    panel = (APPJSX.parent / "ExperimentPanel.jsx").read_text(encoding="utf-8")
    # the Subjects cell: right-aligned fixed width + plain text color
    assert "textAlign: 'right', width: 120, color: 'var(--f-text-primary)'" in panel
    # only the Actions cell carries the state color
    assert "color: isFocus ? 'var(--f-info)' : 'var(--f-ok)'" in panel


def test_experiment_target_table_header_and_direction():
    """P29 supplement: the target display is a table with a Subjects | Actions
    | Direction header, one row per REAL device; the Direction column is a
    small muted mono cell that only carries a value for steering roles (speed
    shows the em dash), and the Subjects column is right-aligned fixed width so
    the colons align across rows."""
    panel = (APPJSX.parent / "ExperimentPanel.jsx").read_text(encoding="utf-8")
    # header row
    assert "<th" in panel
    assert "Subjects</th>" in panel
    assert "Actions</th>" in panel
    assert "Direction</th>" in panel
    # rows per real device (single = one, dual = two)
    assert "<tbody>" in panel
    assert "<tr key={i}>" in panel
    assert "devices.map((d, i)" in panel
    # Direction column: small muted mono, steering only
    assert "fontSize: 12, color: 'var(--f-text-secondary)', fontFamily: 'var(--font-mono)'" in panel
    assert "isSpeed ? '—' : DIR_LABEL[target.b_direction]" in panel
    # Subjects column right-aligned fixed width (colon alignment across rows)
    assert "{subject}:" in panel
    assert "textAlign: 'right', width: 120" in panel


def test_experiment_panel_metadata_autoconfig():
    """P20+P21: metric/device_mode/roles come from the LIVE App.jsx 01 config
    prop (no hand selects, no backend poll); electrode is conditional on
    has_hybrid; subject/session remain hand-filled."""
    panel = (APPJSX.parent / "ExperimentPanel.jsx").read_text(encoding="utf-8")
    # the panel consumes the config from PROPS, not the state poll
    assert "export default function ExperimentPanel({ config })" in panel
    assert "const cfg = config || {};" in panel
    # read-only actual config display (values from the prop, capitalized)
    assert "cfg.metric || '…'" in panel
    assert "(cfg.roles || []).map((r) => ROLE_LABEL[r] || r).join(' / ') || '…'" in panel
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
    """P21③ + P23: all fields vertical — mono-small label on top, body value
    below; the read-only config uses the same fieldLabelStyle layout; every
    label is Title Case."""
    panel = (APPJSX.parent / "ExperimentPanel.jsx").read_text(encoding="utf-8")
    assert "fieldLabelStyle" in panel and "valueStyle" in panel
    assert "fontFamily: 'var(--font-mono)'" in panel      # label font (mono small)
    assert "fontFamily: 'var(--font-display)'" in panel   # value font (body)
    for label in ("Subject\n", "Session #\n", "Electrode\n", "Metric\n", "Mode\n", "Roles\n"):
        assert label in panel, f"missing Title-Case label {label!r}"


def test_experiment_panel_value_capitalization():
    """P23③: raw config values are capitalized for display — Alpha/TBR/EI,
    Dual/Single, Steering/Speed."""
    panel = (APPJSX.parent / "ExperimentPanel.jsx").read_text(encoding="utf-8")
    assert "METRIC_LABEL = { alpha: 'Alpha', tbr: 'TBR', ei: 'EI' }" in panel
    assert "MODE_LABEL = { single: 'Single', dual: 'Dual' }" in panel
    assert "ROLE_LABEL = { speed: 'Speed', steering: 'Steering' }" in panel
    assert "METRIC_LABEL[cfg.metric]" in panel
    assert "MODE_LABEL[cfg.device_mode]" in panel
    assert "ROLE_LABEL[r]" in panel


def test_experiment_panel_electrode_labeled_after_session():
    """P22① + P23: electrode is a labeled field AFTER session_no (subject →
    session → electrode), dropdown carries only dry / wet (no placeholder)."""
    panel = (APPJSX.parent / "ExperimentPanel.jsx").read_text(encoding="utf-8")
    # source order: the Session # label precedes the electrode dropdown
    assert panel.index("Session #") < panel.index("value={meta.electrode || 'dry'}")
    # electrode is a label-wrapped field (own-line text), dry/wet only
    assert "Electrode\n" in panel
    assert 'value="dry"' in panel and 'value="wet"' in panel
    assert 'value=""' not in panel  # no empty placeholder option anywhere
    # single mode (6: Subject/Session/Electrode + Metric/Mode/Roles) +
    # dual mode (6, P24) = 12 labeled fields in the vertical layout
    assert panel.count("style={fieldLabelStyle}") == 12


def test_experiment_panel_electrode_dropdown_tweaks():
    """P26②③ + P27②: the Electrode dropdowns have a FIXED width 64 (so the
    flex column can't stretch them) and options display as Dry / Wet."""
    panel = (APPJSX.parent / "ExperimentPanel.jsx").read_text(encoding="utf-8")
    assert panel.count("width: 64 }} value={meta.electrode") == 2   # single + dual
    assert "minWidth: 64" not in panel                             # no stretchable minWidth
    assert '<option value="dry">Dry</option>' in panel
    assert '<option value="wet">Wet</option>' in panel
    assert '<option value="dry">dry</option>' not in panel  # not the old lowercase text


def test_experiment_panel_field_order():
    """P27①: the field order is Subject → Session → Electrode → Metric →
    Roles → Mode in BOTH branches (Mode last)."""
    panel = (APPJSX.parent / "ExperimentPanel.jsx").read_text(encoding="utf-8")
    # dual branch (first in source): A input → Session → Electrode → Metric → Roles → Mode
    # (label text with \n avoids matching comments like "Session #/Mode")
    assert (panel.index('placeholder="A"')
            < panel.index("Session #\n")
            < panel.index("Electrode\n")
            < panel.index("Metric\n")
            < panel.index("Roles\n")
            < panel.index("Mode\n"))
    # single branch (after the dual branch in source): Metric → Roles → Mode
    assert (panel.rfind("Metric\n")
            < panel.rfind("Roles\n")
            < panel.rfind("Mode\n"))


def test_experiment_panel_dual_layout_markers():
    """P24+P25: dual device renders a two-row column grid — two Subject inputs
    (A/B), shared Session #/Mode stretched, Electrode N/A + dry/wet (centered),
    per-person Metric/Roles with proper row spacing; single-mode unchanged."""
    panel = (APPJSX.parent / "ExperimentPanel.jsx").read_text(encoding="utf-8")
    assert "isDual ? (" in panel                        # dual branch present
    assert 'placeholder="A"' in panel and 'placeholder="B"' in panel  # two subjects
    assert "meta.subject_b" in panel                    # device B operator
    assert ">N/A<" in panel                             # device1 electrode, centered
    assert "justifyContent: 'center'" in panel          # N/A aligns with the select
    assert "height: 58" in panel                        # shared Session #/Mode stretched
    assert "rowValueStyle" in panel                     # per-row height spacing
    assert "METRIC_LABEL[d.metric]" in panel            # per-device metric row
    assert "ROLE_LABEL[d.role]" in panel                # per-device role row
    assert 'placeholder="e.g. S01"' in panel            # single-mode branch kept


def test_experiment_panel_exit_and_reconfigure():
    """P22②: the session view has an Exit button back to the form; Configure
    stays reachable (Configure new session) — no one-way door."""
    panel = (APPJSX.parent / "ExperimentPanel.jsx").read_text(encoding="utf-8")
    assert "formOpen" in panel
    assert "(!configured || formOpen)" in panel       # form reachable again
    assert "configured && !formOpen" in panel         # session view hides the form
    assert "setFormOpen(true)" in panel               # Exit opens the form
    assert "setFormOpen(false)" in panel              # Configure returns to the view
    assert ">Exit<" in panel
    assert "Configure new session" in panel


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
    """P21② + P24: has_hybrid derives from the DEVICE selection — single
    hybrid, dual-with-hybrid, only-headband; dual carries a per-device metric
    and both roles/operators."""
    import subprocess

    fn = _extract_function(_app(), "experimentConfigFromApp")
    script = fn + """
const cases = [
  // single-device hybrid → has_hybrid true, single mode, 1 device
  [{ role1:'speed', role2:'steering', metric:'tbr', metric2:'ei', device1:'hybrid', device2:'', source1:'gtec_hybrid_black', source2:'', dualDevice:false },
   { metric:'tbr', device_mode:'single', roles:['speed'], has_hybrid:true, devCount:1, devMetric:['tbr'] }],
  // dual with a hybrid → has_hybrid true, dual mode, per-device metrics
  [{ role1:'speed', role2:'steering', metric:'ei', metric2:'tbr', device1:'headband', device2:'hybrid', source1:'gtec_bci_core4', source2:'gtec_hybrid_black', dualDevice:true },
   { metric:'ei', device_mode:'dual', roles:['speed','steering'], has_hybrid:true, devCount:2, devMetric:['ei','tbr'] }],
  // only a headband → no hybrid, no electrode
  [{ role1:'speed', role2:'steering', metric:'alpha', metric2:'tbr', device1:'headband', device2:'', source1:'gtec_bci_core4', source2:'', dualDevice:false },
   { metric:'alpha', device_mode:'single', roles:['speed'], has_hybrid:false, devCount:1, devMetric:['alpha'] }],
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
  const dm = got.devices.map((d) => d.metric);
  if (JSON.stringify(dm) !== JSON.stringify(want.devMetric)) {
    console.error("FAIL devMetric", JSON.stringify(dm), JSON.stringify(want.devMetric)); process.exit(1);
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

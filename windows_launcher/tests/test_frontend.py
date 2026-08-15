"""Static regression tests for the console page's fetch method choice.

Real-device bug: action buttons called ``api(path)`` with no body, so the
``api()`` helper (body ? POST : GET) issued a GET → the server only has POST
routes → 404 "Unknown path". These tests pin the fix in the shipped HTML so a
future "bare api()" reversion is caught without a browser.
"""
import json
import re
from pathlib import Path

INDEX = Path(__file__).resolve().parents[1] / "static" / "index.html"
CONFIG = Path(__file__).resolve().parents[1] / "config.json"


def _extract_function(name: str) -> str:
    html = INDEX.read_text(encoding="utf-8")
    m = re.search(rf"async function {name}\(.*?\) \{{.*?\n\}}", html, re.DOTALL)
    assert m, f"async function {name} not found in index.html"
    return m.group(0)


def test_run_action_forces_post():
    """runAction must send a body so api() picks POST, never GET."""
    block = _extract_function("runAction")
    assert "await api(path, {});" in block, "runAction lost its POST body"
    assert not re.search(r"await api\(path\)", block), (
        "bare api(path) in runAction would become a GET → 404"
    )
    # P10③: the endpoint follows the system state (running Start → /restart-system)
    assert "opControl(id, sysState, null).endpoint" in block


def test_render_ops_applies_disabled_at_creation():
    """P10①: op buttons must be born with their disabled state (in renderOps),
    so renderSystem rebuilding / running later can't wipe it — the pre-P10
    order bug. renderOps must run before renderSystem in the poll."""
    html = INDEX.read_text(encoding="utf-8")
    assert "btn.disabled = ctl.disabled;" in html
    assert "renderOps(); renderDevices(); renderSystem();" in html
    # renderSystem no longer touches op buttons (would fight the rebuild)
    assert 'document.getElementById("op-start-system")' not in html


def test_op_control_state_machine():
    """P10③: the Start/Stop/Restart button state machine as a pure function —
    running Start = Restart System (enabled), stopped/error = Start System,
    busy (starting/stopping) and stopped disable the relevant buttons."""
    import subprocess

    html = INDEX.read_text(encoding="utf-8")
    m = re.search(r"function opControl\(opId, sysState, baseLabel\) \{.*?\n\}", html, re.DOTALL)
    assert m, "opControl not found in index.html"
    fn = m.group(0)
    script = fn + """
const cases = [
  ["start-system", "running",  { label:"Restart System", endpoint:"/restart-system", disabled:false }],
  ["start-system", "stopped",  { label:"Start System",   endpoint:"/start-system",   disabled:false }],
  ["start-system", "error",    { label:"Start System",   endpoint:"/start-system",   disabled:false }],
  ["start-system", "starting", { label:"Start System",   endpoint:"/start-system",   disabled:true  }],
  ["start-system", "stopping", { label:"Start System",   endpoint:"/start-system",   disabled:true  }],
  ["stop-system",  "running",  { label:"Stop System",    endpoint:"/stop-system",    disabled:false }],
  ["stop-system",  "stopped",  { label:"Stop System",    endpoint:"/stop-system",    disabled:true  }],
  ["stop-system",  "starting", { label:"Stop System",    endpoint:"/stop-system",    disabled:true  }],
  ["restart-web",  "running",  { label:"Restart Web",    endpoint:"/restart-web",    disabled:false }],
  ["restart-web",  "stopped",  { label:"Restart Web",    endpoint:"/restart-web",    disabled:true  }],
  ["restart-web",  "error",    { label:"Restart Web",    endpoint:"/restart-web",    disabled:false }],
  ["exit",         "running",  { label:"Exit Launcher",  endpoint:"/shutdown",       disabled:false }],
];
for (const [id, st, want] of cases) {
  const got = opControl(id, st, null);
  for (const k of ["label","endpoint","disabled"]) {
    if (got[k] !== want[k]) { console.error("FAIL", id, st, k, "got", got[k], "want", want[k]); process.exit(1); }
  }
}
console.log("opControl OK");
"""
    r = subprocess.run(["node", "-e", script], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    assert "OK" in r.stdout


def test_toggle_device_keeps_body():
    """Device connect/disconnect still passes {device} (unaffected path)."""
    block = _extract_function("toggleDevice")
    assert "api(path, { device: id })" in block


def test_api_helper_picks_post_by_body():
    """The helper's contract: body → POST, no body → GET (used for the
    read-only GETs /status and /config)."""
    html = INDEX.read_text(encoding="utf-8")
    assert "method: body ? \"POST\" : \"GET\"" in html


def test_poll_status_loads_iframe_on_running_transition():
    """① After startup the web GUI auto-loads: pollStatus drives
    updateMainArea, which loads the themed iframe on the non-running →
    running transition. Running only, because the launcher's ready-check
    confirms the frontend is up before setting running."""
    html = INDEX.read_text(encoding="utf-8")
    assert "prevRunning" in html
    assert "updateMainArea()" in html
    assert 'G.status.system.state === "running"' in html
    assert 'G.prevRunning = G.status.system.state === "running";' in html
    assert "frame.src = webUrlWithTheme(G.webUrl, currentTheme())" in html


def test_sidebar_collapse_markers():
    """P2: collapse button lives in the static #mainbar, the collapsed class
    sits on #sidebar — neither is inside the poll re-render containers
    (#devices-list / #ops-list), so polling never resets the fold."""
    html = INDEX.read_text(encoding="utf-8")
    assert 'id="collapse-btn"' in html
    assert "#sidebar.collapsed" in html
    assert 'classList.toggle("collapsed")' in html
    assert "launcherSidebarCollapsed" in html  # localStorage persistence


def test_ferrari_theme_tokens():
    """P3: Ferrari dark palette — fonts, red, razor radius, mono labels."""
    html = INDEX.read_text(encoding="utf-8")
    assert "@import url('https://fonts.googleapis.com" in html
    assert "Space+Grotesk" in html
    assert "IBM+Plex+Mono" in html
    assert "#DA291C" in html.upper()          # Ferrari red (danger)
    assert "--radius:2px" in html             # razor
    assert "'IBM Plex Mono'" in html          # mono label font
    assert "--f-ok:#03904A" in html and "--f-warn:#F13A2C" in html


def test_refresh_button_reloads_iframe():
    """P5: mainbar has a Refresh button that re-points frame.src (the web
    GUI is cross-origin, so contentWindow.location.reload() would throw)."""
    html = INDEX.read_text(encoding="utf-8")
    assert 'id="refresh-btn"' in html
    assert "refreshFrame" in html
    assert 'frame.src = "about:blank"' in html
    assert "frame.src = webUrlWithTheme(G.webUrl, currentTheme())" in html  # themed reload
    # P7-③: Refresh is guarded on running — pointing the iframe at a dead
    # frontend would flash the browser's error page.
    assert 'G.status.system.state !== "running") return;' in html
    # the cross-origin-UNSAFE reload pattern must not appear as code
    # (frame.contentWindow.postMessage is fine — it's location.reload() that throws)
    assert "frame.contentWindow.location.reload()" not in html


def test_user_visible_layer_has_no_cjk():
    """P5: the shipped page and config labels must be CJK-free (English UI)."""
    cjk = re.compile(r"[一-鿿]")
    html = INDEX.read_text(encoding="utf-8")
    assert not cjk.search(html), "index.html has residual CJK"
    cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
    assert not cjk.search(json.dumps(cfg, ensure_ascii=False)), "config.json has residual CJK"


def test_view_log_wired():
    """P17②: the View Log button fetches /log and shows the modal."""
    html = INDEX.read_text(encoding="utf-8")
    assert 'id="log-btn" disabled onclick="viewLog()"' in html
    assert 'id="log-modal"' in html
    assert 'id="log-modal-body"' in html
    assert 'api("/log")' in html
    assert "closeLog" in html


def test_theme_toggle_and_cross_origin_sync_markers():
    """P6-①: theme toggle button, data-theme application, localStorage, and
    the cross-origin postMessage broadcast + listener."""
    html = INDEX.read_text(encoding="utf-8")
    assert 'id="theme-btn"' in html
    assert "toggleTheme" in html
    assert "document.documentElement.dataset.theme" in html
    assert 'type: "set-theme"' in html              # broadcast
    assert 'd.type === "set-theme"' in html         # listener
    assert "contentWindow.postMessage" in html


def test_light_theme_tokens_present():
    """P6-①: the [data-theme=light] Ferrari board mirrors web_gui."""
    html = INDEX.read_text(encoding="utf-8")
    assert '[data-theme="light"]' in html
    assert "--f-text-primary:#181818" in html
    assert "--f-text-secondary:#666666" in html
    assert "--f-red:#C41E13" in html
    assert "--f-status-off:#D6D2CC" in html
    # P7-②: ok/warn/info are NOT overridden in light — they fall back to
    # :root's #03904A/#F13A2C/#4C98B9, value-identical to web_gui's dots.
    assert "--f-ok:#1A7A3A" not in html
    assert "--f-warn:#C5221F" not in html
    assert "--f-info:#1769AA" not in html


def test_light_danger_border_matches_web_gui():
    """P15③: the light-mode .btn.danger border (--f-red-dark) must equal
    web_gui's palette (#B01E0A, styles.css) — not the drifted #A01409."""
    html = INDEX.read_text(encoding="utf-8")
    light = re.search(r'\[data-theme="light"\][^}]*\}', html, re.DOTALL)
    assert light, "light theme block not found in index.html"
    assert "--f-red-dark:#B01E0A" in light.group(0)
    # the danger button still keys its border off that token
    assert ".btn.danger { color:var(--f-red); border-color:var(--f-red-dark); }" in html


def test_placeholder_markers_and_show_hide():
    """P6-②: main-area placeholder exists and toggles with the iframe per
    system state (no browser error page when the frontend is down)."""
    html = INDEX.read_text(encoding="utf-8")
    assert 'id="placeholder"' in html
    assert "System Offline" in html
    assert "Starting System…" in html
    assert "updateMainArea" in html
    assert "Start the system from the sidebar to load the experiment interface." in html
    # iframe is never pre-loaded at init (the crying-face error page source)
    assert "Never pre-load the web GUI at init" in html
    assert 'frame.src = "about:blank"' in html
    assert "frame.style.display = \"none\"" in html
    # P7-①: the placeholder's error branch uses a red (err) dot, not grey
    assert 'st === "error" ? "dot err" : "dot"' in html


def test_mainbar_has_no_experiment_label():
    """P7-⑤: the static "Experiment" span is gone from mainbar."""
    html = INDEX.read_text(encoding="utf-8")
    assert "<span>Experiment</span>" not in html
    assert 'id="refresh-btn"' in html
    assert 'id="theme-btn"' in html


def test_weburl_with_theme_concat_bounds():
    """P6-①: the ?theme= URL concat pure function — the ? vs & boundary
    (extracted from the shipped page and executed under Node)."""
    import subprocess

    html = INDEX.read_text(encoding="utf-8")
    m = re.search(r"function webUrlWithTheme\(url, theme\) \{.*?\n\}", html, re.DOTALL)
    assert m, "webUrlWithTheme not found in index.html"
    fn = m.group(0)
    script = fn + """
const cases = [
  ["http://localhost:5173", "dark",  "http://localhost:5173?theme=dark"],
  ["http://localhost:5173", "light", "http://localhost:5173?theme=light"],
  ["http://localhost:5173/?x=1", "dark", "http://localhost:5173/?x=1&theme=dark"],
  ["http://localhost:5173?x=1", "dark", "http://localhost:5173?x=1&theme=dark"],
];
for (const [url, theme, want] of cases) {
  const got = webUrlWithTheme(url, theme);
  if (got !== want) { console.error("FAIL", url, theme, "got", got, "want", want); process.exit(1); }
}
console.log("webUrlWithTheme OK");
"""
    r = subprocess.run(["node", "-e", script], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    assert "OK" in r.stdout


def test_lan_forward_fix_markers():
    """P42②③: the stale-forwarding prompt + one-click UAC fix button +
    /lan-forward/fix endpoint are wired (English, no CJK in code)."""
    html = INDEX.read_text(encoding="utf-8")
    assert 'id="lan-forward"' in html
    assert "renderLanForward" in html
    assert "fixLanForward" in html
    assert "/lan-forward/fix" in html
    assert 'lan_forward !== "stale"' in html
    assert "LAN forwarding needs an update" in html
    assert "Fix LAN forwarding" in html
    assert "Start-Process" not in html  # the UAC spawn is server-side only

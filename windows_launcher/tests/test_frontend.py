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
    # P1: the 退出总控 button maps to the /shutdown endpoint
    assert '"exit": "/shutdown"' in block


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

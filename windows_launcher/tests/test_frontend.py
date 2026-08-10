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


def test_poll_status_reloads_iframe_on_running_transition():
    """① After startup the web GUI must auto-load: pollStatus reloads the
    iframe on the non-running → running transition. Triggering on running
    (not starting) so the frontend is already up (ready-check confirmed)."""
    html = INDEX.read_text(encoding="utf-8")
    assert "prevRunning" in html
    assert 'G.status.system.state === "running"' in html
    assert 'frame.src = "about:blank"' in html
    assert "G.prevRunning = running;" in html


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
    assert "frame.src = G.webUrl" in html
    # the cross-origin-unsafe reload pattern must not appear as code
    assert "frame.contentWindow" not in html


def test_user_visible_layer_has_no_cjk():
    """P5: the shipped page and config labels must be CJK-free (English UI)."""
    cjk = re.compile(r"[一-鿿]")
    html = INDEX.read_text(encoding="utf-8")
    assert not cjk.search(html), "index.html has residual CJK"
    cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
    assert not cjk.search(json.dumps(cfg, ensure_ascii=False)), "config.json has residual CJK"

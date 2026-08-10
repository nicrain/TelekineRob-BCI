"""Static regression tests for the console page's fetch method choice.

Real-device bug: action buttons called ``api(path)`` with no body, so the
``api()`` helper (body ? POST : GET) issued a GET → the server only has POST
routes → 404 "未知地址". These tests pin the fix in the shipped HTML so a
future "bare api()" reversion is caught without a browser.
"""
import re
from pathlib import Path

INDEX = Path(__file__).resolve().parents[1] / "static" / "index.html"


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

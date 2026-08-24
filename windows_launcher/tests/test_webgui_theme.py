"""Static regression for the web GUI theme sync (P6-① B).

jsdom/vitest aren't installed in this repo and the frontend build is a
user-side WSL2 task, so we pin the P6 markers in App.jsx statically here.
"""
from pathlib import Path

APPJSX = Path(__file__).resolve().parents[2] / "web_gui" / "frontend" / "src" / "App.jsx"


def _app() -> str:
    return APPJSX.read_text(encoding="utf-8")


def test_theme_init_prefers_url_param():
    """?theme= query param > localStorage > default dark."""
    src = _app()
    assert "new URLSearchParams(window.location.search).get('theme')" in src
    assert "localStorage.getItem('theme') || 'dark'" in src
    # the URL param must be checked first (priority order)
    assert src.index("URLSearchParams") < src.index("localStorage.getItem('theme')")


def test_theme_broadcasts_to_parent():
    """Theme change posts set-theme to the embedding launcher."""
    src = _app()
    assert "window.parent.postMessage({ type: 'set-theme', theme }, '*')" in src


def test_theme_listens_for_messages():
    """The launcher's set-theme is received and applied."""
    src = _app()
    assert "window.addEventListener('message', onMessage)" in src
    assert "d.type === 'set-theme'" in src
    assert "setTheme(d.theme)" in src

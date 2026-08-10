"""Static checks for launcher.bat (P1) — batch isn't executed here, the
operator's review + real-device run validate the actual cmd behaviour."""
from pathlib import Path

BAT = Path(__file__).resolve().parents[1] / "launcher.bat"


def test_bat_windowless_with_min_fallback():
    text = BAT.read_text(encoding="utf-8")
    assert "pythonw" in text
    assert 'start /min "" cmd /c "python launcher_server.py"' in text


def test_bat_idempotent_replacement_markers():
    """pidfile + liveness + command-line check before killing the old
    instance (prevents PID-reuse misfire)."""
    text = BAT.read_text(encoding="utf-8")
    assert "launcher_server.pid" in text
    assert "taskkill /F /PID" in text
    assert "wmic" in text              # command-line verification
    assert "launcher_server.py" in text
    assert "del last_url.txt" in text  # stale-URL guard kept


def test_bat_user_facing_strings_are_english():
    """P7-④: the operator-facing echo lines are English and CJK-free."""
    import re

    text = BAT.read_text(encoding="utf-8")
    assert "Python not found" in text
    assert "startup timed out" in text
    assert "Could not read the service address" in text
    assert not re.search(r"[一-鿿]", text), "launcher.bat has residual CJK"

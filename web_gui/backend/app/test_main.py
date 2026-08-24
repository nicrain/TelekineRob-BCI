from app import main
from app.main import _rest_authorized, _validate_origin, _ws_authorized


# ---------------------------------------------------------------------------
# Origin whitelist — default is locked-down (no wildcard)
# ---------------------------------------------------------------------------


def test_origin_default_accepts_vite_and_rejects_external():
    assert main._wildcard_origin is False
    assert _validate_origin("http://localhost:5173") is True
    assert _validate_origin("https://localhost:5173") is True
    assert _validate_origin("http://127.0.0.1:5173") is True
    assert _validate_origin("http://evil.example.com") is False
    assert _validate_origin("") is False
    assert _validate_origin("file:///tmp/x") is False


def test_origin_custom_env_origin(monkeypatch):
    monkeypatch.setattr(main, "_frontend_origin", "https://eeg.zhaoyu.wang")
    monkeypatch.setattr(main, "_wildcard_origin", False)
    assert _validate_origin("https://eeg.zhaoyu.wang") is True
    assert _validate_origin("http://evil.example.com") is False


def test_origin_explicit_wildcard_still_allows_all(monkeypatch):
    monkeypatch.setattr(main, "_wildcard_origin", True)
    assert _validate_origin("http://anything.example.com") is True


# ---------------------------------------------------------------------------
# Control token — opt-in via WEB_GUI_CONTROL_TOKEN
# ---------------------------------------------------------------------------


def test_rest_authorized_no_token_configured(monkeypatch):
    monkeypatch.setattr(main, "_control_token", "")
    assert _rest_authorized("") is True
    assert _rest_authorized("Bearer whatever") is True


def test_rest_authorized_with_token(monkeypatch):
    monkeypatch.setattr(main, "_control_token", "s3cr3t")
    assert _rest_authorized("Bearer s3cr3t") is True
    assert _rest_authorized("Bearer wrong") is False
    assert _rest_authorized("") is False


def test_ws_authorized_with_token(monkeypatch):
    monkeypatch.setattr(main, "_control_token", "s3cr3t")
    assert _ws_authorized("s3cr3t") is True
    assert _ws_authorized("wrong") is False
    assert _ws_authorized("") is False

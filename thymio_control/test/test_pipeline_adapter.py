"""Tests for ``build_adapter()`` in the new modular pipeline."""

import pytest

from thymio_control.pipeline import build_adapter


class _FakeArgs:
    """Minimal argparse-like object for testing."""

    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


# ---------------------------------------------------------------------------
# Dispatch tests — only test modes that don't require external connections
# (mock, keyboard) or config validation (missing file-path, unknown mode).
# LSL / TCP modes need pylsl / network and can't be instantiated here.
# ---------------------------------------------------------------------------


def test_build_adapter_mock_mode():
    args = _FakeArgs(input="mock")
    adapter = build_adapter(args)
    from thymio_control.adapters.mock import MockAdapter

    assert isinstance(adapter, MockAdapter)


def test_build_adapter_keyboard_mode():
    args = _FakeArgs(input="keyboard")
    adapter = build_adapter(args)
    from thymio_control.adapters.mock import KeyboardAdapter

    assert isinstance(adapter, KeyboardAdapter)


def test_build_adapter_rejects_unknown_mode():
    args = _FakeArgs(input="nonesuch")
    with pytest.raises(RuntimeError, match="Unsupported input mode"):
        build_adapter(args)


def test_build_adapter_tcp_file_requires_file_path():
    args = _FakeArgs(input="tcp_file", file_path="")
    with pytest.raises(RuntimeError, match="file-path"):
        build_adapter(args)


def test_build_adapter_file_requires_file_path():
    args = _FakeArgs(input="file", file_path="")
    with pytest.raises(RuntimeError, match="file-path"):
        build_adapter(args)





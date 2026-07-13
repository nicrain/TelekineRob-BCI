"""Tests for ``build_adapter()`` in the new modular pipeline."""

import pytest

from thymio_control.pipeline import build_adapter


class _FakeArgs:
    """Minimal argparse-like object for testing."""

    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


def test_build_adapter_keyboard_mode():
    args = _FakeArgs(input="keyboard")
    adapter = build_adapter(args)
    from thymio_control.adapters.mock import KeyboardAdapter

    assert isinstance(adapter, KeyboardAdapter)


def test_build_adapter_rejects_unknown_mode():
    args = _FakeArgs(input="nonesuch")
    with pytest.raises(RuntimeError, match="Unsupported input mode"):
        build_adapter(args)







"""High-level pipeline assembler for the Thymio EEG control system.

This module is the **single public entry point** for the new modular
architecture.  External code (ROS nodes, scripts, notebooks) should import
from here rather than from individual sub-modules, so internal restructuring
remains transparent to callers.

Typical usage::

    from thymio_control.pipeline import build_pipeline

    adapter, processor, policy = build_pipeline(args)
    while True:
        frame = adapter.read_frame()
        if frame:
            features = processor(frame.metrics)
            intents  = policy.compute_intents(features)
            # → send intents over UDP / publish to ROS
"""
from __future__ import annotations

import logging
from typing import Any, Callable, Dict, Tuple

_log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Public registry of policies
# ---------------------------------------------------------------------------

from thymio_control.policies.ei    import EiPolicy
from thymio_control.policies.tbr   import TbrPolicy
from thymio_control.policies.alpha import AlphaPolicy

POLICIES: Dict[str, type] = {
    "ei":    EiPolicy,
    "tbr":   TbrPolicy,
    "alpha": AlphaPolicy,
}

# ---------------------------------------------------------------------------
# Adapter factory
# ---------------------------------------------------------------------------

def build_adapter(args: Any):
    """Instantiate the appropriate adapter based on ``args.input``.

    Supports the same ``input`` choices as the legacy pipeline:
    ``mock``, ``keyboard``, ``tcp_client``, ``tcp_file``, ``lsl``,
    plus the new ``lsl`` mode that applies on-device DSP.

    Parameters
    ----------
    args : argparse.Namespace or similar
        Must have an ``input`` attribute.

    Raises
    ------
    RuntimeError
        For unsupported input modes or missing configuration.
    """
    from thymio_control.adapters.base import BaseAdapter

    mode = str(getattr(args, "input", "mock")).strip()

    if mode == "mock":
        from thymio_control.adapters.mock import MockAdapter
        return MockAdapter()

    if mode == "keyboard":
        from thymio_control.adapters.mock import KeyboardAdapter
        return KeyboardAdapter()

    if mode == "tcp_client":
        from thymio_control.adapters.tcp_client import TcpClientAdapter
        return TcpClientAdapter(args.tcp_host, args.tcp_port)

    if mode == "tcp_file":
        file_path = getattr(args, "file_path", "")
        if not file_path:
            raise RuntimeError("tcp_file mode requires --file-path")
        from thymio_control.adapters.tcp_file import TcpFileAdapter
        return TcpFileAdapter(file_path)

    if mode == "file":
        file_path = getattr(args, "file_path", "")
        if not file_path:
            raise RuntimeError("file mode requires --file-path")
        from thymio_control.adapters.edf_file import EdfFileAdapter
        return EdfFileAdapter(file_path, realtime=True)

    if mode == "lsl":
        # Raw EEG → on-board DSP via Welch PSD (RawLslAdapter)
        # source_id enables targeting a specific LSL stream (e.g. gtec bridge)
        from thymio_control.adapters.lsl_raw import RawLslAdapter
        return RawLslAdapter(
            stream_type=getattr(args, "lsl_stream_type", "EEG"),
            timeout=getattr(args, "lsl_timeout", 5.0),
            source_id=getattr(args, "lsl_source_id", "") or None,
        )

    raise RuntimeError(f"Unsupported input mode: {mode!r}")


# ---------------------------------------------------------------------------
# Processor factory
# ---------------------------------------------------------------------------

def build_processor() -> Callable[[Dict[str, float]], Dict[str, float]]:
    """Return the default feature enrichment function.

    Returns a callable: ``metrics → enriched_metrics``.
    """
    from thymio_control.processors.enrich import enrich_features
    return enrich_features


# ---------------------------------------------------------------------------
# Top-level assembler
# ---------------------------------------------------------------------------

def build_pipeline(args: Any) -> Tuple[Any, Callable, Any]:
    """Assemble and return ``(adapter, processor, policy)``.

    Parameters
    ----------
    args : argparse.Namespace
        Parsed command-line arguments (or any object with the same attrs).

    Returns
    -------
    (adapter, processor, policy)
        - *adapter*   implements ``read_frame() -> Optional[EegFrame]``
        - *processor* is a callable ``metrics → enriched_metrics``
        - *policy*    implements ``compute_intents(features) -> dict``
    """
    adapter    = build_adapter(args)
    processor  = build_processor()
    policy_name = getattr(args, "policy", "tbr")
    if policy_name not in POLICIES:
        raise ValueError(
            f"Unknown policy: {policy_name!r}. "
            f"Valid options: {sorted(POLICIES.keys())}"
        )
    policy = POLICIES[policy_name]()
    return adapter, processor, policy

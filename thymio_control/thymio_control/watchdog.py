"""Watchdog decision logic for the EEG control node.

The data-loss response is a pure decision (no ROS dependencies) so the
single-device semantics can be unit-tested without a ROS installation.

Original (pre-dual-device) behavior, which is the contract for
``stop_on_data_loss=False``:

- within the watchdog grace window (``stale`` is False)  → hold ("replay")
  the last intents — this is not a silent gap, it smooths dropped frames.
- past the window, first tick (``connected`` is True)   → one zero-velocity
  twist ("zero"), then stop. NOT perpetual replay.
- past the window, already stopped                       → stay silent ("halt").

Dual-device semantics (``stop_on_data_loss=True``): the node goes fully
silent on data loss ("halt") so the ``cmd_vel_fuser`` sees staleness from
the missing messages and takes over with its own freshness watchdog.
"""

from __future__ import annotations


def decide_watchdog_action(
    *,
    stale: bool,
    connected: bool,
    stop_on_data_loss: bool,
) -> str:
    """Decide this tick's response when no frame arrived.

    Parameters
    ----------
    stale : bool
        True when the last frame is older than ``watchdog_sec``.
    connected : bool
        Whether the adapter was receiving data before this loss.
    stop_on_data_loss : bool
        Dual-device mode switch (node stays silent and lets the fuser act).

    Returns
    -------
    str
        One of ``"replay"`` (publish last intents), ``"zero"`` (publish one
        zero-velocity twist then go silent), or ``"halt"`` (publish nothing).
    """
    if stop_on_data_loss:
        return "halt"
    if stale:
        return "zero" if connected else "halt"
    return "replay"

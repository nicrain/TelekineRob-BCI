"""Watchdog decision logic for the EEG control node.

The data-loss response is a pure decision (no ROS dependencies) so the
single-device semantics can be unit-tested without a ROS installation.

The node's analysis frames arrive at hop cadence (~2 Hz, one window per
``hop_sec``) while ``_tick`` runs at ``publish_hz`` (20 Hz). Between two
frames there are ~9 ticks with no new frame; those are NOT data loss.
During them the node must keep publishing ("replay") so the partial twist
stays a continuous ~20 Hz stream — a 2 Hz trickle would sit right at the
fuser's freshness boundary and jitter into periodic zero-velocity.

Decision contract:

- ``stale`` is False (a frame arrived within ``watchdog_sec``) → **"replay"**
  in BOTH modes: publish the last intents. Smooths dropped frames in single
  device; keeps the fuser's input fresh in dual device.
- ``stale`` is True (real loss, > ``watchdog_sec`` since the last frame):
  - single device (``stop_on_data_loss=False``): first tick → "zero" (one
    zero-velocity twist, then silent — the original behavior, not perpetual
    replay); afterwards → "halt".
  - dual device (``stop_on_data_loss=True``): "halt" (stay silent so the
    fuser's freshness watchdog takes over).
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
        True when the last frame is older than ``watchdog_sec`` (real loss).
    connected : bool
        Whether the adapter was receiving data before this loss.
    stop_on_data_loss : bool
        Dual-device mode switch (on real loss stay silent and let the fuser
        act; single device sends one zero then goes silent).

    Returns
    -------
    str
        One of ``"replay"`` (publish last intents), ``"zero"`` (publish one
        zero-velocity twist then go silent), or ``"halt"`` (publish nothing).
    """
    if not stale:
        return "replay"
    if stop_on_data_loss:
        return "halt"
    return "zero" if connected else "halt"

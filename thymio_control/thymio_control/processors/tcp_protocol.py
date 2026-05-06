"""TCP SOD/EOD packet parsing utilities.

Pure-function helpers for the Neuroimagen / Enobio SOD…EOD wire protocol.
No I/O, no state.  Can be used from adapters, tests, and offline scripts.

Protocol format
---------------
``SOD<seq>;<n_features>;<movement>;<f1>;...;<fn>;<artifact>;<unused>EOD``

Fields (semicolon-separated between SOD and EOD):
    0 : sequence number (int)
    1 : feature count  (int, typically 1)
    2 : movement flag  (float, legacy field)
    3…3+n : feature values
    3+n   : artifact flag
    3+n+1 : unused y value
"""
from __future__ import annotations

from typing import Dict


def extract_tcp_feature(packet: str) -> float:
    """Extract the feature value (field index 3) from an SOD/EOD packet.

    This is the strict variant used in unit tests: raises on any malformed
    input rather than silently returning a default.

    Parameters
    ----------
    packet : str
        A complete ``SOD…EOD`` packet string.

    Raises
    ------
    ValueError
        If the packet does not start with SOD / end with EOD, the payload
        is empty, or field 3 is not numeric.
    IndexError
        If the packet contains fewer than 4 semicolon-separated fields.
    """
    packet = packet.strip()
    if not packet.startswith("SOD") or not packet.endswith("EOD"):
        raise ValueError("TCP packet must start with SOD and end with EOD")

    body = packet[3:-3].strip()
    if not body:
        raise ValueError("TCP packet payload is empty")

    parts = [p.strip() for p in body.split(";")]
    if len(parts) <= 3:
        raise IndexError("TCP packet does not contain feature field at index 3")

    try:
        return float(parts[3])
    except ValueError as exc:
        raise ValueError(
            f"TCP feature field at index 3 is not numeric: {parts[3]!r}"
        ) from exc


def parse_sod_packet(packet: str) -> Dict[str, float]:
    """Parse an SOD…EOD packet into a metrics dict.

    Returns an empty dict if the packet is malformed or incomplete.
    All failures are swallowed — callers that need strict validation should
    use :func:`extract_tcp_feature` instead.

    Parameters
    ----------
    packet : str
        A complete ``SOD…EOD`` packet string.

    Returns
    -------
    dict
        Keys: ``packet_no``, ``feature_count``, ``movement``, ``feature``,
        ``feature_1`` … ``feature_n``, ``artifact``, ``current_y_unused``.
        Also sets ``feature_value`` as alias for ``feature_1`` when n==1.
    """
    packet = packet.strip()
    if not packet.startswith("SOD") or not packet.endswith("EOD"):
        return {}

    body = packet[3:-3].strip()
    if not body:
        return {}

    parts = [p.strip() for p in body.split(";") if p.strip() != ""]
    if len(parts) < 5:
        return {}

    try:
        packet_no     = int(float(parts[0]))
        feature_count = int(float(parts[1]))
        movement      = float(parts[2])
    except Exception:
        return {}

    try:
        feature = extract_tcp_feature(packet)
    except (IndexError, ValueError):
        return {}

    expected_len = 5 + feature_count
    if len(parts) < expected_len:
        return {}

    metrics: Dict[str, float] = {
        "packet_no":     float(packet_no),
        "feature_count": float(feature_count),
        "movement":      movement,
        "feature":       feature,
    }

    feature_values = parts[3: 3 + feature_count]
    for idx, value in enumerate(feature_values, start=1):
        try:
            metrics[f"feature_{idx}"] = float(value)
        except Exception:
            continue

    try:
        metrics["artifact"] = float(parts[3 + feature_count])
    except Exception:
        metrics["artifact"] = 0.0

    try:
        metrics["current_y_unused"] = float(parts[4 + feature_count])
    except Exception:
        metrics["current_y_unused"] = -1.0

    if feature_count == 1 and "feature_1" in metrics:
        metrics["feature_value"] = metrics["feature_1"]

    return metrics

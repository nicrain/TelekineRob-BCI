"""RawLslAdapter — pulls raw EEG samples from LSL and applies DSP.

This is the production migration of ``lsl_test/raw_lsl_adapter.py``
(validated in Phase 1).

Architecture
------------
    LSL inlet (raw ADC)
        ↓ pull_chunk
    StreamingBandPowerExtractor (sliding window Welch PSD)
        ↓ feed_chunk → List[Dict[int, BandPowers]]
    band_power_to_metrics (unit-normalised → µV²)
        ↓
    EegFrame  (source="lsl_raw")

Design notes
------------
- Device-agnostic: sample rate and channel count are read from ``StreamInfo``;
  no hard-coded device parameters.
- Unit auto-detection: reads ``source_unit`` from the LSL stream description
  (written by ``EdfToLslBridge``).  Falls back to ``config.source_unit``.
- Real-time first: when multiple windows are ready, only the **latest** result
  is returned to minimise control latency.

Blink detection has been moved out of the adapter.  Active blinks are now
detected directly from the policy metric (theta_beta / EI / alpha) in
``eeg_control_node.py``, using calibration p5/p95 as the normal-range
reference.  See ``_confirm_blink_metric()``.
"""
from __future__ import annotations

import logging
import time
from typing import List, Optional

import numpy as np

from thymio_control.adapters.base import BaseAdapter
from thymio_control.contracts import EegFrame
from thymio_control.processors.band_power import (
    BandPowers,
    DSPConfig,
    StreamingBandPowerExtractor,
    StreamingPreFilter,
    band_power_to_metrics,
    per_channel_metrics,
)


# Devices whose raw data needs pre-filtering before Welch PSD.
# headband (BCI Core-4): gpype applies bandpass + notch on Windows.
# Hybrid Black (UnicornPy): no built-in DSP — we compensate here.
_DEVICES_NEEDING_PRE_FILTER: set[str] = {"gtec_hybrid_black"}


class RawLslAdapter(BaseAdapter):
    """Pull raw EEG from an LSL stream, compute band powers, return EegFrame.

    Parameters
    ----------
    stream_type : str
        LSL stream type to resolve (e.g. ``"EEG"``).
    timeout : float
        Seconds to wait when discovering the stream.
    source_id : str, optional
        If provided, resolve by ``source_id`` instead of ``type`` for
        multi-device setups.
    config : DSPConfig, optional
        DSP parameters for the ``StreamingBandPowerExtractor``.
        ``source_unit`` is overridden by the stream description if present.
    """

    def __init__(
        self,
        stream_type: str = "EEG",
        timeout: float = 5.0,
        source_id: Optional[str] = None,
        config: Optional[DSPConfig] = None,
        debug_frames: int = 0,
    ) -> None:
        try:
            from pylsl import StreamInlet, resolve_byprop  # type: ignore
        except ImportError as exc:
            raise RuntimeError(
                "pylsl is required for RawLslAdapter. "
                "Install with: pip install pylsl"
            ) from exc

        if source_id:
            streams = resolve_byprop("source_id", source_id, timeout=timeout)
        else:
            streams = resolve_byprop("type", stream_type, timeout=timeout)

        if not streams:
            target = f"source_id={source_id}" if source_id else f"type={stream_type}"
            raise RuntimeError(f"No LSL stream found for {target}")

        self._inlet = StreamInlet(streams[0], max_chunklen=64)
        info = self._inlet.info()

        # Device parameters from StreamInfo — no hard-coding
        self._sample_rate  = int(info.nominal_srate())
        self._n_channels   = info.channel_count()
        self._stream_name  = info.name()

        # Channel labels from description
        self._channel_labels = self._read_channel_labels(info)

        # DSP config — honour stream-level source_unit if embedded
        self._cfg = config or DSPConfig()
        self._unit_from_stream = False
        desc = info.desc()
        stream_unit = desc.child_value("source_unit")
        if stream_unit:
            self._cfg.source_unit = stream_unit
            self._unit_from_stream = True
        elif config is None or config.source_unit == DSPConfig.source_unit:
            # source_unit came from hard-coded default — warn the user
            logging.getLogger(__name__).warning(
                "RawLslAdapter: source_unit not found in LSL stream description "
                "and no explicit config provided. Defaulting to '%s'. "
                "If your device outputs nV, set DSPConfig(source_unit='nV') "
                "to avoid a 10⁶× scaling error.",
                self._cfg.source_unit,
            )

        self._extractor = StreamingBandPowerExtractor(
            sample_rate=self._sample_rate,
            n_channels=self._n_channels,
            config=self._cfg,
        )

        # Pre-filter: only Hybrid Black (UnicornPy) needs it;
        # headband data from gpype arrives already filtered.
        self._pre_filter: Optional[StreamingPreFilter] = None
        if self._stream_name in _DEVICES_NEEDING_PRE_FILTER:
            self._pre_filter = StreamingPreFilter(
                sample_rate=self._sample_rate,
                n_channels=self._n_channels,
            )

        # Diagnostic probe (off by default, gated by the node's
        # dsp_debug_frames param): print the stream facts once, then the
        # first N frames' signal RMS + raw band powers (source_unit², before
        # the µV² conversion) + converted metrics. These three signals pin a
        # zero-metric device to a stage:
        #   rms≈0            → data never reaches the extractor (scaling / pull)
        #   rms real, raw≈0  → frequency mapping (declared vs actual sample rate)
        #   raw real, conv≈0 → source_unit mismatch between stream and data
        self._debug_remaining = int(debug_frames)
        if self._debug_remaining > 0:
            print(
                f"[dsp-debug] stream={self._stream_name} nominal_rate={self._sample_rate}Hz "
                f"ch={self._n_channels} source_unit={self._cfg.source_unit!r} "
                f"from_stream={self._unit_from_stream} labels={self._channel_labels}",
                flush=True,
            )

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def sample_rate(self) -> int:
        return self._sample_rate

    @property
    def n_channels(self) -> int:
        return self._n_channels

    @property
    def channel_labels(self) -> List[str]:
        return self._channel_labels

    # ------------------------------------------------------------------
    # BaseAdapter interface
    # ------------------------------------------------------------------

    def read_frame(self) -> Optional[EegFrame]:
        """Pull available samples and return an EegFrame if a window completed.

        Returns ``None`` if no complete window is available yet.
        """
        samples, _ = self._inlet.pull_chunk(timeout=0.0, max_samples=512)
        if not samples:
            return None

        # pull_chunk returns (n_samples, n_channels) — transpose to (n_ch, n_s)
        chunk = np.array(samples, dtype=np.float64).T
        if self._pre_filter is not None:
            self._pre_filter.apply(chunk)
        results = self._extractor.feed_chunk(chunk)
        if not results:
            return None

        # Use the latest result to minimise control latency
        latest = results[-1]

        # Global average band powers
        n = len(latest)
        avg_bp = BandPowers(
            delta=sum(bp.delta for bp in latest.values()) / n,
            theta=sum(bp.theta for bp in latest.values()) / n,
            alpha=sum(bp.alpha for bp in latest.values()) / n,
            beta =sum(bp.beta  for bp in latest.values()) / n,
            gamma=sum(bp.gamma for bp in latest.values()) / n,
        )
        metrics = band_power_to_metrics(avg_bp, source_unit=self._cfg.source_unit)

        # Per-channel lateralisation metrics
        metrics.update(
            per_channel_metrics(self._channel_labels, latest, self._cfg.source_unit)
        )

        if self._debug_remaining > 0:
            rms = float(np.sqrt(np.mean(chunk ** 2))) if chunk.size else 0.0
            ch_pows = " ".join(
                f"ch{i}=[t{latest[i].theta:.4g} a{latest[i].alpha:.4g} "
                f"b{latest[i].beta:.4g}]"
                for i in sorted(latest)
            )
            print(
                f"[dsp-debug] rms={rms:.4g} raw_avg="
                f"[d{avg_bp.delta:.4g} t{avg_bp.theta:.4g} a{avg_bp.alpha:.4g} "
                f"b{avg_bp.beta:.4g} g{avg_bp.gamma:.4g}] "
                f"conv=[alpha={metrics.get('alpha'):.4g} "
                f"beta={metrics.get('beta'):.4g} theta={metrics.get('theta'):.4g}] "
                f"{ch_pows}",
                flush=True,
            )
            self._debug_remaining -= 1

        return EegFrame(ts=time.time(), source="lsl_raw", metrics=metrics)

    # ------------------------------------------------------------------
    # Lifecycle helpers
    # ------------------------------------------------------------------

    def flush(self) -> list:
        """Flush the internal DSP buffer (discard incomplete window)."""
        return self._extractor.flush()

    def reset(self) -> None:
        """Reset the internal DSP buffer and pre-filter state."""
        self._extractor.reset()
        if self._pre_filter is not None:
            self._pre_filter.reset()

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    @staticmethod
    def _read_channel_labels(info) -> List[str]:
        """Try to parse channel labels from the LSL stream description."""
        desc = info.desc()
        labels_str = desc.child_value("channel_labels")
        if labels_str:
            return [s.strip() for s in labels_str.split(",")]
        return [f"ch{i}" for i in range(info.channel_count())]

"""Band power extraction from EEG signals.

This module is the **production copy** migrated from ``lsl_test/eeg_processor.py``
(Phase 1 experimental area).  It is the single source of truth for the
production pipeline.

Algorithm
---------
Uses Welch's method with a Hanning window for power spectral density
estimation.  Falls back to a pure-NumPy Welch implementation if scipy is
unavailable, so the package can run without a full scientific stack.

All five standard frequency bands (delta, theta, alpha, beta, gamma) are
computed for every channel.  The policy layer decides how to aggregate across
channels.

Unit convention
---------------
``band_power_to_metrics()`` always outputs values in **µV²**, regardless of
the device's native voltage unit.  Pass *source_unit* to convert correctly.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

import numpy as np


# ---------------------------------------------------------------------------
# Band definitions
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class BandPowers:
    """Five standard EEG frequency-band powers (in source_unit²)."""

    delta: float
    theta: float
    alpha: float
    beta:  float
    gamma: float


# Band definitions: (low_freq_Hz, high_freq_Hz)
BANDS: Dict[str, tuple] = {
    "delta": (1.0,  4.0),
    "theta": (4.0,  8.0),
    "alpha": (8.0,  13.0),
    "beta":  (13.0, 30.0),
    "gamma": (30.0, 100.0),
}

# ---------------------------------------------------------------------------
# Unit conversion
# ---------------------------------------------------------------------------

# Factors to convert 1 amplitude unit → 1 µV
_UNIT_TO_UV: Dict[str, float] = {
    "nV":  0.001,
    "µV":  1.0,
    "uV":  1.0,
    "mV":  1_000.0,
    "V":   1_000_000.0,
}


def convert_power_to_uv2(value: float, source_unit: str) -> float:
    """Convert a band-power value from *source_unit*² to µV².

    Power scales as amplitude², so the amplitude factor is squared.

    Parameters
    ----------
    value : float
        Band power in source_unit² (e.g. nV²).
    source_unit : str
        The amplitude unit of the source signal (e.g. ``"nV"``, ``"µV"``).

    Raises
    ------
    ValueError
        If *source_unit* is not in the supported unit table.
    """
    factor = _UNIT_TO_UV.get(source_unit)
    if factor is None:
        raise ValueError(
            f"Unknown source_unit {source_unit!r}. "
            f"Supported: {list(_UNIT_TO_UV.keys())}"
        )
    return value * (factor ** 2)


# ---------------------------------------------------------------------------
# Internal PSD helpers
# ---------------------------------------------------------------------------

def _hanning_window(n: int) -> np.ndarray:
    """Return an *n*-point Hanning window."""
    n_arr = np.arange(n)
    return 0.5 * (1 - np.cos(2 * np.pi * n_arr / (n - 1)))


def _manual_welch_psd(
    signal: np.ndarray,
    fs: int,
    nperseg: Optional[int] = None,
    noverlap: Optional[int] = None,
) -> tuple[np.ndarray, np.ndarray]:
    """Compute PSD via Welch's method using pure NumPy.

    Returns ``(freqs, psd)`` where *psd* is in units of signal²/Hz.
    Used as fallback when scipy is not installed.
    """
    n = len(signal)
    if nperseg is None:
        nperseg = min(n, 256)
    if noverlap is None:
        noverlap = nperseg // 2

    window = _hanning_window(nperseg)
    step = nperseg - noverlap

    freqs = np.fft.rfftfreq(nperseg, 1.0 / fs)
    psd = np.zeros(len(freqs))

    n_ensembles = 0
    start = 0
    while start + nperseg <= n:
        segment = signal[start: start + nperseg]
        windowed = segment * window
        spectrum = np.fft.rfft(windowed, n=nperseg)
        psd += np.abs(spectrum) ** 2
        n_ensembles += 1
        start += step

    if n_ensembles == 0:
        return freqs, psd

    psd /= n_ensembles
    psd /= fs
    return freqs, psd


def _band_power_from_psd(
    freqs: np.ndarray,
    psd: np.ndarray,
    band: tuple[float, float],
) -> float:
    """Integrate PSD between *band* edges to obtain band power."""
    low, high = band
    mask = (freqs >= low) & (freqs <= high)
    if not np.any(mask):
        return 0.0
    df = freqs[1] - freqs[0] if len(freqs) > 1 else 1.0
    return float(np.sum(psd[mask]) * df)


# ---------------------------------------------------------------------------
# Public PSD API — scipy-accelerated with NumPy fallback
# ---------------------------------------------------------------------------

try:
    from scipy.signal import welch as _scipy_welch  # type: ignore

    def compute_band_powers(
        signal: np.ndarray,
        sample_rate: int,
        *,
        window_sec: float = 1.0,
        nperseg: Optional[int] = None,
        noverlap: Optional[int] = None,
        bands: Optional[Dict[str, tuple]] = None,
    ) -> BandPowers:
        """Compute all five EEG band powers using scipy Welch's method."""
        if nperseg is None:
            nperseg = min(int(window_sec * sample_rate), 256)
        if noverlap is None:
            noverlap = nperseg // 2
        freqs, psd = _scipy_welch(signal, fs=sample_rate, nperseg=nperseg, noverlap=noverlap)
        b = {**BANDS, **(bands or {})}
        return BandPowers(
            delta=_band_power_from_psd(freqs, psd, b["delta"]),
            theta=_band_power_from_psd(freqs, psd, b["theta"]),
            alpha=_band_power_from_psd(freqs, psd, b["alpha"]),
            beta =_band_power_from_psd(freqs, psd, b["beta"]),
            gamma=_band_power_from_psd(freqs, psd, b["gamma"]),
        )

except ImportError:
    def compute_band_powers(  # type: ignore[misc]
        signal: np.ndarray,
        sample_rate: int,
        *,
        window_sec: float = 1.0,
        nperseg: Optional[int] = None,
        noverlap: Optional[int] = None,
        bands: Optional[Dict[str, tuple]] = None,
    ) -> BandPowers:
        """Compute all five EEG band powers using a pure-NumPy fallback."""
        if nperseg is None:
            nperseg = min(int(window_sec * sample_rate), 256)
        if noverlap is None:
            noverlap = nperseg // 2
        freqs, psd = _manual_welch_psd(signal, sample_rate, nperseg, noverlap)
        b = {**BANDS, **(bands or {})}
        return BandPowers(
            delta=_band_power_from_psd(freqs, psd, b["delta"]),
            theta=_band_power_from_psd(freqs, psd, b["theta"]),
            alpha=_band_power_from_psd(freqs, psd, b["alpha"]),
            beta =_band_power_from_psd(freqs, psd, b["beta"]),
            gamma=_band_power_from_psd(freqs, psd, b["gamma"]),
        )


def compute_channel_band_powers(
    signals: np.ndarray,
    channel_labels: List[str],
    sample_rate: int,
    *,
    window_sec: float = 1.0,
    bands: Optional[Dict[str, tuple]] = None,
) -> Dict[str, BandPowers]:
    """Compute band powers for every channel.

    Parameters
    ----------
    signals : np.ndarray
        Shape ``(n_channels, n_samples)``.
    channel_labels : list of str
        Label for each channel row.
    sample_rate : int
        Sampling rate in Hz.

    Returns
    -------
    dict mapping channel label → BandPowers
    """
    result: Dict[str, BandPowers] = {}
    for ch_idx, label in enumerate(channel_labels):
        if ch_idx >= len(signals):
            continue
        result[label] = compute_band_powers(
            signals[ch_idx], sample_rate,
            window_sec=window_sec, bands=bands,
        )
    return result


def band_power_to_metrics(
    bp: BandPowers,
    source_unit: str = "µV",
) -> Dict[str, float]:
    """Convert BandPowers to an ``EegFrame``-compatible metrics dict.

    Only absolute power values (in µV²) are returned here.  Ratio metrics
    such as ``theta_beta`` and ``alpha_beta`` are **not** included — they
    are computed by :func:`processors.enrich.enrich_features` to avoid
    duplicating the computation for every call site.

    Parameters
    ----------
    bp : BandPowers
        Band powers in source_unit².
    source_unit : str
        Amplitude unit of the source signal (e.g. ``"nV"`` for Enobio,
        ``"µV"`` for most other devices).
    """
    return {
        "alpha": convert_power_to_uv2(bp.alpha, source_unit),
        "beta":  convert_power_to_uv2(bp.beta,  source_unit),
        "theta": convert_power_to_uv2(bp.theta, source_unit),
        "delta": convert_power_to_uv2(bp.delta, source_unit),
        "gamma": convert_power_to_uv2(bp.gamma, source_unit),
    }



# ---------------------------------------------------------------------------
# Streaming (real-time) DSP
# ---------------------------------------------------------------------------

@dataclass
class DSPConfig:
    """Configuration for DSP processing, shared by offline and streaming modes.

    All parameters can be overridden via the YAML ``dsp_config`` section.
    """

    window_sec:  float = 1.0
    hop_sec:     float = 0.5
    nperseg:     Optional[int] = None    # None → auto: min(window_samples, 256)
    noverlap:    Optional[int] = None    # None → auto: nperseg // 2
    bands:       Optional[Dict[str, tuple]] = None  # None → use BANDS
    source_unit: str = "µV"             # amplitude unit of the source signal


class StreamingBandPowerExtractor:
    """Sliding-window band power extractor for real-time EEG streams.

    Device-agnostic: only depends on ``sample_rate`` and ``n_channels``.
    Accumulates samples in a ring buffer and emits ``BandPowers`` for each
    channel every time the hop criterion is met.

    Usage::

        ext = StreamingBandPowerExtractor(sample_rate=500, n_channels=20)
        for chunk in lsl_inlet:             # chunk: (n_channels, n_new)
            results = ext.feed_chunk(chunk)
            for frame in results:
                print(frame)  # Dict[int, BandPowers]

    Parameters
    ----------
    sample_rate : int
        Sampling rate in Hz (e.g. 250 for Unicorn, 500 for Enobio).
    n_channels : int
        Number of EEG channels.
    config : DSPConfig, optional
        DSP parameters; module defaults are used if not provided.
    """

    def __init__(
        self,
        sample_rate: int,
        n_channels: int,
        config: Optional[DSPConfig] = None,
    ) -> None:
        if sample_rate <= 0:
            raise ValueError(f"sample_rate must be positive, got {sample_rate}")
        if n_channels <= 0:
            raise ValueError(f"n_channels must be positive, got {n_channels}")

        self._sample_rate = sample_rate
        self._n_channels  = n_channels
        self._cfg         = config or DSPConfig()
        self._bands       = self._cfg.bands or BANDS

        self._window_samples = int(self._cfg.window_sec * sample_rate)
        self._hop_samples    = int(self._cfg.hop_sec    * sample_rate)

        if self._window_samples <= 0:
            raise ValueError(
                f"window_sec={self._cfg.window_sec} too small for "
                f"sample_rate={sample_rate}"
            )
        if self._hop_samples <= 0:
            raise ValueError(
                f"hop_sec={self._cfg.hop_sec} too small for "
                f"sample_rate={sample_rate}"
            )

        # Ring buffer: shape (n_channels, window_samples)
        self._buf       = np.zeros((n_channels, self._window_samples), dtype=np.float64)
        self._buf_len   = 0   # valid samples in buffer
        self._since_hop = 0   # samples since last emission

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
    def window_samples(self) -> int:
        return self._window_samples

    @property
    def hop_samples(self) -> int:
        return self._hop_samples

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def feed_chunk(self, chunk: np.ndarray) -> List[Dict[int, BandPowers]]:
        """Feed a new chunk of samples and return any completed windows.

        Parameters
        ----------
        chunk : np.ndarray
            Shape ``(n_channels, n_new_samples)``.  A 1-D array is treated
            as single-channel input.

        Returns
        -------
        list of dict
            Each element maps channel index → BandPowers.  Empty list if no
            window has been completed yet.
        """
        if chunk.ndim == 1:
            chunk = chunk.reshape(1, -1)

        n_ch, n_new = chunk.shape
        if n_ch != self._n_channels:
            raise ValueError(
                f"chunk has {n_ch} channels, expected {self._n_channels}"
            )

        results: List[Dict[int, BandPowers]] = []
        consumed = 0

        while consumed < n_new:
            space = self._window_samples - self._buf_len
            take  = min(space, n_new - consumed)

            self._buf[:, self._buf_len: self._buf_len + take] = (
                chunk[:, consumed: consumed + take]
            )
            self._buf_len   += take
            self._since_hop += take
            consumed        += take

            # Emit if buffer is full AND hop criterion met
            if (
                self._buf_len   >= self._window_samples
                and self._since_hop >= self._hop_samples
            ):
                results.append(self._compute_current_window())
                self._advance_buffer()

        return results

    def flush(self) -> List[Dict[int, BandPowers]]:
        """Discard incomplete tail data and reset the buffer.

        Welch's method requires at least ``nperseg`` samples for meaningful
        spectral estimation; partial windows are dropped to avoid polluting
        control signals with low-resolution estimates.
        """
        self.reset()
        return []

    def reset(self) -> None:
        """Clear the internal buffer without emitting anything."""
        self._buf[:]    = 0.0
        self._buf_len   = 0
        self._since_hop = 0

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _compute_current_window(self) -> Dict[int, BandPowers]:
        result: Dict[int, BandPowers] = {}
        for ch in range(self._n_channels):
            signal = self._buf[ch, : self._window_samples]
            result[ch] = compute_band_powers(
                signal,
                self._sample_rate,
                window_sec=self._cfg.window_sec,
                nperseg=self._cfg.nperseg,
                noverlap=self._cfg.noverlap,
                bands=self._bands,
            )
        return result

    def _advance_buffer(self) -> None:
        """Slide the buffer forward by hop_samples.

        Note: uses numpy slicing (copy).  For <20 channels at Phase 2
        this is negligible.  If profiling at 64+ channels reveals CPU
        pressure, replace with a zero-copy circular buffer.
        """
        keep = self._window_samples - self._hop_samples
        if keep > 0:
            self._buf[:, :keep] = self._buf[:, self._hop_samples: self._window_samples]
        self._buf_len   = keep
        self._since_hop = 0

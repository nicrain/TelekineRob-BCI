import { useEffect, useMemo, useRef, useState } from 'react';
import ReactECharts from 'echarts-for-react';
import { api, getWsUrl } from './api';

/* ── Constants ─────────────────────────────────────────── */
const MAX_POINTS = 140;

const CHANNEL_PRESETS = {
  gtec_hybrid: ['Fz', 'C3', 'Cz', 'C4', 'Pz', 'PO7', 'Oz', 'PO8'],
  gtec_headband: ['F8', 'Fp2', 'Fp1', 'F7'],
};

const METRIC_OPTIONS = [
  { value: 'alpha', label: 'Alpha', formula: 'α' },
  { value: 'tbr',   label: 'TBR',   formula: 'θ/β' },
  { value: 'ei',    label: 'EI',    formula: 'β/(α+θ)' },
];

/* ── Helpers ───────────────────────────────────────────── */
function pushPoint(arr, value) {
  const out = [...arr, value];
  if (out.length > MAX_POINTS) out.shift();
  return out;
}

/** ~95th percentile of positive values — used as y-axis max to suppress outlier spikes */
function p95Max(...arrays) {
  const all = [];
  for (const arr of arrays) {
    for (const v of arr) {
      if (v != null && isFinite(v) && v > 0) all.push(v);
    }
  }
  if (all.length < 10) return null;
  all.sort((a, b) => a - b);
  return all[Math.floor(all.length * 0.95)];
}

/** Abbreviate large axis labels: 1,234,567 → "1.2M", 1,234 → "1.2k" */
function fmtAxis(val) {
  const abs = Math.abs(val);
  if (abs >= 1e6) return (val / 1e6).toFixed(1) + 'M';
  if (abs >= 1e3) return (val / 1e3).toFixed(1) + 'k';
  if (abs >= 1) return val.toFixed(1);
  return val.toFixed(3);
}

/* ── Chart options (O5: extracted for reuse across both columns) ── */
const METRIC_LABELS = { alpha: 'Alpha (α)', tbr: 'TBR (θ/β)', ei: 'EI (β/(α+θ))' };
const METRIC_DATA_KEY = { alpha: 'alpha', tbr: 'ratio', ei: 'focus' };

/** Build both ECharts options for one device column.
 *  Extracted so each column can call it with its own series/metric/calib
 *  (batch 2 wires series2; the single-device path calls it once).
 *  @param {Object} series   { t, alpha, theta, beta, ratio, focus, speed, steer }
 *  @param {string} metric   'alpha' | 'tbr' | 'ei'
 *  @param {number} calibOffset / calibScale / calibrating — calibration display
 *  @param {string} theme    'dark' | 'light'
 */
function useChartOptions(series, metric, calibOffset, calibScale, calibrating, theme) {
  const isLight = theme === 'light';
  return useMemo(() => {
    const waveOption = {
      backgroundColor: 'transparent',
      tooltip: { trigger: 'axis', backgroundColor: isLight ? '#fff' : '#2a2a2a', borderColor: isLight ? '#ddd' : '#444', textStyle: { color: isLight ? '#333' : '#ddd' } },
      legend: { textStyle: { color: isLight ? '#555' : '#aaa' }, top: 2 },
      grid: { left: 65, right: 16, top: 36, bottom: 24 },
      xAxis: { type: 'category', data: series.t, axisLabel: { color: isLight ? '#999' : '#888', fontSize: 10 } },
      yAxis: {
        type: 'value',
        max: p95Max(series.alpha, series.theta, series.beta),
        axisLabel: { color: isLight ? '#999' : '#888', fontSize: 10, formatter: fmtAxis },
      },
      series: [
        { name: 'alpha', type: 'line', smooth: true, showSymbol: false, data: series.alpha },
        { name: 'theta', type: 'line', smooth: true, showSymbol: false, data: series.theta },
        { name: 'beta',  type: 'line', smooth: true, showSymbol: false, data: series.beta  },
      ],
      color: isLight ? ['#DA291C', '#F6E500', '#000000'] : ['#DA291C', '#F6E500', '#CCCCCC'],
      animation: false,
    };

    const calibHigh = calibOffset + calibScale;
    const showCalib = calibrating || calibOffset !== 0 || calibScale !== 1;
    const featureOption = {
      backgroundColor: 'transparent',
      tooltip: { trigger: 'axis', backgroundColor: isLight ? '#fff' : '#2a2a2a', borderColor: isLight ? '#ddd' : '#444', textStyle: { color: isLight ? '#333' : '#ddd' } },
      legend: { textStyle: { color: isLight ? '#555' : '#aaa' }, top: 2 },
      grid: { left: 65, right: 16, top: 36, bottom: 24 },
      xAxis: { type: 'category', data: series.t, axisLabel: { color: isLight ? '#999' : '#888', fontSize: 10 } },
      yAxis: {
        type: 'value',
        ...(showCalib ? { min: calibOffset, max: calibHigh } : { max: p95Max(series[METRIC_DATA_KEY[metric]]) }),
        axisLabel: { color: isLight ? '#999' : '#888', fontSize: 10, formatter: fmtAxis },
      },
      series: [
        {
          name: METRIC_LABELS[metric], type: 'line', smooth: true, showSymbol: false,
          data: series[METRIC_DATA_KEY[metric]],
          ...(showCalib ? {
            markLine: {
              silent: true, symbol: 'none',
              lineStyle: { type: 'dashed', color: isLight ? '#888' : '#aaa', width: 1 },
              label: { show: true, position: 'start', formatter: '{b}', color: isLight ? '#888' : '#999', fontSize: 10 },
              data: [
                { yAxis: calibOffset, name: `min=${calibOffset.toFixed(1)}` },
                { yAxis: calibHigh,  name: `max=${(calibOffset+calibScale).toFixed(1)}` },
              ],
            },
          } : {}),
        },
      ],
      color: [calibrating ? '#888' : '#DA291C'],
      animation: false,
      ...(showCalib ? {
        graphic: [
          {
            type: 'text',
            right: 10, top: 6,
            style: {
              text: `min=${calibOffset.toFixed(1)}  max=${(calibOffset + calibScale).toFixed(1)}`,
              fill: isLight ? '#aaa' : '#666',
              fontSize: 11,
            },
          },
        ],
      } : {}),
    };

    return { waveOption, featureOption };
  }, [series, metric, calibOffset, calibScale, calibrating, theme]);
}

/* O22 (b): lsl_source_id is the persisted source of truth. brand is a
 * frontend-only selector: forward (save) maps brand → source_id, and on
 * config load we infer the brand back from source_id (the backend drops
 * the brand field, so it can never be read back directly). */
const INIT_SERIES = { t: [], alpha: [], theta: [], beta: [], ratio: [], focus: [], speed: [], steer: [] };

const BRAND_TO_SOURCE_ID = {
  gtec_hybrid: 'gtec_hybrid_black',
  gtec_headband: 'gtec_bci_core4',
};
const SOURCE_ID_TO_BRAND = {
  gtec_hybrid_black: 'gtec_hybrid',
  gtec_bci_core4: 'gtec_headband',
};

/**
 * Per-device calibration state (design §5.5.1/§5.5.4, O5 continuation).
 * Instantiate once per device: useCalibration('eeg', …) / useCalibration('eeg2', …).
 *
 * O19 absorbed here: the countdown interval is driven by a ref (never created
 * inside a setState updater), both the countdown and the poll intervals are
 * stored in refs, and reset() clears both — Stop can no longer leak a poll.
 *
 * @param {'eeg'|'eeg2'} device  config block key (used for patch + poll read)
 * @param {Function} setFeedback  App's feedback setter (for save errors)
 * @param {Function} onDone       called after calibration finishes — App clears
 *                                charts and auto-stops in dual mode (§5.5.4)
 */
function useCalibration(device, setFeedback, onDone) {
  const [calibrating, setCalibrating] = useState(false);
  const [calibPhase, setCalibPhase] = useState(null);       // 'preparing' | 'counting'
  const [calibCountdown, setCalibCountdown] = useState(30);
  const [calibOffset, setCalibOffset] = useState(0);
  const calibOffsetRef = useRef(0);
  calibOffsetRef.current = calibOffset;
  const [calibScale, setCalibScale] = useState(1);
  const countRef = useRef(30);       // countdown value, readable inside the interval
  const timerRef = useRef(null);     // countdown interval
  const pollRef = useRef(null);      // "waiting for node to write calibrate=false" poll
  const waitingRef = useRef(false);  // true between beginWaiting() and first frame

  function clearTimers() {
    if (timerRef.current) { clearInterval(timerRef.current); timerRef.current = null; }
    if (pollRef.current)  { clearInterval(pollRef.current);  pollRef.current = null; }
  }

  function syncCalib(offset, scale) {
    if (offset != null) setCalibOffset(Number(offset));
    if (scale != null) setCalibScale(Number(scale));
  }

  /** User clicked Calibrate — arm the countdown; it starts on the first frame. */
  function beginWaiting() {
    waitingRef.current = true;
    setCalibrating(true);
    setCalibPhase('preparing');
    setCalibCountdown(30);
    countRef.current = 30;
  }

  /** First analysis frame for this device arrived → start the 30s countdown. */
  function startCountdown() {
    waitingRef.current = false;
    setCalibPhase('counting');
    timerRef.current = setInterval(() => {
      countRef.current -= 1;
      setCalibCountdown(countRef.current);
      if (countRef.current <= 0) {
        clearInterval(timerRef.current);
        timerRef.current = null;
        // Poll until the node writes its params file (calibrate → false).
        pollRef.current = setInterval(() => {
          api.get('/api/config', { params: { reload: true } })
            .then((r) => {
              const dev = r.data?.config?.[device];
              if (!dev?.calibrate) {
                clearInterval(pollRef.current);
                pollRef.current = null;
                finishCalibration(dev || {});
              }
            })
            .catch(() => {
              clearInterval(pollRef.current);
              pollRef.current = null;
              reset();
            });
        }, 500);
      }
    }, 1000);
  }

  function finishCalibration(eeg) {
    clearTimers();
    setCalibrating(false);
    setCalibPhase(null);
    if (eeg?.calib_offset != null) setCalibOffset(Number(eeg.calib_offset));
    if (eeg?.calib_scale != null) setCalibScale(Number(eeg.calib_scale));
    if (onDone) onDone();
  }

  /** Cancel (Stop pressed / poll failed): clear both intervals + waiting flag. */
  function reset() {
    clearTimers();
    waitingRef.current = false;
    setCalibrating(false);
    setCalibPhase(null);
    setCalibCountdown(30);
    countRef.current = 30;
  }

  async function updateCalibMin(raw) {
    const v = Number(raw);
    if (isNaN(v)) return;
    setCalibOffset(v);
    try {
      await api.put('/api/config', { patch: { [device]: { calib_offset: v } } });
    } catch (err) { setFeedback(`Save offset failed: ${err.message}`); }
  }

  async function updateCalibMax(raw) {
    const v = Number(raw);
    if (isNaN(v)) return;
    const scale = Math.max(0.001, v - calibOffsetRef.current);
    setCalibScale(scale);
    try {
      await api.put('/api/config', { patch: { [device]: { calib_scale: scale } } });
    } catch (err) { setFeedback(`Save scale failed: ${err.message}`); }
  }

  return {
    calibrating, calibPhase, calibCountdown, calibOffset, calibScale,
    calibOffsetRef, waitingRef, timerRef, pollRef,
    syncCalib, beginWaiting, startCountdown, finishCalibration, reset,
    updateCalibMin, updateCalibMax,
  };
}

/* ── Hero: Thymio robot icon ─────────────────────────────── */
function HeroEmblem() {
  return (
    <div className="hero-emblem">
      <img
        src="/thymio-logo.png"
        alt="Thymio"
      />
    </div>
  );
}

/* ── Camera Panel ──────────────────────────────────────── */
function CameraPanel() {
  const [frame, setFrame] = useState(null);
  const [camWsConnected, setCamWsConnected] = useState(false);
  const [camError, setCamError] = useState(null);
  const camWsRef = useRef(null);

  useEffect(() => {
    const wsUrl = (import.meta.env.VITE_API_BASE || '').replace(/^http/, 'ws') + '/ws/gazebo_frame';
    let cancelled = false;
    let retryTimer = null;

    const connect = () => {
      if (cancelled) return;
      const ws = new WebSocket(wsUrl);
      camWsRef.current = ws;

      ws.onopen  = () => { setCamWsConnected(true); setCamError(null); };
      ws.onclose = () => {
        setCamWsConnected(false);
        if (!cancelled) {
          retryTimer = window.setTimeout(connect, 1000);
        }
      };
      ws.onerror = () => { setCamError('connection error'); };
      ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        if (data.error) {
          setCamError(data.error);
          return;
        }
        if (data.image) {
          setFrame(`data:image/jpeg;base64,${data.image}`);
          setCamError(null);
        }
      };
    };

    connect();
    return () => {
      cancelled = true;
      if (retryTimer) window.clearTimeout(retryTimer);
      if (camWsRef.current) camWsRef.current.close();
    };
  }, []);

  return (
    <div className="camera-panel">
      <div className="camera-header">
        <span className="section-label">02b — Gazebo View</span>
        <div className={`cam-status-dot ${camWsConnected && !camError ? 'ok' : 'warn'}`} />
        <span className="cam-status-text">
          {camWsConnected ? (camError ? camError : 'live') : 'connecting…'}
        </span>
      </div>
      <div className="camera-frame-wrapper">
        {frame
          ? <img src={frame} alt="Gazebo overhead view" className="camera-frame" />
          : <div className="camera-placeholder">
              {camError ? `Camera: ${camError}` : 'Waiting for stream…'}
            </div>
        }
      </div>
    </div>
  );
}

/* ── Teleop Panel (directional controls) ───────────── */
const DIR_LABELS = {
  forward:  '▲',
  backward: '▼',
  left:     '◀',
  right:    '▶',
  stop:     '■',
};

function TeleopPanel({ teleopWsRef, topic, connected }) {
  const [activeDir, setActiveDir] = useState(null);
  const [ackMsg, setAckMsg] = useState('');
  const activeDirRef = useRef(null);
  const watchdogRef = useRef(null);

  function send(dir) {
    if (!teleopWsRef.current || teleopWsRef.current.readyState !== WebSocket.OPEN) return;
    teleopWsRef.current.send(JSON.stringify({ direction: dir }));
  }

  function handleDirDown(dir) {
    setActiveDir(dir);
    activeDirRef.current = dir;
    send(dir);
    // Clear any pending watchdog
    if (watchdogRef.current) clearTimeout(watchdogRef.current);
  }

  function handleDirUp() {
    setActiveDir(null);
    activeDirRef.current = null;
    send('stop');
    // Start watchdog: resend stop after 200ms in case it was lost
    if (watchdogRef.current) clearTimeout(watchdogRef.current);
    watchdogRef.current = setTimeout(() => {
      // Only resend if still not pressing any button
      if (activeDirRef.current === null) {
        send('stop');
      }
    }, 200);
  }

  const dirs = [
    { dir: 'forward',  row: 0, col: 1 },
    { dir: 'left',      row: 1, col: 0 },
    { dir: 'stop',      row: 1, col: 1 },
    { dir: 'right',     row: 1, col: 2 },
    { dir: 'backward', row: 2, col: 1 },
  ];

  return (
    <div className="teleop-panel">
      <div className="teleop-header">
        <span className="section-label">03 — Teleop Controls</span>
        <span className={`teleop-ws-status ${connected ? 'ok' : 'warn'}`}>
          {connected ? `WS connected — ${topic}` : 'WS disconnected'}
        </span>
      </div>
      <div
        className="teleop-grid"
        style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 60px)', gridTemplateRows: 'repeat(3, 60px)', gap: 4 }}
      >
        {dirs.map(({ dir, row, col }) => (
          <button
            key={dir}
            className={`teleop-btn${activeDir === dir ? ' active' : ''}`}
            style={{ gridRow: row + 1, gridColumn: col + 1 }}
            onMouseDown={() => handleDirDown(dir)}
            onMouseUp={handleDirUp}
            onMouseLeave={activeDir === dir ? handleDirUp : undefined}
            onTouchStart={(e) => { e.preventDefault(); handleDirDown(dir); }}
            onTouchEnd={(e) => { e.preventDefault(); handleDirUp(); }}
          >
            {DIR_LABELS[dir]}
          </button>
        ))}
      </div>
      {ackMsg && <div className="teleop-ack">{ackMsg}</div>}
      <div className="teleop-hint">Click / tap buttons above</div>
    </div>
  );
}

/* ── Cascade Select (styled native <select>) ─────────── */
function CascadeSelect({ label, value, onChange, options, disabled }) {
  return (
    <div className={`cascade-group${disabled ? ' disabled' : ''}`}>
      <span className="cascade-label">{label}</span>
      <select
        className="cascade-select"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        disabled={disabled}
      >
        {options.map((opt) => (
          <option key={opt.value} value={opt.value} disabled={opt.disabled}>
            {opt.label}
          </option>
        ))}
      </select>
    </div>
  );
}

/* ── Channel Picker (multi-select with popover) ──────── */
function ChannelPicker({ channels, selected, onChange, disabled }) {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);

  useEffect(() => {
    function handleClickOutside(e) {
      if (ref.current && !ref.current.contains(e.target)) setOpen(false);
    }
    if (open) document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [open]);

  function toggleChannel(idx) {
    onChange(
      selected.includes(idx)
        ? selected.filter((i) => i !== idx)
        : [...selected, idx]
    );
  }

  function selectAll() {
    onChange(channels.map((_, i) => i));
  }

  function selectNone() {
    onChange([]);
  }

  return (
    <div className={`cascade-group${disabled ? ' disabled' : ''}`} ref={ref}>
      <span className="cascade-label">Channels</span>
      <button
        type="button"
        className="cascade-select channel-picker-trigger"
        onClick={() => !disabled && setOpen(!open)}
        disabled={disabled}
      >
        {selected.length}/{channels.length}
      </button>
      {open && (
        <div className="channel-picker-popover">
          <div className="channel-picker-actions">
            <button type="button" className="ch-action" onClick={selectAll}>All</button>
            <button type="button" className="ch-action" onClick={selectNone}>None</button>
          </div>
          <div className="channel-picker-grid">
            {channels.map((ch, idx) => (
              <label key={idx} className="channel-checkbox">
                <input
                  type="checkbox"
                  checked={selected.includes(idx)}
                  onChange={() => toggleChannel(idx)}
                />
                <span>{ch}</span>
              </label>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

/* ── Control Vector (SVG arrow visualization) ─────────── */
const SVG_SIZE = 200;
const CX = SVG_SIZE / 2;
const CY = SVG_SIZE / 2;
const MIN_LEN = 20;
const MAX_LEN = 80;
const BASE_COLOR = '#555';
const RESULT_COLOR = '#DA291C';

function lerp(min, max, t) {
  return min + Math.max(0, Math.min(1, t)) * (max - min);
}

function BigArrow({ x, y, color, opacity, headRatio }) {
  const len = Math.sqrt(x * x + y * y);
  if (len < 1) return null;
  const angle = Math.atan2(y, x);
  const headLen = len * headRatio;
  const headWidth = headLen * 0.7;
  const bodyWidth = 6;
  const cos = Math.cos(angle);
  const sin = Math.sin(angle);
  const perpX = -sin;
  const perpY = cos;
  const tipX = CX + x;
  const tipY = CY + y;
  const baseX = CX;
  const baseY = CY;
  const neckX = tipX - headLen * cos;
  const neckY = tipY - headLen * sin;
  const bodyPoly = [
    `${baseX + perpX * bodyWidth},${baseY + perpY * bodyWidth}`,
    `${neckX + perpX * bodyWidth},${neckY + perpY * bodyWidth}`,
    `${neckX - perpX * bodyWidth},${neckY - perpY * bodyWidth}`,
    `${baseX - perpX * bodyWidth},${baseY - perpY * bodyWidth}`,
  ].join(' ');
  const headPoly = [
    `${tipX},${tipY}`,
    `${neckX + perpX * headWidth},${neckY + perpY * headWidth}`,
    `${neckX - perpX * headWidth},${neckY - perpY * headWidth}`,
  ].join(' ');
  return (
    <g opacity={opacity}>
      <polygon points={bodyPoly} fill={color} />
      <polygon points={headPoly} fill={color} />
    </g>
  );
}

function ControlVector({ speed, steer, role, steerDirection }) {
  // speed: 0..1 (no backward), steer: 0..1 (0.5=center)
  const clampedSpeed = Math.max(0, Math.min(1, speed));

  // Forward arrow
  const fwdLen = lerp(MIN_LEN, MAX_LEN, clampedSpeed);

  // Steer magnitude from intent (0.5=no turn, 1.0=max turn)
  const steerMag = Math.abs(steer - 0.5) * 2;  // 0..1
  const steerLen = lerp(MIN_LEN, MAX_LEN, steerMag);

  // Direction: +1 = right, -1 = left, 0 = no direction (show both dimmed)
  const showLeft  = steerDirection < 0 && steerMag > 0.03;
  const showRight = steerDirection > 0 && steerMag > 0.03;

  const isSpeed = role === 'speed';

  return (
    <svg width={SVG_SIZE} height={SVG_SIZE} viewBox={`0 0 ${SVG_SIZE} ${SVG_SIZE}`} className="control-vector-svg">
      {isSpeed ? (
        <>
          {/* Speed role: forward arrow only, fill by percentage */}
          <BigArrow x={0} y={-fwdLen} color={BASE_COLOR} opacity={0.18} headRatio={0.35} />
          <BigArrow x={0} y={-lerp(MIN_LEN, MAX_LEN, clampedSpeed)} color={RESULT_COLOR} opacity={clampedSpeed > 0.03 ? 0.90 : 0} headRatio={0.35} />
        </>
      ) : (
        <>
          {/* Steering role: background arrow shows current direction only, fill by magnitude */}
          {steerDirection >= 0 && (
            <BigArrow x={MAX_LEN} y={0} color={BASE_COLOR} opacity={0.18} headRatio={0.35} />
          )}
          {steerDirection <= 0 && (
            <BigArrow x={-MAX_LEN} y={0} color={BASE_COLOR} opacity={0.18} headRatio={0.35} />
          )}
          <BigArrow x={showLeft ? -steerLen : -MIN_LEN} y={0} color={RESULT_COLOR} opacity={showLeft ? 0.90 : 0} headRatio={0.35} />
          <BigArrow x={showRight ? steerLen : MIN_LEN} y={0} color={RESULT_COLOR} opacity={showRight ? 0.90 : 0} headRatio={0.35} />
        </>
      )}
    </svg>
  );
}

/* ── Chart Column (role-adapted charts for one input) ──── */
function ChartColumn({
  label, role, waveOption, featureOption, metricLabel,
  speed, steer, steerDirection, dimmed,
  showCalib, calibOffset, calibScale, calibrating, calibPhase, calibCountdown,
  onCalibrate, onMinChange, onMaxChange, disabled,
}) {
  const roleLabel = role === 'speed' ? 'Speed' : 'Steering';
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <span className="section-label">{label}</span>
        <span className="vl-dot" style={{ background: role === 'speed' ? '#4da6ff' : '#ff944d' }} />
        <span style={{ fontSize: 13, color: '#999' }}>{roleLabel}</span>
      </div>
      <div className={`chart-card${dimmed ? ' dimmed-card' : ''}`}>
        <h3>Raw Wave &mdash; alpha / theta / beta</h3>
        <ReactECharts option={waveOption} style={{ height: 200 }} />
      </div>
      <div className={`chart-card${dimmed ? ' dimmed-card' : ''}`}>
        <h3>{metricLabel}</h3>
        <ReactECharts option={featureOption} style={{ height: 200 }} />
      </div>
      <div className="chart-card">
        <h3>Control Vector</h3>
        <div className="vector-card-body">
          <ControlVector speed={speed} steer={steer} role={role} steerDirection={steerDirection} />
        </div>
      </div>
      {showCalib && (
        <div className="chart-card">
          <h3>Calibration (this device)</h3>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
            <button
              className="btn btn-ghost calib-btn"
              disabled={disabled || calibrating}
              onClick={onCalibrate}
            >
              {calibrating
                ? (calibPhase === 'counting' ? `Calibrating… ${calibCountdown}s` : 'Preparing…')
                : 'Calibrate'}
            </button>
            <span className="calib-edit-group">
              <span className="calib-edit-row">
                <label className="calib-edit-label">min</label>
                <input
                  type="number" step="any"
                  className="calib-edit-input"
                  value={calibOffset}
                  onChange={(e) => onMinChange(e.target.value)}
                  disabled={disabled}
                />
              </span>
              <span className="calib-edit-row">
                <label className="calib-edit-label">max</label>
                <input
                  type="number" step="any"
                  className="calib-edit-input"
                  value={calibOffset + calibScale}
                  onChange={(e) => onMaxChange(e.target.value)}
                  disabled={disabled}
                />
              </span>
            </span>
          </div>
        </div>
      )}
    </div>
  );
}

/* ── App ───────────────────────────────────────────────── */
export default function App() {
  /* ── State ─────────────────────────────────────────── */
  const [config, setConfig]         = useState(null);
  const [feedback, setFeedback]     = useState('Ready.');
  const [series, setSeries]         = useState({ ...INIT_SERIES });
  const [series2, setSeries2]       = useState({ ...INIT_SERIES });
  const [wsConnected, setWsConnected] = useState(false);

  /* ── UI mode state ─────────────────────────────────── */
  const [inputMode, setInputMode]         = useState('eeg');
  const [eegBrand, setEegBrand]           = useState('gtec_headband');
  const [eegProtocol, setEegProtocol]     = useState('lsl');
  const [filePath, setFilePath]           = useState('');
  const [selectedChannels, setSelectedChannels] = useState([0, 1, 2]);
  const [metric, setMetric]               = useState('tbr');
  const [role1, setRole1]                 = useState('speed');
  const [role2, setRole2]                 = useState('none');
  const [device2, setDevice2]             = useState('eeg');
  const [eegBrand2, setEegBrand2]         = useState('gtec_headband');
  const [eegProtocol2, setEegProtocol2]   = useState('lsl');
  const [selectedChannels2, setSelectedChannels2] = useState([0, 1, 2]);
  const [metric2, setMetric2]             = useState('tbr');
  const [steerDirection, setSteerDirection] = useState(0);  // +1=right, -1=left, 0=none
  const dualDevice = role2 !== 'none';
  const [outputMode, setOutputMode]         = useState('thymio_simu');
  const [thymioDevice, setThymioDevice]     = useState('ser:device=/dev/ttyACM0');
  const [running, setRunning]               = useState(false);
  const [theme, setTheme]                   = useState(() => localStorage.getItem('theme') || 'dark');
  // role refs so the WS onmessage closure always sees the current roles
  // without reopening the socket when they change.
  const role1Ref = useRef(role1);
  role1Ref.current = role1;
  const role2Ref = useRef(role2);
  role2Ref.current = role2;
  // Per-device calibration (design §5.5.1): two independent hook instances.
  // onDone: clear charts + auto-stop in dual mode (calibration ends stopped,
  // user starts the real experiment manually — §5.5.4).
  const calib1 = useCalibration('eeg', setFeedback, () => {
    clearSeries();
    if (role2Ref.current !== 'none') stopSystem();
  });
  const calib2 = useCalibration('eeg2', setFeedback, () => {
    clearSeries();
    stopSystem();
  });

  function clearSeries() { setSeries({ ...INIT_SERIES }); setSeries2({ ...INIT_SERIES }); }

  /* ── System status (ROS2 + Thymio) ──────────────────── */
  const [systemStatus, setSystemStatus] = useState({ ros_available: false, thymio_connected: false });

  /* ── Sync theme to <html> ──────────────────────────── */
  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    localStorage.setItem('theme', theme);
  }, [theme]);

  const wsRef = useRef(null);
  const teleopWsRef = useRef(null);
  const teleopTopicRef = useRef('/cmd_vel');
  const [teleopConnected, setTeleopConnected] = useState(false);

  /* ── Derived ────────────────────────────────────────── */
  const isControlMode = inputMode === 'teleop';
  const activeCalib = calib1.calibrating ? calib1 : (calib2.calibrating ? calib2 : null);

  /* ── Load config ────────────────────────────────────── */
  useEffect(() => {
    api.get('/api/config')
      .then((r) => {
        const cfg = r.data.config;
        setConfig(cfg);
        setFeedback('Config loaded.');
        // Sync backend config → local UI state
        let loadedRole1 = role1;
        let loadedRole2 = role2;
        if (cfg.eeg) {
          if (cfg.eeg.input) setInputMode('eeg');
          calib1.syncCalib(cfg.eeg.calib_offset, cfg.eeg.calib_scale);
          if (cfg.eeg.role) { loadedRole1 = cfg.eeg.role; setRole1(cfg.eeg.role); }
          if (cfg.eeg.policy) setMetric(cfg.eeg.policy);
          // O22 (b): brand is frontend-local — infer it from the persisted
          // lsl_source_id (the backend drops the brand field on patch).
          if (cfg.eeg.lsl_source_id) {
            setEegBrand(SOURCE_ID_TO_BRAND[cfg.eeg.lsl_source_id] || 'gtec_headband');
          }
        }
        if (cfg.eeg2) {
          loadedRole2 = cfg.eeg2.role || 'steering';
          setRole2(loadedRole2);
          calib2.syncCalib(cfg.eeg2.calib_offset, cfg.eeg2.calib_scale);
          if (cfg.eeg2.policy) setMetric2(cfg.eeg2.policy);
          if (cfg.eeg2.lsl_source_id) {
            setEegBrand2(SOURCE_ID_TO_BRAND[cfg.eeg2.lsl_source_id] || 'gtec_headband');
          }
        }
        // Guard against YAML hand-edits: if both roles are the same (and not 'none'), fix
        if (loadedRole1 !== 'none' && loadedRole2 !== 'none' && loadedRole1 === loadedRole2) {
          setRole2(loadedRole1 === 'speed' ? 'steering' : 'speed');
        }
        if (cfg.launch) {
          setOutputMode(cfg.launch.use_sim ? 'thymio_simu' : 'thymio');
        }
      })
      .catch((err) => setFeedback(`Init failed: ${err.message}`));
  }, []);

  /* ── Enforce role mutual exclusion ───────────────────── */
  useEffect(() => {
    if (role1 === role2) {
      setRole2(role1 === 'speed' ? 'steering' : 'speed');
    }
  }, [role1]);  // only react to role1 changes

  /* ── Poll system status (ROS2 + Thymio) ─────────────── */
  useEffect(() => {
    const poll = () => {
      api.get('/api/status')
        .then((r) => setSystemStatus(r.data))
        .catch(() => {});  // silent fail
    };
    poll();  // initial fetch
    const timer = setInterval(poll, 3000);  // poll every 3s
    return () => clearInterval(timer);
  }, []);

  /* ── WebSocket ──────────────────────────────────────── */
  useEffect(() => {
    if (wsRef.current) wsRef.current.close();
    const ws = new WebSocket(getWsUrl());
    wsRef.current = ws;

    ws.onopen  = () => setWsConnected(true);
    ws.onclose = () => setWsConnected(false);
    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      const devs = data.devices || {};
      const dev1 = devs[role1Ref.current] || Object.values(devs)[0] || null;
      const dev2 = devs[role2Ref.current] || null;
      if (!dev1 && !dev2) return;  // no real data yet — keep charts frozen

      // A device awaiting calibration starts its 30s countdown on its first
      // analysis frame (design §5.5.4).
      if (calib1.waitingRef.current && dev1) calib1.startCountdown();
      else if (calib2.waitingRef.current && dev2) calib2.startCountdown();

      if (!isControlMode) {
        if (dev1) {
          setSeries((prev) => ({
            t:     pushPoint(prev.t,     new Date(dev1.timestamp * 1000).toLocaleTimeString()),
            alpha: pushPoint(prev.alpha,  dev1.channels?.alpha             ?? 0),
            theta: pushPoint(prev.theta,  dev1.channels?.theta             ?? 0),
            beta:  pushPoint(prev.beta,   dev1.channels?.beta               ?? 0),
            ratio: pushPoint(prev.ratio,  dev1.features?.theta_beta_ratio   ?? 0),
            focus: pushPoint(prev.focus,  dev1.features?.focus_index        ?? 0),
            speed: pushPoint(prev.speed,  dev1.control?.speed_intent        ?? 0),
            steer: pushPoint(prev.steer,  dev1.control?.steer_intent        ?? 0),
          }));
        }
        if (dev2) {
          setSeries2((prev) => ({
            t:     pushPoint(prev.t,     new Date(dev2.timestamp * 1000).toLocaleTimeString()),
            alpha: pushPoint(prev.alpha,  dev2.channels?.alpha             ?? 0),
            theta: pushPoint(prev.theta,  dev2.channels?.theta             ?? 0),
            beta:  pushPoint(prev.beta,   dev2.channels?.beta               ?? 0),
            ratio: pushPoint(prev.ratio,  dev2.features?.theta_beta_ratio   ?? 0),
            focus: pushPoint(prev.focus,  dev2.features?.focus_index        ?? 0),
            speed: pushPoint(prev.speed,  dev2.control?.speed_intent        ?? 0),
            steer: pushPoint(prev.steer,  dev2.control?.steer_intent        ?? 0),
          }));
        }
        // steer_direction is read from the steering device's control when it
        // exists, else from the single device's own control.
        const steerDev = devs.steering || dev1;
        setSteerDirection(steerDev?.control?.steer_direction ?? 0);
      }
    };
    return () => ws.close();
  }, [isControlMode]);

  /* ── Teleop WebSocket ─────────────────────────────── */
  useEffect(() => {
    if (inputMode !== 'teleop') {
      if (teleopWsRef.current) teleopWsRef.current.close();
      return;
    }

    const wsUrl = (import.meta.env.VITE_API_BASE || '').replace(/^http/, 'ws') + '/ws/teleop';
    const ws = new WebSocket(wsUrl);
    teleopWsRef.current = ws;

    ws.onopen = () => setTeleopConnected(true);
    ws.onclose = () => setTeleopConnected(false);
    ws.onerror = () => setTeleopConnected(false);
    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      if (data.type === 'config') {
        teleopTopicRef.current = data.topic;
        setTeleopConnected(true);
      }
    };

    return () => {
      ws.close();
    };
  }, [inputMode]);

  /* ── Fetch record files when source is file-based ──── */

  /* ── Chart options (per column — O5/O6) ──────────────── */
  const col1 = useChartOptions(series, metric, calib1.calibOffset, calib1.calibScale, calib1.calibrating, theme);
  const col2 = useChartOptions(series2, metric2, calib2.calibOffset, calib2.calibScale, calib2.calibrating, theme);

  /* ── Build patch ─────────────────────────────────────── */
  function buildPatch() {
    const isSim = outputMode === 'thymio_simu';
    const patch = {
      eeg: {
        input:           'lsl',
        role:            role1,
        policy:          metric,
        calibrate:       false,
        lsl_stream_type: 'EEG',
        lsl_timeout:     8.0,
        lsl_source_id:   BRAND_TO_SOURCE_ID[eegBrand] || '',
        brand:           eegBrand,  // backend ignores; frontend-local (O22)
      },
      eeg2: (dualDevice && device2 === 'eeg') ? {
        input:           'lsl',
        role:            role2,
        policy:          metric2,
        lsl_stream_type: 'EEG',
        lsl_timeout:     8.0,
        lsl_source_id:   BRAND_TO_SOURCE_ID[eegBrand2] || '',
        brand:           eegBrand2,  // backend ignores; frontend-local (O22)
      } : null,
      launch: {
        use_sim:  isSim,
        use_gui:  false,
        run_eeg:  inputMode === 'eeg',
        device:   outputMode === 'thymio' ? thymioDevice : '',
      },
    };
    return patch;
  }

  /* ── Actions ─────────────────────────────────────────── */
  async function saveConfig() {
    try {
      await api.put('/api/config', { patch: buildPatch() });
      setFeedback('Config saved in backend memory.');
    } catch (err) {
      setFeedback(`Save failed: ${err.message}`);
      throw err;
    }
  }

  async function startSystem(skipSave, skipUncalibratedPrompt) {
    try {
      await runAction('/api/system/stop', false);  // kill old processes, keep calib state
      // UX (design §5.5.4): starting with an uncalibrated device is allowed
      // but prompts first. "Uncalibrated" = never calibrated (0/1 defaults).
      // Calibration itself must skip this prompt (it would block the start).
      if (role2Ref.current !== 'none' && !skipUncalibratedPrompt) {
        const uncalibrated = [];
        if (calib1.calibOffset === 0 && calib1.calibScale === 1) {
          uncalibrated.push(role1 === 'speed' ? 'Speed device' : 'Steering device');
        }
        if (calib2.calibOffset === 0 && calib2.calibScale === 1) {
          uncalibrated.push(role2 === 'speed' ? 'Speed device' : 'Steering device');
        }
        if (uncalibrated.length && !window.confirm(`${uncalibrated.join(' & ')} not calibrated. Start anyway?`)) {
          return;
        }
      }
      if (!skipSave) await saveConfig();
      // Re-read calib values (may have been updated by a previous calibration run)
      const r = await api.get('/api/config', { params: { reload: true } });
      const cfg = r.data?.config;
      calib1.syncCalib(cfg?.eeg?.calib_offset, cfg?.eeg?.calib_scale);
      calib2.syncCalib(cfg?.eeg2?.calib_offset, cfg?.eeg2?.calib_scale);
      await runAction('/api/system/start', false);
      setRunning(true);
    } catch (err) {
      if (!String(err?.message || err).includes('Save failed')) {
        setFeedback(`Start failed: ${err.message}`);
      }
    }
  }

  /** Arm one device's calibration: patch calibrate=true, then start the system
   *  (the hook's countdown begins on that device's first analysis frame). */
  async function calibrateDevice(device, calib) {
    const patch = buildPatch();
    patch[device].calibrate = true;
    await api.put('/api/config', { patch });
    calib.beginWaiting();
    // Skip saveConfig (already saved with calibrate=true) and skip the
    // uncalibrated-start prompt (calibration is the very act of calibrating).
    await startSystem(true, true);
  }

  async function stopSystem() {
    try {
      // UX (design §5.5.4): if a device was mid-calibration, clear its
      // calibrate flag so the next Start doesn't re-enter calibration.
      const wasCalib1 = calib1.calibrating;
      const wasCalib2 = calib2.calibrating;
      calib1.reset();
      calib2.reset();
      if (wasCalib1) {
        try { await api.put('/api/config', { patch: { eeg: { calibrate: false } } }); } catch {}
      }
      if (wasCalib2) {
        try { await api.put('/api/config', { patch: { eeg2: { calibrate: false } } }); } catch {}
      }
      await runAction('/api/system/stop', false);
    } finally {
      setRunning(false);
    }
  }

  async function runAction(path, dryRun) {
    try {
      const res = await api.post(path, { dry_run: dryRun });
      setFeedback(`${res.data.detail}  —  ${res.data.command}`);
    } catch (err) {
      setFeedback(`Action failed: ${err.message}`);
    }
  }

  /* ── Render ───────────────────────────────────────────── */
  if (!config) {
    return <div className="loading">Loading dashboard&hellip;</div>;
  }

  return (
    <div className="page">

      {/* ── TOP BAR ───────────────────────────────────── */}
      <header className="topbar">
        <div className="topbar-brand">
          <HeroEmblem />
          <span className="topbar-title">Thymio EEG Control</span>
        </div>
        <div className="topbar-actions">
          <button
            className="btn btn-theme-toggle"
            onClick={() => setTheme((t) => (t === 'dark' ? 'light' : 'dark'))}
            title={theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}
          >
            {theme === 'dark' ? '☀' : '☾'}
          </button>
          <button className="btn btn-cta" disabled={running} onClick={() => startSystem()}>
            {running ? (activeCalib?.calibPhase === 'preparing' ? 'Preparing...' : activeCalib?.calibPhase === 'counting' ? `Calibrating... ${activeCalib.calibCountdown}s` : 'Running...') : 'Start'}
          </button>
          <button className="btn btn-ghost" disabled={!running} onClick={() => stopSystem()}>Stop</button>
          {/* Single-device calibration lives in the topbar (design §5.5.4 现状);
              in dual mode each column has its own Calibrate + min/max editors. */}
          {inputMode === 'eeg' && !dualDevice && (
            <span className="calib-right-group">
              <button className="btn btn-ghost calib-btn" disabled={running} onClick={() => calibrateDevice('eeg', calib1)}>Calibrate</button>
              <span className="calib-edit-group">
                <span className="calib-edit-row">
                  <label className="calib-edit-label">min</label>
                  <input
                    type="number" step="any"
                    className="calib-edit-input"
                    value={calib1.calibOffset}
                    onChange={(e) => calib1.updateCalibMin(e.target.value)}
                    disabled={running}
                  />
                </span>
                <span className="calib-edit-row">
                  <label className="calib-edit-label">max</label>
                  <input
                    type="number" step="any"
                    className="calib-edit-input"
                    value={calib1.calibOffset + calib1.calibScale}
                    onChange={(e) => calib1.updateCalibMax(e.target.value)}
                    disabled={running}
                  />
                </span>
              </span>
            </span>
          )}
        </div>
      </header>

      {/* ── SECTION 2: Controls (Dark surface) ────────── */}
      <div className="section-dark">
        <div className="controls-grid">

          {/* LEFT — Input Source */}
          <div>
            <span className="section-label">01 — Input Source</span>

            {/* ── Row 1 ──────────────────────────────── */}
            <div className="cascade-row" style={{ marginBottom: 12 }}>
              <img src={eegBrand === 'gtec_hybrid' ? '/HybridBlack.png' : '/Headband.png'} alt="" style={{ width: 28, height: 28, alignSelf: 'center' }} />
              <CascadeSelect
                label="Role"
                value={role1}
                onChange={setRole1}
                disabled={running}
                options={[
                  { value: 'speed',    label: 'Speed' },
                  { value: 'steering', label: 'Steering' },
                ]}
              />
              <CascadeSelect
                label="Device"
                value={inputMode}
                onChange={setInputMode}
                disabled={running}
                options={[
                  { value: 'eeg',    label: 'EEG' },
                  { value: 'teleop', label: 'Keyboard' },
                ]}
              />

              {inputMode === 'eeg' && (
                <>
                  <CascadeSelect
                    label="Brand"
                    value={eegBrand}
                    onChange={(v) => {
                      setEegBrand(v);
                      setSelectedChannels([0, 1, 2]);
                      setEegProtocol('lsl');
                    }}
                    disabled={running}
                    options={[
                      { value: 'gtec_hybrid',    label: 'g.tec Hybrid Black' },
                      { value: 'gtec_headband',  label: 'g.tec Headband' },
                    ]}
                  />
                  <CascadeSelect
                    label="Source"
                    value={eegProtocol}
                    onChange={(v) => { setEegProtocol(v); }}
                    disabled={running}
                    options={[{ value: 'lsl', label: 'LSL Stream' }]}
                  />
                  <ChannelPicker
                    channels={CHANNEL_PRESETS[eegBrand]}
                    selected={selectedChannels}
                    onChange={setSelectedChannels}
                    disabled={running}
                  />
                </>
              )}

              {inputMode === 'eeg' && (
                <CascadeSelect
                  label="Metric"
                  value={metric}
                  onChange={setMetric}
                  disabled={running}
                  options={METRIC_OPTIONS.map((m) => ({
                    value: m.value,
                    label: `${m.label} (${m.formula})`,
                  }))}
                />
              )}
            </div>

            {/* ── Row 2 ──────────────────────────────── */}
            <div className="cascade-row" style={{ marginBottom: 0 }}>
              <img src={eegBrand2 === 'gtec_hybrid' ? '/HybridBlack.png' : '/Headband.png'} alt="" style={{ width: 28, height: 28, alignSelf: 'center', opacity: dualDevice ? 1 : 0.35 }} />
              <CascadeSelect
                label="Role"
                value={role2}
                onChange={setRole2}
                disabled={running}
                options={[
                  { value: 'speed',    label: 'Speed',    disabled: role1 === 'speed' },
                  { value: 'steering', label: 'Steering', disabled: role1 === 'steering' },
                  { value: 'none',     label: 'None' },
                ]}
              />
              <fieldset disabled={!dualDevice} style={{ border: 'none', padding: 0, margin: 0, display: 'contents' }}>
                <CascadeSelect
                label="Device"
                value={device2}
                onChange={setDevice2}
                disabled={running || !dualDevice}
                options={[
                  { value: 'eeg',    label: 'EEG' },
                  { value: 'teleop', label: 'Keyboard' },
                ]}
              />

              {device2 === 'eeg' && (
                <>
                  <CascadeSelect
                    label="Brand"
                    value={eegBrand2}
                    onChange={(v) => {
                      setEegBrand2(v);
                      setSelectedChannels2([0, 1, 2]);
                      setEegProtocol2('lsl');
                    }}
                    disabled={running || !dualDevice}
                    options={[
                      { value: 'gtec_hybrid',    label: 'g.tec Hybrid Black' },
                      { value: 'gtec_headband',  label: 'g.tec Headband' },
                    ]}
                  />
                  <CascadeSelect
                    label="Source"
                    value={eegProtocol2}
                    onChange={(v) => { setEegProtocol2(v); }}
                    disabled={running || !dualDevice}
                    options={[{ value: 'lsl', label: 'LSL Stream' }]}
                  />
                  <ChannelPicker
                    channels={CHANNEL_PRESETS[eegBrand2]}
                    selected={selectedChannels2}
                    onChange={setSelectedChannels2}
                    disabled={running || !dualDevice}
                  />
                </>
              )}

              {device2 === 'eeg' && (
                <CascadeSelect
                  label="Metric"
                  value={metric2}
                  onChange={setMetric2}
                  disabled={running || !dualDevice}
                  options={METRIC_OPTIONS.map((m) => ({
                    value: m.value,
                    label: `${m.label} (${m.formula})`,
                  }))}
                />
              )}
            </fieldset>

          </div>

          </div>

          {/* RIGHT — Output Target */}
          <div>
            <span className="section-label">02 — Output Target</span>

            <div className="output-row">
              <div className="output-radios">
                {[
                  { value: 'thymio',        title: 'Thymio',       desc: 'Real robot' },
                  { value: 'thymio_simu',   title: 'Thymio Simu',  desc: 'Gazebo simulation' },
                  { value: 'none',          title: 'Sans robot',    desc: 'Waveforms only' },
                ].map((opt) => (
                  <label
                    key={opt.value}
                    className={`output-radio${outputMode === opt.value ? ' selected' : ''}${running ? ' disabled' : ''}`}
                  >
                    <input
                      type="radio"
                      name="output_mode"
                      value={opt.value}
                      checked={outputMode === opt.value}
                      onChange={() => setOutputMode(opt.value)}
                      disabled={running}
                    />
                    <span className="output-radio-title">{opt.title}</span>
                    <span className="output-radio-desc">{opt.desc}</span>
                  </label>
                ))}
              </div>

              {outputMode === 'thymio' && (
                <div className="thymio-device-input">
                  <span className="cascade-label">Device</span>
                  <input
                    type="text"
                    className="cascade-select"
                    value={thymioDevice}
                    onChange={(e) => setThymioDevice(e.target.value)}
                    disabled={running}
                    placeholder="ser:device=/dev/ttyACM0"
                  />
                </div>
              )}

              <div className="status-strip">
                <div className="status-row">
                  <div className={`status-dot ${wsConnected ? 'ok' : 'warn'}`} />
                  <span className="status-label">WebSocket</span>
                  <span className="status-value">{wsConnected ? 'connected' : 'disconnected'}</span>
                </div>
                <div className="status-row">
                  <div className={`status-dot ${systemStatus.ros_available ? 'ok' : 'off'}`} />
                  <span className="status-label">ROS2</span>
                  <span className="status-value">{systemStatus.ros_available ? 'available' : 'not found'}</span>
                </div>
                <div className="status-row">
                  <div className={`status-dot ${systemStatus.thymio_connected ? 'ok' : 'off'}`} />
                  <span className="status-label">Thymio</span>
                  <span className="status-value">{systemStatus.thymio_connected ? 'connected' : 'disconnected'}</span>
                </div>
              </div>
            </div>

          </div>

        </div>
      </div>

      {/* ── SECTION 2b: Camera (+ Teleop beside it when in simu+teleop) ─ */}
      {outputMode === 'thymio_simu' && (
        <div className="camera-row">
          <div className="camera-panel-wrap">
            <CameraPanel />
          </div>
          {inputMode === 'teleop' && (
            <div className="teleop-panel-wrap">
              <TeleopPanel
                teleopWsRef={teleopWsRef}
                topic={teleopTopicRef.current}
                connected={teleopConnected}
              />
            </div>
          )}
        </div>
      )}

      {/* ── SECTION 3: Teleop (real robot) OR Waveforms ─ */}
      {inputMode === 'teleop' && outputMode !== 'thymio_simu' ? (
        <TeleopPanel
          teleopWsRef={teleopWsRef}
          topic={teleopTopicRef.current}
          connected={teleopConnected}
        />
      ) : (
        <div className="section-light">
          <div className="section-header-row">
            <div>
              <span className="section-label">03 — Real-time Signals</span>
              <h2 className="section-heading">Signal Monitoring</h2>
            </div>
          </div>

          <div className="charts-grid" style={dualDevice ? { gridTemplateColumns: 'repeat(2, 1fr)' } : undefined}>
            <ChartColumn
              label={eegBrand === 'gtec_hybrid' ? 'Hybrid Black' : 'Headband'}
              role={role1}
              waveOption={col1.waveOption}
              featureOption={col1.featureOption}
              metricLabel={METRIC_LABELS[metric]}
              speed={series.speed.length ? series.speed[series.speed.length - 1] : 0}
              steer={series.steer.length ? series.steer[series.steer.length - 1] : 0.5}
              steerDirection={steerDirection}
              dimmed={inputMode !== 'eeg'}
              showCalib={dualDevice}
              calibOffset={calib1.calibOffset}
              calibScale={calib1.calibScale}
              calibrating={calib1.calibrating}
              calibPhase={calib1.calibPhase}
              calibCountdown={calib1.calibCountdown}
              onCalibrate={() => calibrateDevice('eeg', calib1)}
              onMinChange={calib1.updateCalibMin}
              onMaxChange={calib1.updateCalibMax}
              disabled={running}
            />
            {dualDevice && (
              <ChartColumn
                label={eegBrand2 === 'gtec_hybrid' ? 'Hybrid Black' : 'Headband'}
                role={role2}
                waveOption={col2.waveOption}
                featureOption={col2.featureOption}
                metricLabel={METRIC_LABELS[metric2]}
                speed={series2.speed.length ? series2.speed[series2.speed.length - 1] : 0}
                steer={series2.steer.length ? series2.steer[series2.steer.length - 1] : 0.5}
                steerDirection={steerDirection}
                dimmed={inputMode !== 'eeg'}
                showCalib
                calibOffset={calib2.calibOffset}
                calibScale={calib2.calibScale}
                calibrating={calib2.calibrating}
                calibPhase={calib2.calibPhase}
                calibCountdown={calib2.calibCountdown}
                onCalibrate={() => calibrateDevice('eeg2', calib2)}
                onMinChange={calib2.updateCalibMin}
                onMaxChange={calib2.updateCalibMax}
                disabled={running}
              />
            )}
          </div>
        </div>
      )}

      {/* ── Footer ────────────────────────────────────── */}
      <footer className="footer">
        <span className="footer-log">{feedback}</span>
        <span className="footer-badge">Thymio Control Console</span>
      </footer>

    </div>
  );
}

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

function ControlVector({ speed, steer, role }) {
  // speed: 0..1 (no backward), steer: 0..1 (0.5=center)
  const clampedSpeed = Math.max(0, Math.min(1, speed));
  const steerOffset = steer - 0.5; // -0.5..0.5

  // Forward arrow
  const fwdLen = lerp(MIN_LEN, MAX_LEN, clampedSpeed);

  // Left/Right arrows
  const leftMag = Math.abs(Math.min(steerOffset, 0)) * 2; // 0..1
  const leftLen = lerp(MIN_LEN, MAX_LEN, leftMag);
  const rightMag = Math.abs(Math.max(steerOffset, 0)) * 2; // 0..1
  const rightLen = lerp(MIN_LEN, MAX_LEN, rightMag);

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
          {/* Steering role: left/right arrows, fill active direction */}
          <BigArrow x={-MAX_LEN} y={0} color={BASE_COLOR} opacity={0.18} headRatio={0.35} />
          <BigArrow x={leftLen > 0 ? -leftLen : -MIN_LEN} y={0} color={RESULT_COLOR} opacity={leftMag > 0.03 ? 0.90 : 0} headRatio={0.35} />
          <BigArrow x={MAX_LEN} y={0} color={BASE_COLOR} opacity={0.18} headRatio={0.35} />
          <BigArrow x={rightLen > 0 ? rightLen : MIN_LEN} y={0} color={RESULT_COLOR} opacity={rightMag > 0.03 ? 0.90 : 0} headRatio={0.35} />
        </>
      )}
    </svg>
  );
}

/* ── Chart Column (role-adapted charts for one input) ──── */
function ChartColumn({ label, role, waveOption, featureOption, metricLabel, speed, steer, dimmed }) {
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
          <ControlVector speed={speed} steer={steer} role={role} />
        </div>
      </div>
    </div>
  );
}

/* ── App ───────────────────────────────────────────────── */
export default function App() {
  /* ── State ─────────────────────────────────────────── */
  const [config, setConfig]         = useState(null);
  const [feedback, setFeedback]     = useState('Ready.');
  const [series, setSeries]         = useState({
    t: [], alpha: [], theta: [], beta: [],
    ratio: [], focus: [], speed: [], steer: [],
  });
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
  const dualDevice = role2 !== 'none';
  const [outputMode, setOutputMode]         = useState('thymio_simu');
  const [thymioDevice, setThymioDevice]     = useState('ser:device=/dev/ttyACM0');
  const [showWaveform, setShowWaveform]     = useState(true);
  const [running, setRunning]               = useState(false);
  const [calibrating, setCalibrating]        = useState(false);
  const [calibPhase, setCalibPhase]          = useState(null);  // 'preparing' | 'counting'
  const [calibCountdown, setCalibCountdown]  = useState(30);
  const [calibOffset, setCalibOffset]        = useState(0);
  const calibOffsetRef                        = useRef(0);
  calibOffsetRef.current = calibOffset;
  const [calibScale, setCalibScale]          = useState(1);
  const [theme, setTheme]                   = useState(() => localStorage.getItem('theme') || 'dark');
  const calibTimerRef                        = useRef(null);
  const calibWaitingRef                      = useRef(false);  // waiting for first WS frame

  const INIT_SERIES = { t: [], alpha: [], theta: [], beta: [], ratio: [], focus: [], speed: [], steer: [] };
  function clearSeries() { setSeries({ ...INIT_SERIES }); }

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

  /* ── Load config ────────────────────────────────────── */
  useEffect(() => {
    api.get('/api/config')
      .then((r) => {
        const cfg = r.data.config;
        setConfig(cfg);
        setFeedback('Config loaded.');
        // Sync backend config → local UI state
        if (cfg.eeg) {
          if (cfg.eeg.input) setInputMode('eeg');
          if (cfg.eeg.calib_offset != null) setCalibOffset(Number(cfg.eeg.calib_offset));
          if (cfg.eeg.calib_scale != null) setCalibScale(Number(cfg.eeg.calib_scale));
          if (cfg.eeg.role) setRole1(cfg.eeg.role);
          if (cfg.eeg.policy) setMetric(cfg.eeg.policy);
          if (cfg.eeg.brand) setEegBrand(cfg.eeg.brand);
        }
        if (cfg.eeg2) {
          setRole2(cfg.eeg2.role || 'steering');
          if (cfg.eeg2.policy) setMetric2(cfg.eeg2.policy);
          if (cfg.eeg2.brand) setEegBrand2(cfg.eeg2.brand);
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
      if (data.channels == null) return;  // no real data yet — keep charts frozen
      // First data frame arrived → environment ready, start real countdown
      if (calibWaitingRef.current) {
        calibWaitingRef.current = false;
        setCalibPhase('counting');
        calibTimerRef.current = setInterval(() => {
          setCalibCountdown((prev) => {
            if (prev <= 1) {
              clearInterval(calibTimerRef.current);
              // Countdown done — re-read config and transition to Running
              api.get('/api/config', { params: { reload: true } }).then(r => {
                const eeg = r.data?.config?.eeg;
                finishCalibration(eeg || {});
              }).catch(() => { setCalibrating(false); setCalibPhase(null); });
              return 0;
            }
            return prev - 1;
          });
        }, 1000);
      }
      if (!isControlMode) {
        setSeries((prev) => ({
          t:     pushPoint(prev.t,     new Date(data.timestamp * 1000).toLocaleTimeString()),
          alpha: pushPoint(prev.alpha,  data.channels?.alpha             ?? 0),
          theta: pushPoint(prev.theta,  data.channels?.theta             ?? 0),
          beta:  pushPoint(prev.beta,   data.channels?.beta               ?? 0),
          ratio: pushPoint(prev.ratio,  data.features?.theta_beta_ratio   ?? 0),
          focus: pushPoint(prev.focus,  data.features?.focus_index        ?? 0),
          speed: pushPoint(prev.speed,  data.control?.speed_intent        ?? 0),
          steer: pushPoint(prev.steer,  data.control?.steer_intent        ?? 0),
        }));
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

  /* ── ECharts options (adapt to theme) ────────────────── */
  const isDarkCharts = theme === 'light';
  const waveOption = useMemo(() => ({
    backgroundColor: 'transparent',
    tooltip: { trigger: 'axis', backgroundColor: isDarkCharts ? '#fff' : '#2a2a2a', borderColor: isDarkCharts ? '#ddd' : '#444', textStyle: { color: isDarkCharts ? '#333' : '#ddd' } },
    legend: { textStyle: { color: isDarkCharts ? '#555' : '#aaa' }, top: 2 },
    grid: { left: 65, right: 16, top: 36, bottom: 24 },
    xAxis: { type: 'category', data: series.t, axisLabel: { color: isDarkCharts ? '#999' : '#888', fontSize: 10 } },
    yAxis: {
      type: 'value',
      max: p95Max(series.alpha, series.theta, series.beta),
      axisLabel: { color: isDarkCharts ? '#999' : '#888', fontSize: 10, formatter: fmtAxis },
    },
    series: [
      { name: 'alpha', type: 'line', smooth: true, showSymbol: false, data: series.alpha },
      { name: 'theta', type: 'line', smooth: true, showSymbol: false, data: series.theta },
      { name: 'beta',  type: 'line', smooth: true, showSymbol: false, data: series.beta  },
    ],
    color: isDarkCharts ? ['#DA291C', '#F6E500', '#000000'] : ['#DA291C', '#F6E500', '#CCCCCC'],
    animation: false,
  }), [series, isDarkCharts]);

  const metricLabels = { alpha: 'Alpha (α)', tbr: 'TBR (θ/β)', ei: 'EI (β/(α+θ))' };
  const metricDataKey = { alpha: 'alpha', tbr: 'ratio', ei: 'focus' };
  const featureOption = useMemo(() => {
    const showCalib = calibrating || calibScale > 2;  // scale ≈ 1 when not calibrated
    const calibHigh = calibOffset + calibScale;
    return {
      backgroundColor: 'transparent',
      tooltip: { trigger: 'axis', backgroundColor: isDarkCharts ? '#fff' : '#2a2a2a', borderColor: isDarkCharts ? '#ddd' : '#444', textStyle: { color: isDarkCharts ? '#333' : '#ddd' } },
      legend: { textStyle: { color: isDarkCharts ? '#555' : '#aaa' }, top: 2 },
      grid: { left: 65, right: 16, top: 36, bottom: 24 },
      xAxis: { type: 'category', data: series.t, axisLabel: { color: isDarkCharts ? '#999' : '#888', fontSize: 10 } },
      yAxis: {
        type: 'value',
        max: p95Max(series[metricDataKey[metric]]),
        axisLabel: { color: isDarkCharts ? '#999' : '#888', fontSize: 10, formatter: fmtAxis },
      },
      series: [
        {
          name: metricLabels[metric], type: 'line', smooth: true, showSymbol: false,
          data: series[metricDataKey[metric]],
          ...(showCalib ? {
            markLine: {
              silent: true, symbol: 'none',
              lineStyle: { type: 'dashed', color: isDarkCharts ? '#888' : '#aaa', width: 1 },
              label: { show: true, position: 'start', formatter: '{b}', color: isDarkCharts ? '#888' : '#999', fontSize: 10 },
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
              fill: isDarkCharts ? '#aaa' : '#666',
              fontSize: 11,
            },
          },
        ],
      } : {}),
    };
  }, [series, metric, isDarkCharts, calibOffset, calibScale, calibrating]);

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
        lsl_source_id:   eegBrand === 'gtec_headband' ? 'gtec_bci_core4' : eegBrand === 'gtec_hybrid' ? 'gtec_hybrid_black' : '',
        brand:           eegBrand,
      },
      eeg2: (dualDevice && device2 === 'eeg') ? {
        input:           'lsl',
        role:            role2,
        policy:          metric2,
        lsl_stream_type: 'EEG',
        lsl_timeout:     8.0,
        lsl_source_id:   eegBrand2 === 'gtec_headband' ? 'gtec_bci_core4' : eegBrand2 === 'gtec_hybrid' ? 'gtec_hybrid_black' : '',
        brand:           eegBrand2,
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

  async function startSystem(skipSave) {
    try {
      await runAction('/api/system/stop', false);  // kill old processes, keep calib state
      if (!skipSave) await saveConfig();
      // Re-read calib values (may have been updated by a previous calibration run)
      const r = await api.get('/api/config', { params: { reload: true } });
      const eeg = r.data?.config?.eeg;
      if (eeg) {
        if (eeg.calib_offset != null) setCalibOffset(Number(eeg.calib_offset));
        if (eeg.calib_scale != null) setCalibScale(Number(eeg.calib_scale));
      }
      await runAction('/api/system/start', false);
      setRunning(true);
    } catch (err) {
      if (!String(err?.message || err).includes('Save failed')) {
        setFeedback(`Start failed: ${err.message}`);
      }
    }
  }

  function finishCalibration(eeg) {
    setCalibrating(false);
    setCalibPhase(null);
    clearSeries();
    if (eeg?.calib_offset != null) setCalibOffset(Number(eeg.calib_offset));
    if (eeg?.calib_scale != null) setCalibScale(Number(eeg.calib_scale));
  }

  function startCountdown() {
    calibWaitingRef.current = true;
    setCalibrating(true);
    setCalibPhase('preparing');
    setCalibCountdown(30);
  }

  async function updateCalibMin(raw) {
    const v = Number(raw);
    if (isNaN(v)) return;
    setCalibOffset(v);
    try {
      await api.put('/api/config', { patch: { eeg: { calib_offset: v } } });
    } catch (err) { setFeedback(`Save offset failed: ${err.message}`); }
  }

  async function updateCalibMax(raw) {
    const v = Number(raw);
    if (isNaN(v)) return;
    const scale = Math.max(0.001, v - calibOffsetRef.current);
    setCalibScale(scale);
    try {
      await api.put('/api/config', { patch: { eeg: { calib_scale: scale } } });
    } catch (err) { setFeedback(`Save scale failed: ${err.message}`); }
  }

  async function stopSystem() {
    try {
      clearInterval(calibTimerRef.current);
      calibWaitingRef.current = false;
      setCalibrating(false);
      setCalibPhase(null);
      setCalibCountdown(30);
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
            {running ? (calibPhase === 'preparing' ? 'Preparing...' : calibPhase === 'counting' ? `Calibrating... ${calibCountdown}s` : 'Running...') : 'Start'}
          </button>
          <button className="btn btn-ghost" disabled={!running} onClick={() => stopSystem()}>Stop</button>
          {inputMode === 'eeg' && (
            <span className="calib-right-group">
              <button className="btn btn-ghost calib-btn" disabled={running} onClick={async () => {
                const patch = buildPatch();
                patch.eeg.calibrate = true;
                await api.put('/api/config', { patch });
                startCountdown();
                await startSystem(true);  // skip saveConfig — already saved with calibrate=true
              }}>Calibrate</button>
              <span className="calib-edit-group">
                <span className="calib-edit-row">
                  <label className="calib-edit-label">min</label>
                  <input
                    type="number" step="any"
                    className="calib-edit-input"
                    value={calibOffset}
                    onChange={(e) => updateCalibMin(e.target.value)}
                    disabled={running}
                  />
                </span>
                <span className="calib-edit-row">
                  <label className="calib-edit-label">max</label>
                  <input
                    type="number" step="any"
                    className="calib-edit-input"
                    value={calibOffset + calibScale}
                    onChange={(e) => updateCalibMax(e.target.value)}
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

            <label className={`waveform-toggle${isControlMode ? ' disabled' : ''}`}>
              <input
                type="checkbox"
                checked={showWaveform}
                disabled={isControlMode}
                onChange={(e) => setShowWaveform(e.target.checked)}
              />
              <span className="waveform-toggle-text">Show Waveforms</span>
              <span className="waveform-toggle-note">
                {isControlMode ? '— unavailable for this mode' : 'alpha · theta · beta · features · control'}
              </span>
            </label>
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

          <div className={`charts-grid${!showWaveform || isControlMode ? ' dimmed' : ''}`} style={dualDevice ? { gridTemplateColumns: 'repeat(2, 1fr)' } : undefined}>
            <ChartColumn
              label={eegBrand === 'gtec_hybrid' ? 'Hybrid Black' : 'Headband'}
              role={role1}
              waveOption={waveOption}
              featureOption={featureOption}
              metricLabel={metricLabels[metric]}
              speed={series.speed.length ? series.speed[series.speed.length - 1] : 0}
              steer={series.steer.length ? series.steer[series.steer.length - 1] : 0.5}
              dimmed={inputMode !== 'eeg'}
            />
            {dualDevice && (
              <ChartColumn
                label={eegBrand2 === 'gtec_hybrid' ? 'Hybrid Black' : 'Headband'}
                role={role2}
                waveOption={waveOption}
                featureOption={featureOption}
                metricLabel={metricLabels[metric2]}
                speed={series.speed.length ? series.speed[series.speed.length - 1] : 0}
                steer={series.steer.length ? series.steer[series.steer.length - 1] : 0.5}
                dimmed={inputMode !== 'eeg'}
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

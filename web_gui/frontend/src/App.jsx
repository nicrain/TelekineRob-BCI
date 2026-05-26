import { useEffect, useMemo, useRef, useState } from 'react';
import ReactECharts from 'echarts-for-react';
import { api, getWsUrl } from './api';

/* ── Constants ─────────────────────────────────────────── */
const MAX_POINTS = 140;

const CHANNEL_PRESETS = {
  enobio: [
    'Fp1', 'Fp2', 'F3', 'F4', 'C3', 'C4', 'P3', 'P4', 'O1', 'O2',
    'F7', 'F8', 'T7', 'T8', 'P7', 'P8', 'Fz', 'Cz', 'Pz', 'Oz',
  ],
  gtec_hybrid: ['Fz', 'C3', 'Cz', 'C4', 'Pz', 'PO7', 'Oz', 'PO8'],
  gtec_headband: ['Fp1', 'Fp2', 'T7', 'T8'],
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

/* ── Hero: Thymio robot icon ─────────────────────────────── */
function HeroEmblem() {
  return (
    <div className="hero-emblem">
      <img
        src="https://play-lh.googleusercontent.com/_S_Xg6eG0b3rFbtPrc9DVd2DbFbM71_1YO9HZQqxGnYyKy8SuPmtfE9m_ynqxj_WTIw=w600-h300-pc0xffffff-pd"
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

  function send(dir) {
    if (!teleopWsRef.current || teleopWsRef.current.readyState !== WebSocket.OPEN) return;
    teleopWsRef.current.send(JSON.stringify({ direction: dir }));
  }

  function handleDirDown(dir) {
    setActiveDir(dir);
    send(dir);
  }

  function handleDirUp() {
    setActiveDir(null);
    send('stop');
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
          <option key={opt.value} value={opt.value}>
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

function ControlVector({ speed, steer }) {
  // speed: 0..1 (no backward), steer: 0..1 (0.5=center)
  const clampedSpeed = Math.max(0, Math.min(1, speed));
  const steerOffset = steer - 0.5; // -0.5..0.5

  // Forward arrow (up in SVG = -Y)
  const fwdLen = lerp(MIN_LEN, MAX_LEN, clampedSpeed);
  const fwdActive = clampedSpeed > 0.05;

  // Left arrow: steerOffset < 0
  const leftMag = Math.abs(Math.min(steerOffset, 0)) * 2; // 0..1
  const leftLen = lerp(MIN_LEN, MAX_LEN, leftMag);
  const leftActive = steerOffset < -0.05;

  // Right arrow: steerOffset > 0
  const rightMag = Math.abs(Math.max(steerOffset, 0)) * 2; // 0..1
  const rightLen = lerp(MIN_LEN, MAX_LEN, rightMag);
  const rightActive = steerOffset > 0.05;

  // Resultant: combine forward (Y) and steer (X)
  const resMag = Math.sqrt(clampedSpeed * clampedSpeed + steerOffset * steerOffset * 4);
  const resLen = lerp(MIN_LEN, MAX_LEN, Math.min(resMag, 1));
  const resAngle = Math.atan2(-clampedSpeed, steerOffset * 2);
  const resX = resLen * Math.cos(resAngle);
  const resY = resLen * Math.sin(resAngle);

  return (
    <svg width={SVG_SIZE} height={SVG_SIZE} viewBox={`0 0 ${SVG_SIZE} ${SVG_SIZE}`} className="control-vector-svg">
      {/* Base arrows — all same color, big style */}
      {/* Forward (up) */}
      <BigArrow x={0} y={-fwdLen} color={BASE_COLOR} opacity={fwdActive ? 1 : 0.2} headRatio={0.35} />
      {/* Left */}
      <BigArrow x={-leftLen} y={0} color={BASE_COLOR} opacity={leftActive ? 1 : 0.2} headRatio={0.35} />
      {/* Right */}
      <BigArrow x={rightLen} y={0} color={BASE_COLOR} opacity={rightActive ? 1 : 0.2} headRatio={0.35} />

      {/* Resultant vector — different color, different style (thinner body, bigger head) */}
      <BigArrow x={resX} y={resY} color={RESULT_COLOR} opacity={0.85} headRatio={0.4} />
    </svg>
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
  const [eegBrand, setEegBrand]           = useState('enobio');
  const [eegProtocol, setEegProtocol]     = useState('tcp');
  const [filePath, setFilePath]           = useState('');
  const [selectedChannels, setSelectedChannels] = useState([0, 1, 2]);
  const [metric, setMetric]               = useState('tbr');
  const [recordFiles, setRecordFiles]     = useState([]);

  const [outputMode, setOutputMode]         = useState('thymio_simu');
  const [showWaveform, setShowWaveform]     = useState(true);
  const [useMockData, setUseMockData]       = useState(false);

  const wsRef = useRef(null);
  const teleopWsRef = useRef(null);
  const teleopTopicRef = useRef('/cmd_vel');
  const [teleopConnected, setTeleopConnected] = useState(false);

  /* ── Derived ────────────────────────────────────────── */
  const isControlMode = inputMode === 'teleop' || inputMode === 'tobii';

  /* ── Load config ────────────────────────────────────── */
  useEffect(() => {
    api.get('/api/config')
      .then((r) => {
        const cfg = r.data.config;
        setConfig(cfg);
        setFeedback('Config loaded.');
        // Sync backend config → local UI state
        if (cfg.eeg) {
          const inp = cfg.eeg.input || 'mock';
          if (inp === 'mock') {
            setInputMode('eeg');
            setEegProtocol('tcp');
          } else if (inp === 'tcp_file') {
            setInputMode('eeg');
            setEegProtocol('tcp_file');
          } else if (inp === 'lsl') {
            setInputMode('eeg');
            setEegProtocol('lsl');
          } else if (inp === 'file') {
            setInputMode('eeg');
            setEegProtocol('file');
          } else {
            setInputMode('eeg');
            setEegProtocol('tcp');
          }
          if (cfg.eeg.file_path) setFilePath(cfg.eeg.file_path);
        }
        if (cfg.pipeline) {
          if (cfg.pipeline.selected_channels) setSelectedChannels(cfg.pipeline.selected_channels);
          if (cfg.pipeline.algorithm) {
            const algMap = { alpha_only: 'alpha', theta_beta_ratio: 'tbr', engagement_index: 'ei' };
            setMetric(algMap[cfg.pipeline.algorithm] || 'tbr');
          }
        }
        if (cfg.launch) {
          setOutputMode(cfg.launch.use_sim ? 'thymio_simu' : 'thymio');
        }
      })
      .catch((err) => setFeedback(`Init failed: ${err.message}`));
  }, []);

  /* ── Mock data generator ────────────────────────────── */
  function generateMockPoint() {
    const now = new Date().toLocaleTimeString();
    const rand = (base, amp) => base + (Math.random() - 0.5) * amp;
    return {
      t: now,
      alpha: rand(10, 6),
      theta: rand(6, 4),
      beta:  rand(8, 5),
      ratio: rand(0.8, 0.4),
      focus: rand(1.2, 0.6),
      speed: Math.max(0, rand(0.3, 0.5)),
      steer: rand(0.5, 0.4),
    };
  }

  /* ── Mock data interval ─────────────────────────────── */
  useEffect(() => {
    if (!useMockData) return;
    const id = setInterval(() => {
      const d = generateMockPoint();
      setSeries((prev) => ({
        t:     pushPoint(prev.t,     d.t),
        alpha: pushPoint(prev.alpha, d.alpha),
        theta: pushPoint(prev.theta, d.theta),
        beta:  pushPoint(prev.beta,  d.beta),
        ratio: pushPoint(prev.ratio, d.ratio),
        focus: pushPoint(prev.focus, d.focus),
        speed: pushPoint(prev.speed, d.speed),
        steer: pushPoint(prev.steer, d.steer),
      }));
    }, 200);
    return () => clearInterval(id);
  }, [useMockData]);

  /* ── WebSocket ──────────────────────────────────────── */
  useEffect(() => {
    if (useMockData) return;
    if (wsRef.current) wsRef.current.close();
    const ws = new WebSocket(getWsUrl());
    wsRef.current = ws;

    ws.onopen  = () => setWsConnected(true);
    ws.onclose = () => setWsConnected(false);
    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      if (data.channels == null) return;  // no real data yet — keep charts frozen
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
  }, [isControlMode, useMockData]);

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
  const isFileSource = eegProtocol === 'tcp_file' || eegProtocol === 'lsl_file';
  useEffect(() => {
    if (!isFileSource) { setRecordFiles([]); return; }
    api.get('/api/files/records')
      .then((r) => setRecordFiles(r.data.files || []))
      .catch(() => setRecordFiles([]));
  }, [isFileSource]);

  /* ── ECharts options (light theme for white panel) ──── */
  const waveOption = useMemo(() => ({
    backgroundColor: 'transparent',
    tooltip: { trigger: 'axis', backgroundColor: '#fff', borderColor: '#ddd', textStyle: { color: '#333' } },
    legend: { textStyle: { color: '#555' }, top: 2 },
    grid: { left: 28, right: 16, top: 36, bottom: 24 },
    xAxis: { type: 'category', data: series.t, axisLabel: { color: '#999', fontSize: 10 } },
    yAxis: { type: 'value', axisLabel: { color: '#999', fontSize: 10 } },
    series: [
      { name: 'alpha', type: 'line', smooth: true, showSymbol: false, data: series.alpha },
      { name: 'theta', type: 'line', smooth: true, showSymbol: false, data: series.theta },
      { name: 'beta',  type: 'line', smooth: true, showSymbol: false, data: series.beta  },
    ],
    color: ['#DA291C', '#F6E500', '#000000'],
    animation: false,
  }), [series]);

  const metricLabels = { alpha: 'Alpha (α)', tbr: 'TBR (θ/β)', ei: 'EI (β/(α+θ))' };
  const metricDataKey = { alpha: 'alpha', tbr: 'ratio', ei: 'focus' };
  const featureOption = useMemo(() => ({
    backgroundColor: 'transparent',
    tooltip: { trigger: 'axis', backgroundColor: '#fff', borderColor: '#ddd', textStyle: { color: '#333' } },
    legend: { textStyle: { color: '#555' }, top: 2 },
    grid: { left: 28, right: 16, top: 36, bottom: 24 },
    xAxis: { type: 'category', data: series.t, axisLabel: { color: '#999', fontSize: 10 } },
    yAxis: { type: 'value', axisLabel: { color: '#999', fontSize: 10 } },
    series: [
      { name: metricLabels[metric], type: 'line', smooth: true, showSymbol: false, data: series[metricDataKey[metric]] },
    ],
    color: ['#DA291C'],
    animation: false,
  }), [series, metric]);

  /* ── Build patch ─────────────────────────────────────── */
  function buildPatch() {
    const inputMap = {
      eeg:     eegProtocol === 'tcp' ? 'tcp_client' : eegProtocol === 'tcp_file' ? 'tcp_file' : eegProtocol === 'lsl' ? 'lsl' : 'file',
      tobii:   'lsl',
      teleop:  'tcp_client',
    };
    const algorithmMap = { alpha: 'alpha_only', tbr: 'theta_beta_ratio', ei: 'engagement_index' };
    const isSim = outputMode === 'thymio_simu';
    const patch = {
      eeg: {
        input:           inputMap[inputMode] || 'mock',
        policy:          'focus',
        tcp_control_mode: 'feature',
        tcp_host:        '127.0.0.1',
        tcp_port:        1234,
        file_path:       filePath,
        lsl_stream_type: 'EEG',
        lsl_timeout:     8.0,
        lsl_channel_map: 'alpha=0,theta=1,beta=2,left_alpha=3,right_alpha=4',
        brand:           eegBrand,
      },
      launch: {
        use_sim:           isSim,
        use_gui:           false,
        run_eeg:           inputMode === 'eeg' || inputMode === 'mock',
        run_gaze:          inputMode === 'tobii',
        use_teleop:        inputMode === 'teleop',
        use_tobii_bridge:  inputMode === 'tobii',
        use_enobio_bridge: false,
      },
      pipeline: {
        source_type:       inputMap[inputMode] || 'mock',
        selected_channels: selectedChannels,
        algorithm:         algorithmMap[metric] || 'theta_beta_ratio',
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

  async function startSystem() {
    try {
      await saveConfig();
      await runAction('/api/system/start', false);
    } catch (err) {
      if (!String(err?.message || err).includes('Save failed')) {
        setFeedback(`Start failed: ${err.message}`);
      }
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
        <div className={`topbar-status ${wsConnected ? 'ok' : 'warn'}`}>
          <span className="status-dot-wrapper">
            <span className={`status-dot ${wsConnected ? 'ok' : 'warn'}`} />
          </span>
          <span className="topbar-status-text">WebSocket {wsConnected ? 'connected' : 'disconnected'}</span>
        </div>
      </header>

      {/* ── SECTION 2: Controls (Dark surface) ────────── */}
      <div className="section-dark">
        <div className="controls-grid">

          {/* LEFT — Input Source */}
          <div>
            <span className="section-label">01 — Input Source</span>

            <div className="cascade-row">
              <CascadeSelect
                label="Device"
                value={inputMode}
                onChange={setInputMode}
                options={[
                  { value: 'eeg',    label: 'EEG' },
                  { value: 'mock',   label: 'Mock' },
                  { value: 'tobii',  label: 'Tobii' },
                  { value: 'teleop', label: 'Keyboard' },
                ]}
              />

              {inputMode === 'eeg' && (
                <>
                  <CascadeSelect
                    label="Brand"
                    value={eegBrand}
                    onChange={(v) => { setEegBrand(v); setSelectedChannels([0, 1, 2]); }}
                    options={[
                      { value: 'enobio',         label: 'Enobio' },
                      { value: 'gtec_hybrid',    label: 'g.tec Hybrid Black' },
                      { value: 'gtec_headband',  label: 'g.tec Headband' },
                    ]}
                  />

                  <CascadeSelect
                    label="Source"
                    value={eegProtocol}
                    onChange={(v) => { setEegProtocol(v); setFilePath(''); }}
                    options={[
                      { value: 'tcp',      label: 'TCP Stream' },
                      { value: 'lsl',      label: 'LSL Stream' },
                      { value: 'tcp_file', label: 'TCP File' },
                      { value: 'lsl_file', label: 'LSL File' },
                    ]}
                  />

                  {isFileSource && (
                    <CascadeSelect
                      label="File"
                      value={filePath}
                      onChange={setFilePath}
                      options={[
                        { value: '', label: '— select file —' },
                        ...recordFiles.map((f) => ({ value: f, label: f })),
                      ]}
                    />
                  )}

                  <ChannelPicker
                    channels={CHANNEL_PRESETS[eegBrand]}
                    selected={selectedChannels}
                    onChange={setSelectedChannels}
                  />

                  <CascadeSelect
                    label="Metric"
                    value={metric}
                    onChange={setMetric}
                    options={METRIC_OPTIONS.map((m) => ({
                      value: m.value,
                      label: `${m.label} (${m.formula})`,
                    }))}
                  />
                </>
              )}
            </div>

            <div className="btn-row">
              <button className="btn btn-cta"     onClick={startSystem}>Start</button>
              <button className="btn btn-ghost"   onClick={() => runAction('/api/system/stop',  false)}>Stop</button>
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
                    className={`output-radio${outputMode === opt.value ? ' selected' : ''}`}
                  >
                    <input
                      type="radio"
                      name="output_mode"
                      value={opt.value}
                      checked={outputMode === opt.value}
                      onChange={() => setOutputMode(opt.value)}
                    />
                    <span className="output-radio-title">{opt.title}</span>
                    <span className="output-radio-desc">{opt.desc}</span>
                  </label>
                ))}
              </div>

              <div className="status-strip">
                <div className="status-row">
                  <div className={`status-dot ${wsConnected ? 'ok' : 'warn'}`} />
                  <span className="status-label">WebSocket</span>
                  <span className="status-value">{wsConnected ? 'connected' : 'disconnected'}</span>
                </div>
                <div className="status-row">
                  <div className="status-dot off" />
                  <span className="status-label">ROS2</span>
                  <span className="status-value">—</span>
                </div>
                <div className="status-row">
                  <div className="status-dot off" />
                  <span className="status-label">Thymio</span>
                  <span className="status-value">—</span>
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
            <label className={`data-toggle${useMockData ? ' mock' : ''}`}>
              <span className="data-toggle-label">Real</span>
              <input
                type="checkbox"
                checked={useMockData}
                onChange={(e) => setUseMockData(e.target.checked)}
              />
              <span className="data-toggle-track" />
              <span className="data-toggle-label">Mock</span>
            </label>
          </div>

          <div className={`charts-grid${!showWaveform || isControlMode ? ' dimmed' : ''}`}>
            <div className="chart-card">
              <h3>Raw Wave &mdash; alpha / theta / beta</h3>
              <ReactECharts option={waveOption} style={{ height: 220 }} />
            </div>
            <div className={`chart-card${inputMode !== 'eeg' ? ' dimmed-card' : ''}`}>
              <h3>{metricLabels[metric]}</h3>
              <ReactECharts option={featureOption} style={{ height: 220 }} />
            </div>
            <div className="chart-card">
              <h3>Control Vector</h3>
              <div className="vector-card-body">
                <ControlVector
                  speed={series.speed.length ? series.speed[series.speed.length - 1] : 0}
                  steer={series.steer.length ? series.steer[series.steer.length - 1] : 0.5}
                />
                <div className="vector-legend">
                  <span className="vl-item"><span className="vl-dot" style={{ background: '#555' }} /> base</span>
                  <span className="vl-item"><span className="vl-dot" style={{ background: '#DA291C' }} /> résultante</span>
                </div>
              </div>
            </div>
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

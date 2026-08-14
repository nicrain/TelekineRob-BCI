/* P16/E3: experiment-mode panel — protocol-driven trial prompting.

Drives the backend experiment session (P16/E1/E4): configure a session
(metadata + default protocol), then Start/Pause/Resume/Reset. Polls
/api/experiment/state every 0.5 s to show the current phase, the target
(A attention/rest, B attention/rest + direction) and the countdown, with a
rest prompt between trials. The frontend build is a user-side WSL2 task —
markers here are pinned by windows_launcher/tests/test_webgui_app_ui.py.
*/
import { useEffect, useState } from 'react';
import { api } from './api';

const PHASE_LABELS = { idle: 'Idle', prompt: 'Prompt', trial: 'Trial', rest: 'Break', paused: 'Paused', done: 'Done' };
// P28②: the per-row target STATE reads Focus (attention, blue) / Relax (rest,
// green); Break is the between-trials rest phase shown below the badge.
const STATE_LABEL = { attention: 'Focus', rest: 'Relax' };
const DIR_LABEL = { left: 'LEFT', right: 'RIGHT' };

const inputStyle = {
  padding: '6px 8px',
  fontSize: 13,
  background: 'var(--f-input-bg)',
  color: 'var(--f-text-primary)',
  border: '1px solid var(--f-border-strong)',
  borderRadius: 2,
  fontFamily: 'var(--font-mono)',
};
// P21/P23: fields are vertical — mono-small label on top, body value below.
const fieldLabelStyle = {
  display: 'flex', flexDirection: 'column', gap: 4, fontSize: 11,
  color: 'var(--f-text-secondary)', fontFamily: 'var(--font-mono)',
};
const valueStyle = { fontSize: 14, color: 'var(--f-text-primary)', fontFamily: 'var(--font-display)' };
// P25①: dual-device per-person rows match the input row height so the two
// values sit properly apart in the column (no cramped/too-high second row).
const rowValueStyle = { ...valueStyle, height: 28, display: 'flex', alignItems: 'center' };
// P23③: capitalize the raw config values for display.
const METRIC_LABEL = { alpha: 'Alpha', tbr: 'TBR', ei: 'EI' };
const MODE_LABEL = { single: 'Single', dual: 'Dual' };
const ROLE_LABEL = { speed: 'Speed', steering: 'Steering' };

// P29 supplement: target-table header — small mono secondary label; per-column
// alignment overridden on the Subjects header (right, for the colon alignment).
const thStyle = {
  fontFamily: 'var(--font-mono)', fontSize: 11, fontWeight: 400,
  color: 'var(--f-text-secondary)', paddingBottom: 6, textAlign: 'left',
};

// P29②: smooth integer-second countdown from an ABSOLUTE wall-clock end
// timestamp (ms) and the current time (ms). Ticking every ~200 ms, the shown
// second changes exactly 1 s apart — no uneven 0.5/2 s jumps.
function countdownSec(endTsMs, nowMs) {
  return Math.max(0, Math.ceil((endTsMs - nowMs) / 1000));
}

// P30: protocol-generator templates — each maps (a_state, b_state, b_direction).
const TEMPLATE_OPTIONS = [
  { value: 'a_only', label: 'A-only (speed: focus/relax)' },
  { value: 'b_steering', label: 'B-steering (turns)' },
  { value: 'b_blink', label: 'B-blink (direction)' },
  { value: 'dual_joint', label: 'Dual-joint (both)' },
];

// P30: seeded PRNG (mulberry32) so random/balanced shuffle is reproducible.
function mulberry32(a) {
  return function () {
    a |= 0; a = (a + 0x6D2B79F5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

// P30: same modes as the backend shuffle_trials — none keeps order, random
// shuffles (seeded), balanced round-robins over condition buckets (mirrors
// backend balanced_shuffle, so the preview matches what the backend would do).
function shuffleTrials(trials, mode, seed) {
  if (mode !== 'random' && mode !== 'balanced') return trials.slice();
  const rng = seed == null ? Math.random : mulberry32(seed);
  const shuffled = trials.slice();
  if (mode === 'random') {
    for (let i = shuffled.length - 1; i > 0; i--) {
      const j = Math.floor(rng() * (i + 1));
      [shuffled[i], shuffled[j]] = [shuffled[j], shuffled[i]];
    }
    return shuffled;
  }
  // balanced: shuffle within each condition bucket, then round-robin the
  // buckets in stable order — balanced exposure, no target streaks.
  const buckets = new Map();
  for (const t of shuffled) {
    const key = `${t.a_state}|${t.b_state}|${t.b_direction}`;
    if (!buckets.has(key)) buckets.set(key, []);
    buckets.get(key).push(t);
  }
  for (const bucket of buckets.values()) {
    for (let i = bucket.length - 1; i > 0; i--) {
      const j = Math.floor(rng() * (i + 1));
      [bucket[i], bucket[j]] = [bucket[j], bucket[i]];
    }
  }
  const out = [];
  let keys = [...buckets.keys()];
  while (keys.length) {
    const next = [];
    for (const k of keys) {
      const bucket = buckets.get(k);
      if (bucket.length) out.push(bucket.shift());
      if (bucket.length) next.push(k);
    }
    keys = next;
  }
  return out;
}

// P30: generate a template's trials then apply shuffle. Returns the FINAL
// protocol — the trials are already in run order, so Configure posts them
// verbatim (the backend applies none) and the preview equals the run.
function buildProtocol(template, opts) {
  const o = opts || {};
  const n = Math.max(1, Math.floor(o.n || 1));
  const duration_sec = o.duration_sec != null ? o.duration_sec : 20;
  const rest_sec = o.rest_sec != null ? o.rest_sec : 10;
  const prompt_sec = o.prompt_sec != null ? o.prompt_sec : 3;
  const shuffle = o.shuffle || 'balanced';
  const seed = o.seed != null ? o.seed : null;
  const t = [];
  const push = (a, b, d) => t.push({ a_state: a, b_state: b, b_direction: d, duration_sec, rest_sec });
  if (template === 'a_only') {
    // b rest throughout; a attention × n then rest × n
    for (let i = 0; i < n; i++) push('attention', 'rest', 'left');
    for (let i = 0; i < n; i++) push('rest', 'rest', 'left');
  } else if (template === 'b_steering') {
    // a rest throughout; b attention × n then rest × n
    for (let i = 0; i < n; i++) push('rest', 'attention', 'left');
    for (let i = 0; i < n; i++) push('rest', 'rest', 'left');
  } else if (template === 'b_blink') {
    // a rest, b attention throughout; direction left × n then right × n
    for (let i = 0; i < n; i++) push('rest', 'attention', 'left');
    for (let i = 0; i < n; i++) push('rest', 'attention', 'right');
  } else if (template === 'dual_joint') {
    // every (a, b, direction) combo × n — the joint balanced design
    for (const a of ['attention', 'rest']) {
      for (const b of ['attention', 'rest']) {
        for (const d of ['left', 'right']) {
          for (let i = 0; i < n; i++) push(a, b, d);
        }
      }
    }
  } else {
    throw new Error(`unknown template ${template}`);
  }
  const trials = shuffleTrials(t, shuffle, seed);
  return { trials, n_trials: trials.length, shuffle, seed, prompt_sec };
}

export default function ExperimentPanel({ config }) {
  const [exp, setExp] = useState(null);
  const [protocol, setProtocol] = useState(null);
  const [busy, setBusy] = useState(false);
  // P22②: after Configure the session view shows; formOpen lets the operator
  // EXIT back to the form (to re-configure / open a new session) — no one-way
  // door.
  const [formOpen, setFormOpen] = useState(false);
  // P20/P21: only subject / session_no are hand-filled; metric/device_mode/
  // roles/devices/has_hybrid come from the LIVE App.jsx 01 config prop (no
  // backend poll); electrode only when a hybrid is present. P24: subject_b is
  // device B's operator (dual mode).
  const [meta, setMeta] = useState({
    subject: '', subject_b: '', role: 'pilot', session_no: 1, electrode: '', date: '',
  });
  // P29②: `now` ticks every 200 ms so the countdown recomputes from the
  // absolute phase-end timestamp (end_ts_ms) — steady 1 s steps regardless
  // of the 500 ms state poll.
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), 200);
    return () => clearInterval(t);
  }, []);
  // P30: protocol generator — template + per-condition params → buildProtocol
  // on Generate; the result is sent to Configure (falls back to the saved
  // default protocol.json when nothing was generated).
  const [template, setTemplate] = useState('a_only');
  const [nTrials, setNTrials] = useState(4);
  const [duration, setDuration] = useState(20);
  const [restSec, setRestSec] = useState(10);
  const [promptSec, setPromptSec] = useState(3);
  const [shuffleMode, setShuffleMode] = useState('balanced');
  const [genProto, setGenProto] = useState(null);

  function refresh() {
    api.get('/api/experiment/state').then((r) => setExp(r.data)).catch(() => {});
  }
  useEffect(() => {
    refresh();
    const t = setInterval(refresh, 500);
    return () => clearInterval(t);
  }, []);

  useEffect(() => {
    api.get('/api/experiment/protocol').then((r) => setProtocol(r.data)).catch(() => {});
  }, []);

  function setMetaField(key, value) {
    setMeta((m) => ({ ...m, [key]: value }));
  }

  function generate() {
    setGenProto(buildProtocol(template, {
      n: nTrials, duration_sec: duration, rest_sec: restSec,
      prompt_sec: promptSec, shuffle: shuffleMode,
    }));
  }

  async function configure() {
    setBusy(true);
    try {
      // P21: send the live 01 config; the backend validates it and records it
      // into session.json's system block. P22②: re-configuring is allowed —
      // the backend starts a fresh session; flip back to the session view.
      // P30: when the operator generated a protocol, send it (trials are in
      // final run order — buildProtocol already applied shuffle); otherwise
      // the backend uses the saved default protocol.json.
      const r = await api.post('/api/experiment/configure', {
        meta: { ...meta, date: new Date().toISOString().slice(0, 10) },
        config: cfg,
        ...(genProto ? {
          trials: genProto.trials,
          shuffle: genProto.shuffle,
          seed: genProto.seed,
          prompt_sec: genProto.prompt_sec,
        } : {}),
      });
      if (r.data?.state) setExp(r.data.state);
      setFormOpen(false);
    } catch (e) {
      window.alert(`Configure failed: ${e.message}`);
    }
    setBusy(false);
  }

  async function action(path) {
    try {
      const r = await api.post(path);
      if (r.data?.state) setExp(r.data.state);
    } catch (e) {
      window.alert(`${path} failed: ${e.message}`);
    }
    await refresh();
  }

  const phase = exp?.phase || 'idle';
  const target = exp?.target || null;
  const cfg = config || {};   // P21: the LIVE App.jsx 01 config (props)
  const isDual = cfg.device_mode === 'dual';   // P24: two-row column grid
  const devices = cfg.devices || [];
  const idx = (exp?.trial_idx ?? 0) + 1;
  const total = exp?.n_trials ?? 0;
  // P29②: prefer the absolute phase-end timestamp + the 200 ms `now` tick;
  // fall back to the polled remaining_sec (older backend / pre-configure).
  const remaining = exp?.end_ts_ms
    ? countdownSec(exp.end_ts_ms, now)
    : Math.ceil(exp?.remaining_sec ?? 0);
  const configured = !!exp?.configured;

  const targetOn = phase === 'prompt' || phase === 'trial';
  const phaseBadgeStyle = {
    padding: '2px 8px', borderRadius: 2, fontSize: 12, fontFamily: 'var(--font-mono)',
    background: phase === 'trial' ? 'rgba(3,144,74,.15)' : (phase === 'prompt' ? 'rgba(241,58,44,.15)' : 'rgba(76,152,185,.15)'),
    color: phase === 'trial' ? 'var(--f-ok)' : (phase === 'prompt' ? 'var(--f-warn)' : 'var(--f-info)'),
  };

  return (
    <div style={{ border: '1px solid var(--f-border-strong)', borderRadius: 2, padding: 16, marginTop: 16, background: 'var(--f-surface)' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 8 }}>
        <span className="section-label">04 — Experiment Mode</span>
        {exp?.session_id && (
          <span style={{ fontFamily: 'var(--font-mono)', fontSize: 12, color: 'var(--f-text-secondary)' }}>
            {exp.session_id}
          </span>
        )}
      </div>

      {(!configured || formOpen) && (
        <div>
          {/* P24: dual device → a column grid whose values span TWO rows —
              Subject (A/B), Session #/Mode (shared, stretched), and the
              Electrode column (device1 n/a, device2 dry/wet) each show two
              rows; Metric/Roles are per person; single-device mode keeps the
              layout below unchanged. */}
          {isDual ? (
            <div style={{ display: 'flex', gap: 20, flexWrap: 'wrap', marginTop: 10 }}>
              <div style={fieldLabelStyle}>
                Subject
                <input style={inputStyle} placeholder="A" value={meta.subject}
                  onChange={(e) => setMetaField('subject', e.target.value)} />
                <input style={inputStyle} placeholder="B" value={meta.subject_b}
                  onChange={(e) => setMetaField('subject_b', e.target.value)} />
              </div>
              <div style={fieldLabelStyle}>
                Session #
                <input style={{ ...inputStyle, width: 64, height: 58 }} type="number" min="1"
                  value={meta.session_no} onChange={(e) => setMetaField('session_no', Number(e.target.value) || 1)} />
              </div>
              <div style={fieldLabelStyle}>
                Electrode
                {devices.map((d, i) => (
                  d.device === 'hybrid'
                    ? <select key={i} style={{ ...inputStyle, width: 64 }} value={meta.electrode || 'dry'}
                        onChange={(e) => setMetaField('electrode', e.target.value)}>
                        <option value="dry">Dry</option>
                        <option value="wet">Wet</option>
                      </select>
                    // P25② + P27②: headband row → N/A, fixed width, centered to
                    // match the select (a minWidth would still stretch in the column)
                    : <div key={i} style={{ ...rowValueStyle, width: 64, justifyContent: 'center' }}>N/A</div>
                ))}
              </div>
              <div style={fieldLabelStyle}>
                Metric
                {devices.map((d, i) => (
                  <div key={i} style={rowValueStyle}>{METRIC_LABEL[d.metric] || d.metric || '…'}</div>
                ))}
              </div>
              <div style={fieldLabelStyle}>
                Roles
                {devices.map((d, i) => (
                  <div key={i} style={rowValueStyle}>{ROLE_LABEL[d.role] || d.role || '…'}</div>
                ))}
              </div>
              {/* P27①: Mode last — same order in single and dual */}
              <div style={fieldLabelStyle}>
                Mode
                <div style={{ ...valueStyle, display: 'flex', alignItems: 'center', height: 58 }}>
                  {MODE_LABEL[cfg.device_mode] || cfg.device_mode || '…'}
                </div>
              </div>
            </div>
          ) : (
            <div style={{ display: 'flex', gap: 28, flexWrap: 'wrap', marginTop: 10, alignItems: 'flex-end' }}>
              <div style={{ display: 'flex', gap: 12 }}>
                <label style={fieldLabelStyle}>
                  Subject
                  <input style={inputStyle} placeholder="e.g. S01" value={meta.subject}
                    onChange={(e) => setMetaField('subject', e.target.value)} />
                </label>
                <label style={fieldLabelStyle}>
                  Session #
                  <input style={{ ...inputStyle, width: 64 }} type="number" min="1"
                    value={meta.session_no} onChange={(e) => setMetaField('session_no', Number(e.target.value) || 1)} />
                </label>
                {cfg.has_hybrid && (
                  <label style={fieldLabelStyle}>
                    Electrode
                    {/* P26②③ + P27②: dry/wet is short — a FIXED width (not
                        minWidth, which still stretches in the flex column)
                        keeps the dropdown genuinely narrow. */}
                    <select style={{ ...inputStyle, width: 64 }} value={meta.electrode || 'dry'}
                      onChange={(e) => setMetaField('electrode', e.target.value)}>
                      <option value="dry">Dry</option>
                      <option value="wet">Wet</option>
                    </select>
                  </label>
                )}
              </div>
              {/* P23 + P27①: read-only config is VERTICAL like the hand-filled
                  fields — Title-Case label on top, capitalized value below;
                  order Metric → Roles → Mode (same as dual, Mode last). */}
              <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap', paddingBottom: 6 }}>
                <span style={fieldLabelStyle}>
                  Metric
                  <span style={valueStyle}>{METRIC_LABEL[cfg.metric] || cfg.metric || '…'}</span>
                </span>
                <span style={fieldLabelStyle}>
                  Roles
                  <span style={valueStyle}>{(cfg.roles || []).map((r) => ROLE_LABEL[r] || r).join(' / ') || '…'}</span>
                </span>
                <span style={fieldLabelStyle}>
                  Mode
                  <span style={valueStyle}>{MODE_LABEL[cfg.device_mode] || cfg.device_mode || '…'}</span>
                </span>
              </div>
            </div>
          )}
          {/* P30: protocol generator — template + params → Generate builds
              the trials (pure buildProtocol) → preview → Configure sends them
              to the backend, which records them in session.json (P31: NOT
              written back to the repo protocol.json — reuse is by regenerating
              in the panel). Without Generate, Configure keeps the saved
              default — a hand-written protocol.json stays a valid entry. */}
          <div style={{ marginTop: 12, padding: 10, border: '1px solid var(--f-border-strong)', borderRadius: 2 }}>
            <span className="section-label">Protocol</span>
            <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'flex-end', marginTop: 6 }}>
              <label style={fieldLabelStyle}>
                Template
                <select style={{ ...inputStyle, width: 200 }} value={template}
                  onChange={(e) => setTemplate(e.target.value)}>
                  {TEMPLATE_OPTIONS.map((o) => (
                    <option key={o.value} value={o.value}>{o.label}</option>
                  ))}
                </select>
              </label>
              <label style={fieldLabelStyle}>
                n / condition
                <input style={{ ...inputStyle, width: 48 }} type="number" min="1" value={nTrials}
                  onChange={(e) => setNTrials(Number(e.target.value) || 1)} />
              </label>
              <label style={fieldLabelStyle}>
                duration
                <input style={{ ...inputStyle, width: 48 }} type="number" min="1" value={duration}
                  onChange={(e) => setDuration(Number(e.target.value) || 1)} />
              </label>
              <label style={fieldLabelStyle}>
                rest
                <input style={{ ...inputStyle, width: 48 }} type="number" min="0" value={restSec}
                  onChange={(e) => setRestSec(Number(e.target.value) || 0)} />
              </label>
              <label style={fieldLabelStyle}>
                prompt
                <input style={{ ...inputStyle, width: 48 }} type="number" min="0" value={promptSec}
                  onChange={(e) => setPromptSec(Number(e.target.value) || 0)} />
              </label>
              <label style={fieldLabelStyle}>
                shuffle
                <select style={{ ...inputStyle, width: 100 }} value={shuffleMode}
                  onChange={(e) => setShuffleMode(e.target.value)}>
                  <option value="none">none</option>
                  <option value="random">random</option>
                  <option value="balanced">balanced</option>
                </select>
              </label>
              <button className="btn btn-cta" onClick={generate}>Generate</button>
            </div>
            {genProto && (
              <div style={{ fontFamily: 'var(--font-mono)', fontSize: 12, color: 'var(--f-text-secondary)', marginTop: 8 }}>
                <div>{genProto.n_trials} trials · shuffle {genProto.shuffle} · {genProto.prompt_sec}s prompt</div>
                {genProto.trials.slice(0, 4).map((tr, i) => (
                  <div key={i} style={{ color: 'var(--f-text-primary)' }}>
                    {i + 1}: a={tr.a_state} · b={tr.b_state} · dir={tr.b_direction}
                  </div>
                ))}
              </div>
            )}
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginTop: 12 }}>
            <button className="btn btn-cta" disabled={busy} onClick={configure}>
              {configured ? 'Configure new session' : 'Configure session'}
            </button>
            <span style={{ fontSize: 12, color: 'var(--f-text-secondary)' }}>
              {(genProto || protocol)
                ? `${(genProto || protocol).n_trials} trials · shuffle ${(genProto || protocol).shuffle} · ${(genProto || protocol).prompt_sec}s prompt`
                : 'loading protocol…'}
            </span>
            {configured && exp?.session_id && (
              <span style={{ fontSize: 12, color: 'var(--f-text-secondary)', fontFamily: 'var(--font-mono)' }}>
                current session: {exp.session_id}
              </span>
            )}
          </div>
        </div>
      )}

      {configured && !formOpen && (
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginTop: 10, flexWrap: 'wrap' }}>
            <span style={phaseBadgeStyle}>{PHASE_LABELS[phase]}</span>
            <span style={{ fontSize: 13 }}>Trial {idx} / {total}</span>
            {phase === 'trial' && <span style={{ fontSize: 13, color: 'var(--f-ok)' }}>● recording</span>}
            <span style={{ flex: 1 }} />
            {phase !== 'idle' && phase !== 'done' && phase !== 'paused'
              ? <button className="btn btn-ghost" onClick={() => action('/api/experiment/pause')}>Pause</button>
              : null}
            {phase === 'paused'
              ? <button className="btn btn-ghost" onClick={() => action('/api/experiment/resume')}>Resume</button>
              : null}
            {phase === 'idle' || phase === 'done'
              ? <button className="btn btn-cta" onClick={() => action('/api/experiment/start')}>Start</button>
              : null}
            <button className="btn btn-ghost" onClick={() => action('/api/experiment/reset')}>Reset</button>
            {/* P22②: exit the experiment session back to the form — the
                session stays on disk; Configure can open a new one. */}
            <button className="btn btn-ghost" onClick={() => setFormOpen(true)}>Exit</button>
          </div>

          {target && targetOn && (
            <div style={{ padding: '14px 0' }}>
              {/* P29 supplement: the target display is a table on top of the
                  P28 role mapping — Subjects | Actions | Direction, one row
                  per REAL device (single = one, dual = two). P29①: subject
                  names are plain text color. P29④: the Subjects column is
                  right-aligned fixed width so the colons line up; Action text
                  left-aligned, not all centered. P29③: Direction is a small
                  muted mono cell — steering only (speed shows the em dash). */}
              <table style={{ margin: '0 auto', borderCollapse: 'collapse', textAlign: 'left' }}>
                <thead>
                  <tr>
                    <th style={{ ...thStyle, textAlign: 'right', paddingRight: 10 }}>Subjects</th>
                    <th style={thStyle}>Actions</th>
                    <th style={{ ...thStyle, paddingLeft: 18 }}>Direction</th>
                  </tr>
                </thead>
                <tbody>
                  {devices.map((d, i) => {
                    const isSpeed = d.role === 'speed';
                    const state = isSpeed ? target.a_state : target.b_state;
                    const isFocus = state === 'attention';
                    const subject = devices.length > 1
                      ? (i === 0 ? meta.subject : meta.subject_b)
                      : meta.subject;
                    return (
                      <tr key={i}>
                        <td style={{ textAlign: 'right', width: 120, color: 'var(--f-text-primary)', fontFamily: 'var(--font-display)', padding: '3px 10px 3px 0' }}>
                          {subject}:
                        </td>
                        <td style={{ color: isFocus ? 'var(--f-info)' : 'var(--f-ok)', fontWeight: 600, fontSize: 16, padding: '3px 0' }}>
                          {STATE_LABEL[state]}
                        </td>
                        <td style={{ fontSize: 12, color: 'var(--f-text-secondary)', fontFamily: 'var(--font-mono)', padding: '3px 0 3px 18px' }}>
                          {isSpeed ? '—' : DIR_LABEL[target.b_direction]}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
              <div style={{ fontSize: 34, fontFamily: 'var(--font-mono)', marginTop: 8, textAlign: 'center' }}>
                {remaining}s
              </div>
              <div style={{ fontSize: 13, color: 'var(--f-text-secondary)', textAlign: 'center' }}>
                Trial {idx} / {total}
              </div>
              {phase === 'prompt' && (
                <div style={{ color: 'var(--f-info)', fontSize: 13, textAlign: 'center' }}>Get ready — trial starts soon</div>
              )}
            </div>
          )}

          {phase === 'rest' && (
            <div style={{ textAlign: 'center', padding: '14px 0', color: 'var(--f-text-secondary)' }}>
              {/* P28①: Break is the BETWEEN-trials rest — neutral gray + timer
                  icon + 'next trial in Xs' countdown. It is NOT the per-row
                  Relax target shown inside a trial (that is green, with the
                  trial timer above) — the two never mix. */}
              <div style={{ fontSize: 20 }}>⏱ Break — next trial in {remaining}s</div>
            </div>
          )}

          {phase === 'done' && (
            <div style={{ textAlign: 'center', padding: '14px 0', color: 'var(--f-ok)' }}>
              Protocol complete — trial CSV + labels written to the session folder
            </div>
          )}

          {phase === 'idle' && (
            <div style={{ textAlign: 'center', padding: '14px 0', color: 'var(--f-text-secondary)' }}>
              Session ready — press Start when the operator is set
            </div>
          )}
        </div>
      )}
    </div>
  );
}

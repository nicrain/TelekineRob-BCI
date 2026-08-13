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

const PHASE_LABELS = { idle: 'Idle', prompt: 'Prompt', trial: 'Trial', rest: 'Rest', paused: 'Paused', done: 'Done' };
const STATE_LABEL = { attention: 'ATTENTION', rest: 'REST' };
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

  async function configure() {
    setBusy(true);
    try {
      // P21: send the live 01 config; the backend validates it and records it
      // into session.json's system block. P22②: re-configuring is allowed —
      // the backend starts a fresh session; flip back to the session view.
      const r = await api.post('/api/experiment/configure', {
        meta: { ...meta, date: new Date().toISOString().slice(0, 10) },
        config: cfg,
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
  const remaining = Math.ceil(exp?.remaining_sec ?? 0);
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
              Subject (A/B), Session #/Mode (shared, stretched), Electrode
              (device1 n/a, device2 dry/wet), Metric/Roles (per person).
              single-device mode keeps the layout below unchanged. */}
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
                Mode
                <div style={{ ...valueStyle, display: 'flex', alignItems: 'center', height: 58 }}>
                  {MODE_LABEL[cfg.device_mode] || cfg.device_mode || '…'}
                </div>
              </div>
              <div style={fieldLabelStyle}>
                Electrode
                {devices.map((d, i) => (
                  d.device === 'hybrid'
                    ? <select key={i} style={{ ...inputStyle, minWidth: 64 }} value={meta.electrode || 'dry'}
                        onChange={(e) => setMetaField('electrode', e.target.value)}>
                        <option value="dry">Dry</option>
                        <option value="wet">Wet</option>
                      </select>
                    // P25②: headband row → N/A, centered to align with the select
                    : <div key={i} style={{ ...rowValueStyle, minWidth: 88, justifyContent: 'center' }}>N/A</div>
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
                    {/* P26②③: dry/wet is short — narrower dropdown, capitalized options */}
                    <select style={{ ...inputStyle, minWidth: 64 }} value={meta.electrode || 'dry'}
                      onChange={(e) => setMetaField('electrode', e.target.value)}>
                      <option value="dry">Dry</option>
                      <option value="wet">Wet</option>
                    </select>
                  </label>
                )}
              </div>
              {/* P23: read-only config is VERTICAL like the hand-filled fields —
                  Title-Case label on top, capitalized value below. */}
              <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap', paddingBottom: 6 }}>
                <span style={fieldLabelStyle}>
                  Metric
                  <span style={valueStyle}>{METRIC_LABEL[cfg.metric] || cfg.metric || '…'}</span>
                </span>
                <span style={fieldLabelStyle}>
                  Mode
                  <span style={valueStyle}>{MODE_LABEL[cfg.device_mode] || cfg.device_mode || '…'}</span>
                </span>
                <span style={fieldLabelStyle}>
                  Roles
                  <span style={valueStyle}>{(cfg.roles || []).map((r) => ROLE_LABEL[r] || r).join(' / ') || '…'}</span>
                </span>
              </div>
            </div>
          )}
          <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginTop: 12 }}>
            <button className="btn btn-cta" disabled={busy} onClick={configure}>
              {configured ? 'Configure new session' : 'Configure session'}
            </button>
            <span style={{ fontSize: 12, color: 'var(--f-text-secondary)' }}>
              {protocol ? `${protocol.n_trials} trials · shuffle ${protocol.shuffle} · ${protocol.prompt_sec}s prompt` : 'loading protocol…'}
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
            <div style={{ textAlign: 'center', padding: '14px 0' }}>
              <div style={{ fontSize: 26, fontWeight: 700, letterSpacing: 1, fontFamily: 'var(--font-mono)', color: 'var(--f-red)' }}>
                A: {STATE_LABEL[target.a_state]}
              </div>
              <div style={{ fontSize: 17, marginTop: 4 }}>
                B: {STATE_LABEL[target.b_state]} · direction {DIR_LABEL[target.b_direction]}
              </div>
              <div style={{ fontSize: 34, fontFamily: 'var(--font-mono)', marginTop: 8 }}>
                {remaining}s
              </div>
              {phase === 'prompt' && (
                <div style={{ color: 'var(--f-warn)', fontSize: 13 }}>Get ready — trial starts soon</div>
              )}
            </div>
          )}

          {phase === 'rest' && (
            <div style={{ textAlign: 'center', padding: '14px 0', color: 'var(--f-text-secondary)' }}>
              <div style={{ fontSize: 20 }}>Rest — next trial in {remaining}s</div>
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

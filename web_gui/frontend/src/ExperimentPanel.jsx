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
// P21: name (mono small secondary) vs value (body) — distinct fonts.
const fieldLabelStyle = {
  display: 'flex', flexDirection: 'column', gap: 4, fontSize: 11,
  color: 'var(--f-text-secondary)', fontFamily: 'var(--font-mono)',
};
const kvStyle = { display: 'flex', alignItems: 'baseline', gap: 6 };
const nameStyle = { fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--f-text-secondary)' };
const valueStyle = { fontSize: 14, color: 'var(--f-text-primary)' };

export default function ExperimentPanel({ config }) {
  const [exp, setExp] = useState(null);
  const [protocol, setProtocol] = useState(null);
  const [busy, setBusy] = useState(false);
  // P20/P21: only subject / session_no are hand-filled; metric/device_mode/
  // roles/devices/has_hybrid come from the LIVE App.jsx 01 config prop (no
  // backend poll); electrode only when a hybrid is present.
  const [meta, setMeta] = useState({
    subject: '', role: 'pilot', session_no: 1, electrode: '', date: '',
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
      // into session.json's system block.
      const r = await api.post('/api/experiment/configure', {
        meta: { ...meta, date: new Date().toISOString().slice(0, 10) },
        config: cfg,
      });
      if (r.data?.state) setExp(r.data.state);
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

      {!configured && (
        <div>
          {/* ③: hand-filled fields carry labels; the read-only actual config
              sits on the SAME row to the right, names in mono small,
              values in body text. */}
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
            </div>
            <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap', paddingBottom: 6 }}>
              <span style={kvStyle}><span style={nameStyle}>metric</span><span style={valueStyle}>{cfg.metric || '…'}</span></span>
              <span style={kvStyle}><span style={nameStyle}>mode</span><span style={valueStyle}>{cfg.device_mode || '…'}</span></span>
              <span style={kvStyle}><span style={nameStyle}>roles</span><span style={valueStyle}>{(cfg.roles || []).join(' / ') || '…'}</span></span>
              {cfg.has_hybrid && (
                <select style={inputStyle} value={meta.electrode}
                  onChange={(e) => setMetaField('electrode', e.target.value)}>
                  <option value="">electrode</option>
                  <option value="dry">dry</option>
                  <option value="wet">wet</option>
                </select>
              )}
            </div>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginTop: 12 }}>
            <button className="btn btn-cta" disabled={busy} onClick={configure}>Configure session</button>
            <span style={{ fontSize: 12, color: 'var(--f-text-secondary)' }}>
              {protocol ? `${protocol.n_trials} trials · shuffle ${protocol.shuffle} · ${protocol.prompt_sec}s prompt` : 'loading protocol…'}
            </span>
          </div>
        </div>
      )}

      {configured && (
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

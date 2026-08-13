/* P17①: web GUI log panel — recent backend records + WSL launcher log tails.

Collapsible; Refresh fetches /api/logs, the auto checkbox polls every 2 s.
The frontend build is a user-side WSL2 task — markers here are pinned by
windows_launcher/tests/test_webgui_app_ui.py.
*/
import { useEffect, useState } from 'react';
import { api } from './api';

export default function LogPanel() {
  const [open, setOpen] = useState(false);
  const [auto, setAuto] = useState(false);
  const [data, setData] = useState(null);

  function refresh() {
    api.get('/api/logs').then((r) => setData(r.data)).catch(() => {});
  }
  useEffect(() => {
    if (!open) return;
    refresh();
    if (!auto) return;
    const t = setInterval(refresh, 2000);
    return () => clearInterval(t);
  }, [open, auto]);

  const backend = data?.backend || [];
  const files = data?.files || [];

  const boxStyle = {
    border: '1px solid var(--f-border-strong)', borderRadius: 2, padding: 16, marginTop: 16,
    background: 'var(--f-surface)',
  };
  const lineStyle = {
    fontFamily: 'var(--font-mono)', fontSize: 11.5, lineHeight: 1.5,
    color: 'var(--f-text-secondary)', whiteSpace: 'pre-wrap', wordBreak: 'break-word',
  };

  return (
    <div style={boxStyle}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
        <span className="section-label">05 — Logs</span>
        <button className="btn btn-ghost" onClick={() => setOpen((v) => !v)}>
          {open ? 'Collapse' : 'Expand'}
        </button>
        {open && (
          <>
            <button className="btn btn-ghost" onClick={refresh}>Refresh</button>
            <label style={{ fontSize: 12, color: 'var(--f-text-secondary)', display: 'flex', alignItems: 'center', gap: 4 }}>
              <input type="checkbox" checked={auto} onChange={(e) => setAuto(e.target.checked)} />
              auto (2 s)
            </label>
          </>
        )}
      </div>

      {open && (
        <div style={{ marginTop: 10, maxHeight: 360, overflow: 'auto' }}>
          {backend.length === 0 && files.length === 0 && (
            <div style={lineStyle}>No log records yet.</div>
          )}
          {backend.length > 0 && (
            <>
              <div style={{ ...lineStyle, color: 'var(--f-text-primary)' }}>── backend ──</div>
              {backend.map((r, i) => (
                <div key={`b${i}`} style={lineStyle}>
                  <span style={{ color: r.level === 'ERROR' ? 'var(--f-warn)' : 'var(--f-info)' }}>
                    {new Date(r.ts * 1000).toLocaleTimeString()} {r.level}
                  </span>
                  {' '}{r.logger} — {r.message}
                </div>
              ))}
            </>
          )}
          {files.map((f, i) => (
            <div key={`f${i}`}>
              <div style={{ ...lineStyle, color: 'var(--f-text-primary)' }}>── {f.source} ──</div>
              {f.lines.map((line, j) => (
                <div key={`fl${j}`} style={lineStyle}>{line}</div>
              ))}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

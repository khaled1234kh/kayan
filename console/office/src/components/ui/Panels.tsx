import { useState } from 'react';
import { eventLevel, eventMessage, type KayanEvent } from '../../types/events';
import type { SecurityDecisionView as KayanSecurityDecision } from '../../security/policyTypes';
import type { ConnectionState } from '../../transport';
const FEED_FILTERED = new Set<KayanEvent['type']>(['trustgate_snapshot']);
export function TopBar({ onAudit, onPlanning, onReconnect, connection, active='live' }: { onAudit: () => void; onPlanning?: () => void; onReconnect?: () => void; connection: ConnectionState; active?:'live'|'planning'|'audit' }) {
  const labels: Record<ConnectionState,string> = { connected: 'Console connected', connecting: 'Connecting to console',
    reconnecting: 'Reconnecting to console', disconnected: 'Console disconnected', error: 'Console error', idle: 'Console idle' };
  const tone = connection === 'connected' ? 'ok' : ['error','disconnected'].includes(connection) ? 'bad' : 'wait';
  return <header className="topbar"><div className="brand"><span className="brand-mark">K</span>KAYAN <span className="brand-sub">TrustGate</span></div>
    <nav className="main-nav" aria-label="Workspace"><button className={active==='live'?'is-current':''} type="button" aria-current={active==='live'?'page':undefined}>Live</button><button className={active==='planning'?'is-current':''} type="button" onClick={onPlanning}>Planning</button><button className={active==='audit'?'is-current':''} type="button" onClick={onAudit}>Audit</button></nav>
    <div className="top-right"><span className="conn" data-testid="connection" data-connection={tone}>
      <span className="conn-dot" />{labels[connection]}</span>
      {['disconnected','error'].includes(connection) && <button type="button" className="btn" onClick={onReconnect}>Reconnect</button>}
      <a className="btn presentation-link" href="/review.html">Recorded demo ↗</a>
</div></header>;
}
export function EventFeed({ events }: { events: KayanEvent[] }) {
  // Read straight from the event history. Transport-level message events are
  // filtered so the feed reads as a sequence of actions rather than raw traffic.
  const visible = events.filter((e) => !FEED_FILTERED.has(e.type));
  return (
    <aside className="panel panel-events" data-testid="event-feed">
      <div className="panel-label">Activity</div>
      {visible.length === 0 ? (
        <p className="muted">Waiting for activity from the selected event source.</p>
      ) : (
        <ul className="events">
          {visible.slice(0, 8).map((e) => (
            <li key={e.id} className={`event event-${eventLevel(e)}`} data-event-type={e.type}>
              <span className="event-time mono">
                {new Date(e.timestamp).toLocaleTimeString('en-GB', { hour12: false })}
              </span>
              <span className="event-msg">{eventMessage(e)}</span>
            </li>
          ))}
        </ul>
      )}
    </aside>
  );
}

export function TrustGatePanel({ decision, scopeLabel, emptyMessage }: {
  decision: KayanSecurityDecision | null; scopeLabel?: string; emptyMessage?: string;
}) {
  const denied = decision?.decision === 'deny';
  return (
    <aside className="panel panel-security" data-testid="trustgate-panel">
      <div className="panel-label">TrustGate{scopeLabel ? ` · ${scopeLabel}` : ''}</div>
      {!decision ? (
        <p className="muted" data-testid="security-empty">
          {emptyMessage ?? 'No security decisions yet.'}
        </p>
      ) : (
        <>
          <div className="security-verdict">
            <span className="panel-title security-title">Decision</span>
            <span
              className={`chip ${denied ? 'chip-danger' : 'chip-active'}`}
              data-testid="security-decision"
            >
              {denied ? 'Denied' : 'Allowed'}
            </span>
          </div>
          <div className="kv">
            <span className="k">Policy</span>
            <span className="v" data-testid="security-policy"><CopyValue value={decision.policy} label="Policy reference" /></span>
          </div>
          <div className="kv">
            <span className="k">Subject</span>
            <span className="v">{decision.subject}</span>
          </div>
          <div className="kv">
            <span className="k">Action</span>
            <span className="v">{decision.action}</span>
          </div>
          <div className="kv">
            <span className="k">Resource</span>
            <span className="v mono">{decision.resource}</span>
          </div>
          {decision.auditEntryId && <div className="kv"><span className="k">Audit reference</span><CopyValue value={decision.auditEntryId} label="Audit reference" /></div>}
          <div className="kv">
            <span className="k">Reason</span>
            <span className="v" data-testid="security-reason">{decision.reason}</span>
          </div>
        </>
      )}
    </aside>
  );
}

/** Legend so the colour language is readable without hovering. */
export function Legend() {
  const items: Array<[string, string]> = [
    ['var(--accent)', 'Working'],
    ['var(--allow)', 'Completed'],
    ['var(--wait)', 'Waiting / approval'],
    ['var(--deny)', 'Blocked'],
    ['var(--muted)', 'Idle'],
  ];
  return (
    <div className="legend">
      {items.map(([c, label]) => (
        <span className="legend-item" key={label}>
          <span className="legend-dot" style={{ background: c }} />
          {label}
        </span>
      ))}<span className="legend-item" title="Thin white outline: selected workstation. Colored small ring: recorded agent state."><span className="legend-selection"/>Selected</span>
    </div>
  );
}

export function CopyValue({ value, label }: { value: string; label: string }) {
  const [notice,setNotice] = useState('');
  async function copy() { try { await navigator.clipboard.writeText(value); setNotice('Copied'); } catch { setNotice('Copy unavailable; expand the full value.'); } }
  return <span className="copy-value"><span className="truncate" title={value}>{value}</span><button type="button" aria-label={`Copy ${label}`} onClick={() => void copy()}>Copy</button>
    <details><summary>Full value</summary><code>{value}</code></details>{notice && <span role="status">{notice}</span>}</span>;
}

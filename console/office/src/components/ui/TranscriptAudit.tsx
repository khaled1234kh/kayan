import { useEffect, useRef, useState } from 'react';
import type { TrustGateTranscriptEntry } from '../../types/trustgate';
import { decisionTone } from './LiveAgentPanel';

export function AuditEntries({ entries }: { entries: TrustGateTranscriptEntry[] }) {
  return <div className="session-transcript">{entries.map(entry => <details className={`session-entry ${decisionTone(entry)}`}
    data-kind={entry.kind} key={entry.id}><summary><time>{new Date(entry.timestamp).toLocaleTimeString()}</time>{' '}
      <strong>{entry.agent_role}</strong>{' · '}{entry.content}</summary>
    {!!entry.audit_entry_id && <p>Audit entry: <code>{entry.audit_entry_id}</code></p>}
    <pre>{JSON.stringify(entry,null,2)}</pre></details>)}</div>;
}

/** Read-only console transcript, not a browser authorization engine or audit-chain verifier. */
export function TranscriptAudit({ transcript, engagementId, onClose }: {
  transcript: TrustGateTranscriptEntry[]; engagementId?: string; onClose: () => void;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  const [role,setRole] = useState('all');
  useEffect(() => { dialog.current?.showModal(); }, []);
  const entries = transcript.filter(entry => role === 'all' || entry.agent_role === role);
  function exportTranscript() {
    const blob = new Blob([JSON.stringify({ engagement_id: engagementId, transcript },null,2)],{type:'application/json'});
    const url = URL.createObjectURL(blob); const link = document.createElement('a');
    link.href=url;link.download=`kayan-transcript-${engagementId ?? 'waiting'}.json`;link.click();
    window.setTimeout(() => URL.revokeObjectURL(url),1000);
  }
  return <dialog ref={dialog} className="planning-dialog" onCancel={event => { event.preventDefault(); onClose(); }}>
    <header><h2>Engagement evidence</h2><button type="button" className="btn" onClick={onClose}>Close</button></header>
    <p>Saved console transcript · {engagementId ?? 'No engagement loaded'}</p>
    <p className="muted">Read-only records supplied by the console. Audit IDs refer to backend decisions; this view does not verify the audit chain.</p>
    <label>Agent filter <select value={role} onChange={event => setRole(event.target.value)}><option value="all">All agents</option>
      {[...new Set(transcript.map(entry => entry.agent_role))].map(value => <option key={value}>{value}</option>)}</select></label>
    <p>{entries.length} visible / {transcript.length} transcript entries. Export includes the complete transcript.</p>
    <AuditEntries entries={entries} />
    <button type="button" className="btn" onClick={exportTranscript} disabled={!transcript.length}>Export transcript JSON</button>
  </dialog>;
}

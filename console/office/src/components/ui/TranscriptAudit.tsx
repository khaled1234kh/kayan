import { useEffect, useRef, useState } from 'react';
import type { TrustGateTranscriptEntry } from '../../types/trustgate';
import { decisionTone } from './LiveAgentPanel';
import { coverageRoleLabel } from './CoverageDetails';

export function filterAuditEntries(transcript:TrustGateTranscriptEntry[],role:string,decision:string,search:string) {
  const term=search.trim().toLowerCase();
  return transcript.filter(entry=>(role==='all'||entry.agent_role===role)
    &&(decision==='all'||decisionTone(entry)==='is-'+(decision==='deny'?'denied':'allowed'))
    &&(!term||[entry.content,entry.tool_name,entry.audit_entry_id,entry.id].join(' ').toLowerCase().includes(term)));
}

export function AuditEntries({entries}:{entries:TrustGateTranscriptEntry[]}) {
  return <div className="audit-records">{entries.map(entry=><details className={`session-entry ${decisionTone(entry)}`} data-kind={entry.kind} key={entry.id}>
    <summary><div className="audit-record-meta"><time dateTime={new Date(entry.timestamp).toISOString()}>{new Date(entry.timestamp).toLocaleTimeString('en-GB')}</time><strong>{coverageRoleLabel(entry.agent_role)}</strong><span>{entry.kind.replace(/_/g,' ')}</span></div><p>{entry.content.length>180?entry.content.slice(0,180)+'…':entry.content}</p></summary>
    {!!entry.audit_entry_id&&<p>Audit entry: <code>{entry.audit_entry_id}</code></p>}
    <pre>{JSON.stringify(entry,null,2)}</pre>
  </details>)}</div>;
}

/** Read-only session evidence; only the backend verifies its audit chain. */
export function TranscriptAudit({transcript,engagementId,onClose}:{transcript:TrustGateTranscriptEntry[];engagementId?:string;onClose:()=>void}) {
  const dialog=useRef<HTMLDialogElement>(null),searchField=useRef<HTMLInputElement>(null);
  const [role,setRole]=useState('all'),[decision,setDecision]=useState('all'),[search,setSearch]=useState('');
  useEffect(()=>{const view=dialog.current;view?.showModal();searchField.current?.focus();return()=>view?.close();},[]);
  const entries=filterAuditEntries(transcript,role,decision,search);
  function exportTranscript(){
    const blob=new Blob([JSON.stringify({engagement_id:engagementId,transcript},null,2)],{type:'application/json'});
    const url=URL.createObjectURL(blob),link=document.createElement('a');link.href=url;link.download=`kayan-transcript-${engagementId??'waiting'}.json`;link.click();window.setTimeout(()=>URL.revokeObjectURL(url),1000);
  }
  return <dialog ref={dialog} className="audit-workspace" aria-labelledby="audit-title" onCancel={event=>{event.preventDefault();onClose();}}>
    <header className="modal-heading"><div><span className="eyebrow">Read-only evidence</span><h2 id="audit-title">Engagement evidence</h2></div><button type="button" className="btn" onClick={onClose}>Close</button></header>
    <div className="audit-context"><code>{engagementId??'No engagement loaded'}</code><p>Records supplied by the console. Audit IDs refer to backend decisions; this view does not verify the audit chain.</p></div>
    <div className="audit-controls"><label>Search records<input ref={searchField} value={search} onChange={event=>setSearch(event.target.value)} placeholder="Text, tool or audit ID"/></label>
      <label>Agent filter<select value={role} onChange={event=>setRole(event.target.value)}><option value="all">All agents</option>{[...new Set(transcript.map(entry=>entry.agent_role))].map(value=><option key={value} value={value}>{coverageRoleLabel(value)}</option>)}</select></label>
      <label>Decision filter<select value={decision} onChange={event=>setDecision(event.target.value)}><option value="all">All records</option><option value="allow">ALLOW only</option><option value="deny">DENY only</option></select></label>
    </div>
    <div className="audit-scroll"><p className="muted audit-count">{entries.length} visible / {transcript.length} transcript entries</p>{entries.length?<AuditEntries entries={entries}/>:<div className="empty-state"><strong>{transcript.length?'No matching records':'No session records yet'}</strong><p>{transcript.length?'Adjust the filters. The original transcript is unchanged.':'Load or run an assessment to inspect its recorded activity.'}</p></div>}</div>
    <footer className="modal-actions"><span>Export includes the complete transcript, regardless of filters.</span><button type="button" className="btn btn-primary" onClick={exportTranscript} disabled={!transcript.length}>Export transcript JSON</button></footer>
  </dialog>;
}

import { useEffect, useRef, useState, type ReactNode } from 'react';
import type { Actor } from '../../types';
import { TRUSTGATE_SEATS, type TrustGateFinding, type TrustGateTranscriptEntry } from '../../types/trustgate';
import { TierBadge } from './TierBadge';
import { AgentMessageComposer } from './OperatorControls';
import { CoverageDetails, coverageRoleLabel, parseCoverage, type SpecialistCoverage } from './CoverageDetails';
import { CoordinationDetails, parseOutcomeReview } from './CoordinationDetails';

export function decisionTone(entry: TrustGateTranscriptEntry): string {
  const decision = String(entry.decision ?? entry.trustgate_decision ?? '').toUpperCase();
  return decision === 'DENY' ? 'is-denied' : decision === 'ALLOW' ? 'is-allowed' : '';
}

export function findingLabel(kind:string){return ({sql_injection:'SQL injection',command_injection:'Command injection',path_traversal:'Path traversal',xss:'XSS'} as Record<string,string>)[kind]??kind.replace(/_/g,' ');}

function rawTranscript(entry: TrustGateTranscriptEntry): string {
  // The transcript scrolls to its end as output grows. Keep the streamed
  // output there, after the large input/context fields, so that it is visible.
  const { output, ...record } = entry;
  return JSON.stringify(output === undefined ? record : { ...record, output }, null, 2);
}

/** Existing sidebar pattern, with raw chronological records expanded on demand. */
export function LiveAgentPanel({ actor, transcript, findings, decision, gateAvailable, onClose }: {
  actor: Actor | null; transcript: TrustGateTranscriptEntry[]; findings: TrustGateFinding[]; decision?: ReactNode; gateAvailable?: boolean; onClose?:()=>void;
}) {
  const [tab, setTab] = useState('Activity');
  const [followLatest,setFollowLatest]=useState(true);
  useEffect(()=>{setTab('Activity');setFollowLatest(true);},[actor?.id]);
  const scroll = useRef<HTMLDivElement>(null);
  const entries = actor ? transcript.filter((entry) => TRUSTGATE_SEATS[entry.agent_role] === actor.id)
    .slice().sort((a, b) => (a.seq ?? a.timestamp) - (b.seq ?? b.timestamp)) : [];
  const lastId = entries[entries.length - 1]?.id;
  const streamedLength = String(entries[entries.length - 1]?.output ?? '').length;
  useEffect(() => {
    const element = scroll.current;
    if (element && followLatest) element.scrollTop = element.scrollHeight;
  }, [actor?.id, lastId, streamedLength, followLatest, tab]);
  if (!actor) return <aside className="panel live-agent-panel session-empty"><div className="rail-heading"><span className="eyebrow">Agent session</span>{onClose&&<button type="button" className="icon-button" aria-label="Close agent session" onClick={onClose}>×</button>}</div><div className="session-empty-mark" aria-hidden="true"><svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"><rect x="8" y="3" width="8" height="5" rx="1"/><path d="M12 8v5M5 13h14M5 13v3m14-3v3"/><rect x="2" y="16" width="6" height="5" rx="1"/><rect x="16" y="16" width="6" height="5" rx="1"/></svg></div><h2>Meet your assessment team</h2>
    <p>Select an agent in the team list or on the office floor to inspect its work.</p><ul><li>Current task and recorded activity</li><li>Findings and authorization decisions</li><li>Governed status questions and instructions</li></ul><small>Only recorded session state is shown. An idle agent does not imply a completed assessment.</small></aside>;
  const coordinator = actor.id === TRUSTGATE_SEATS.planner_agent;
  const coverageByRole = new Map<string, SpecialistCoverage>();
  for (const entry of entries) {
    const outcome = entry.specialist_outcome as {role?: string; coverage?: unknown} | undefined;
    const coverage = parseCoverage(coordinator ? outcome?.coverage : entry.coverage);
    if (coverage) coverageByRole.set(coordinator ? outcome?.role ?? entry.agent_role : entry.agent_role, coverage);
  }
  const incomplete = [...coverageByRole].filter(([, coverage]) => !coverage.complete);
  const aggregatesFindings=coordinator||actor.id===TRUSTGATE_SEATS.reporting_agent;
  const produced = aggregatesFindings ? findings : findings.filter((finding) => TRUSTGATE_SEATS[finding.agent] === actor.id);
  return <aside className="panel live-agent-panel" data-testid="live-agent-panel">
    <div className="rail-heading"><span className="eyebrow session-eyebrow">Agent session</span>{onClose&&<button className="icon-button" type="button" aria-label="Close agent session" onClick={onClose}>×</button>}</div><header className="session-heading"><h2 data-testid="actor-name">{actor.name}</h2><TierBadge tier={actor.modelTier} /></header>
    <p className="muted model-resolution">{actor.executionEngine === 'deterministic_baseline' ? 'Deterministic baseline · no LLM inference' : !actor.modelName || actor.modelName.startsWith('UNRESOLVED') ? 'Model not selected for this session' : `Model: ${actor.modelName}`}</p>
    <div className="session-status-line"><span className="session-state" data-state={actor.state} data-testid="actor-state">{actor.state}</span><span>{entries.length} records · {produced.length} findings</span></div>
    <div className="session-task"><span className="eyebrow">Current assignment</span><strong data-testid="current-task">{actor.currentTask ?? 'No active task'}</strong></div>
    <p className="session-activity" data-testid="agent-activity" title="Latest recorded activity. Expand the matching transcript entry for full evidence.">{actor.activity || 'Standing by'}</p>
    {coordinator && <details className="role-boundary"><summary>Coordination role & boundaries</summary><p>Coordinator only · Recon → Web-App → Network → Reporting. Shared local model; no specialist tool authority.</p></details>}
    {coordinator && <CoordinationDetails reviews={entries.map(e => parseOutcomeReview(e.review)).filter(r => r !== null)}/>}
    {!!incomplete.length && <details className="coverage-warning"><summary>Assessment coverage limits ({incomplete.length})</summary>
      {incomplete.map(([role, coverage]) => <section key={role}><strong>{coverageRoleLabel(role)}</strong>
        <CoverageDetails coverage={coverage}/></section>)}
    </details>}
    <div className="agent-tabs" role="tablist" aria-label="Agent details">{['Activity','Findings','Decision','Message'].map(label =>
      <button type="button" key={label} role="tab" id={`agent-tab-${label}`} aria-selected={tab === label} tabIndex={tab===label?0:-1} onKeyDown={event=>{const labels=['Activity','Findings','Decision','Message'];let index=labels.indexOf(label);if(event.key==='ArrowRight')index=(index+1)%4;else if(event.key==='ArrowLeft')index=(index+3)%4;else if(event.key==='Home')index=0;else if(event.key==='End')index=3;else return;event.preventDefault();setTab(labels[index]);document.getElementById(`agent-tab-${labels[index]}`)?.focus();}} aria-controls={`agent-pane-${label}`} onClick={() => setTab(label)}>{label}</button>)}</div>
    <section role="tabpanel" id="agent-pane-Activity" aria-labelledby="agent-tab-Activity" hidden={tab !== 'Activity'}>
    <div className="transcript-heading"><h3>Session transcript <span className="muted">({entries.length})</span></h3><button type="button" className="text-action" aria-pressed={followLatest} onClick={()=>setFollowLatest(true)}>{followLatest?'Following latest':'Jump to latest'}</button></div>
    <div className="session-transcript" ref={scroll} onScroll={event=>{const e=event.currentTarget;setFollowLatest(e.scrollHeight-e.scrollTop-e.clientHeight<32);}} tabIndex={0} aria-label="Session transcript" role="log" aria-live="polite" data-testid="tool-transcript">
      {!actor.backendAgentId ? <p className="muted">Idle — no live session.</p> : entries.length === 0 ?
        <p className="muted">Waiting for transcript entries…</p> : entries.map((entry) => (
          <details key={entry.id} className={`session-entry ${decisionTone(entry)}`} data-kind={entry.kind}>
            <summary><time dateTime={new Date(entry.timestamp).toISOString()}>{new Date(entry.timestamp).toLocaleTimeString()}</time>
              <span>{entry.seq ? `${entry.seq}. ` : ''}{entry.content.split('\n')[0].slice(0, 180)}</span></summary>
            <pre>{rawTranscript(entry)}</pre>
          </details>
        ))}
    </div>
    </section><section role="tabpanel" id="agent-pane-Findings" aria-labelledby="agent-tab-Findings" hidden={tab !== 'Findings'}>
    <h3>{aggregatesFindings ? 'Assessment findings' : 'Reported findings'} <span className="muted">({produced.length})</span></h3>
    <div className="session-findings" data-testid="agent-findings">
      {produced.length === 0 ? <p className="muted">{aggregatesFindings ? 'No specialist findings received. This does not establish safety.' : 'No findings reported by this agent.'}</p> : produced.map((finding, index) => (
        <details key={finding.id ?? index} className="session-finding"><summary>{findingLabel(finding.type)}
          {aggregatesFindings && <span className="muted"> · {coverageRoleLabel(finding.agent)}</span>}
          <span className="mitre-tag">{finding.mitre ?? 'Unmapped'}</span></summary>
          <pre>{JSON.stringify(finding, null, 2)}</pre>
        </details>
      ))}
    </div>
    </section><section role="tabpanel" id="agent-pane-Decision" aria-labelledby="agent-tab-Decision" hidden={tab !== 'Decision'}>{decision ?? <p>No recorded decision for this agent.</p>}</section>
    <section role="tabpanel" id="agent-pane-Message" aria-labelledby="agent-tab-Message" hidden={tab !== 'Message'}>
    <AgentMessageComposer key={actor.backendAgentId ?? actor.id} actor={actor} gateAvailable={gateAvailable} />
    </section>
  </aside>;
}

import { useEffect, useRef, useState, type ReactNode } from 'react';
import type { Actor } from '../../types';
import { TRUSTGATE_SEATS, type TrustGateFinding, type TrustGateTranscriptEntry } from '../../types/trustgate';
import { TierBadge } from './TierBadge';
import { AgentMessageComposer } from './OperatorControls';

export function decisionTone(entry: TrustGateTranscriptEntry): string {
  const decision = String(entry.decision ?? entry.trustgate_decision ?? '').toUpperCase();
  return decision === 'DENY' ? 'is-denied' : decision === 'ALLOW' ? 'is-allowed' : '';
}

function rawTranscript(entry: TrustGateTranscriptEntry): string {
  // The transcript scrolls to its end as output grows. Keep the streamed
  // output there, after the large input/context fields, so that it is visible.
  const { output, ...record } = entry;
  return JSON.stringify(output === undefined ? record : { ...record, output }, null, 2);
}

/** Existing sidebar pattern, with raw chronological records expanded on demand. */
export function LiveAgentPanel({ actor, transcript, findings, decision, gateAvailable }: {
  actor: Actor | null; transcript: TrustGateTranscriptEntry[]; findings: TrustGateFinding[]; decision?: ReactNode; gateAvailable?: boolean;
}) {
  const [tab, setTab] = useState('Activity');
  const scroll = useRef<HTMLDivElement>(null);
  const entries = actor ? transcript.filter((entry) => TRUSTGATE_SEATS[entry.agent_role] === actor.id)
    .slice().sort((a, b) => (a.seq ?? a.timestamp) - (b.seq ?? b.timestamp)) : [];
  const lastId = entries[entries.length - 1]?.id;
  const streamedLength = String(entries[entries.length - 1]?.output ?? '').length;
  useEffect(() => {
    const element = scroll.current;
    if (element) element.scrollTop = element.scrollHeight;
  }, [actor?.id, lastId, streamedLength]);
  if (!actor) return <aside className="panel live-agent-panel"><h2>Agent session</h2>
    <p className="muted">Select a named agent or its workstation to inspect the live session.</p></aside>;
  const coordinator = actor.id === TRUSTGATE_SEATS.planner_agent;
  const produced = coordinator ? findings : findings.filter((finding) => TRUSTGATE_SEATS[finding.agent] === actor.id);
  return <aside className="panel live-agent-panel" data-testid="live-agent-panel">
    <header className="session-heading"><h2 data-testid="actor-name">{actor.name}</h2><TierBadge tier={actor.modelTier} /></header>
    <p className="muted model-resolution">{actor.executionEngine === 'deterministic_baseline' ? 'Deterministic baseline · no LLM inference' : !actor.modelName || actor.modelName.startsWith('UNRESOLVED') ? 'Model not selected for this session' : `Model: ${actor.modelName}`}</p>
    <div className="kv"><span className="k">Status</span><span data-testid="actor-state">{actor.state}</span></div>
    <div className="kv"><span className="k">Current task</span><strong data-testid="current-task">{actor.currentTask ?? 'No active task'}</strong></div>
    <p className="session-activity" data-testid="agent-activity">{actor.activity || 'Standing by'}</p>
    {coordinator && <p className="muted">Coordinator only · Recon → Web-App → Network → Reporting. Shared local model; no specialist tool authority.</p>}
    <div className="agent-tabs" role="tablist" aria-label="Agent details">{['Activity','Findings','Decision','Message'].map(label =>
      <button type="button" key={label} role="tab" id={`agent-tab-${label}`} aria-selected={tab === label} aria-controls={`agent-pane-${label}`} onClick={() => setTab(label)}>{label}</button>)}</div>
    <section role="tabpanel" id="agent-pane-Activity" aria-labelledby="agent-tab-Activity" hidden={tab !== 'Activity'}>
    <h3>Session transcript <span className="muted">({entries.length})</span></h3>
    <div className="session-transcript" ref={scroll} role="log" aria-live="polite" data-testid="tool-transcript">
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
    <h3>{coordinator ? 'Assessment findings' : 'Reported findings'} <span className="muted">({produced.length})</span></h3>
    <div className="session-findings" data-testid="agent-findings">
      {produced.length === 0 ? <p className="muted">{coordinator ? 'No specialist findings received. This does not establish safety.' : 'No findings reported by this agent.'}</p> : produced.map((finding, index) => (
        <details key={finding.id ?? index} className="session-finding"><summary>{finding.type}
          {coordinator && <span className="muted"> · {finding.agent}</span>}
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

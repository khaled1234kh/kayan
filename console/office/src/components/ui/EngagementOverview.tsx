import type { Actor } from '../../types';
import type { TrustGateTranscriptEntry } from '../../types/trustgate';
import { EngagementLauncher } from './OperatorControls';
export function engagementLabel(actors: Actor[], running: boolean, transcript: TrustGateTranscriptEntry[] = []) {
  const enrolled = actors.filter(a => a.backendAgentId);
  if (!enrolled.length) return 'No assessment loaded';
  if (enrolled.some(a => a.state === 'blocked')) return running ? 'Attention required' : 'Partial / blocked assessment';
  if (running) return 'Assessment in progress';
  const completion = [...transcript].reverse().find(e => e.agent_role === 'planner_agent' && e.kind === 'agent_completed')
    ?.assessment_completion as { complete?: boolean } | undefined;
  if (completion?.complete === false) return 'Assessment finished · incomplete coverage';
  return enrolled.every(a => a.state === 'completed') ? 'Saved completed assessment' : 'Assessment ready';
}
export function EngagementOverview({actors,running,onSelect,selectedId,onClose,gate,restorationNotice,transcript=[]}: {actors:Actor[];running:boolean;onSelect:(id:string)=>void;selectedId?:string|null;onClose?:()=>void;restorationNotice?:string;gate:'checking'|'available'|'unavailable'|'unknown';transcript?:TrustGateTranscriptEntry[]}) {
  const order=['planner','ai-manager','ai-sales','ai-ops','human'];
  return <aside className="engagement-zone" id="operations-panel" aria-label="Engagement overview">
    <div><div className="rail-heading"><span className="eyebrow">Engagement</span>{onClose&&<button type="button" className="icon-button" aria-label="Hide operations" onClick={onClose}>×</button>}</div><h1>Operations</h1><p className="engagement-status">{engagementLabel(actors,running,transcript)}</p></div>
    <div className={`runtime-notice ${gate}`} role="status">{gate==='checking' ? 'Checking Gate availability…' : gate==='unknown' ? 'Gate status unknown: reconnect the console' : gate==='available' ? 'Gate responding · authorization required' : 'Gate unavailable: recorded evidence mode'}</div>
    {restorationNotice&&<details className="restoration-notice"><summary>Restored session</summary><p>{restorationNotice}</p></details>}
    <EngagementLauncher running={running} hidePlanning gateAvailable={gate==='available'} />
    <section><div className="team-heading"><h2>Agent team</h2><span>5 roles</span></div><p className="team-caption">Execution state · coverage reported separately</p><ol className="assessment-stages">{order.map((id,index) => {
      const actor=actors.find(a=>a.id===id);const state=actor?.backendAgentId ? actor.state : 'idle';
      return <li key={id} data-state={state}><button type="button" aria-pressed={selectedId===id} onClick={()=>onSelect(id)}><span className="stage-dot">{index+1}</span><span>{actor?.name.replace(' Agent','') ?? id}<small>{state}</small></span></button></li>;
    })}</ol></section>
    <details className="system-limits"><summary>System boundaries</summary><p>One shared local Qwen model; role-specific contracts. No fine-tuning or separate helper model. Planner coordinates, specialists execute only through TrustGate.</p><p>No grounding improvement was demonstrated. Preserve this failure.</p></details>
    <a className="evidence-link" href="/review.html">View recorded evidence ↗</a>
  </aside>;
}

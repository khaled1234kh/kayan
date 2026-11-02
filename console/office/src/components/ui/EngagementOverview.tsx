import type { Actor } from '../../types';
import { EngagementLauncher } from './OperatorControls';
export function engagementLabel(actors: Actor[], running: boolean) {
  const enrolled = actors.filter(a => a.backendAgentId);
  if (!enrolled.length) return 'No assessment loaded';
  if (enrolled.some(a => a.state === 'blocked')) return running ? 'Attention required' : 'Partial / blocked assessment';
  if (running) return 'Assessment in progress';
  return enrolled.every(a => a.state === 'completed') ? 'Saved completed assessment' : 'Assessment ready';
}
export function EngagementOverview({actors,running,onSelect,gate}: {actors:Actor[];running:boolean;onSelect:(id:string)=>void;gate:'checking'|'available'|'unavailable'|'unknown'}) {
  const order=['planner','ai-manager','ai-sales','ai-ops','human'];
  return <aside className="engagement-zone" aria-label="Engagement overview">
    <div><span className="eyebrow">Engagement</span><h1>Operations</h1><p className="engagement-status">{engagementLabel(actors,running)}</p></div>
    <div className={`runtime-notice ${gate}`} role="status">{gate==='checking' ? 'Checking Gate availability…' : gate==='unknown' ? 'Gate status unknown: reconnect the console' : gate==='available' ? 'Gate responding · actions still require authorization' : 'Gate unavailable: recorded evidence mode'}</div>
    <EngagementLauncher running={running} hidePlanning gateAvailable={gate==='available'} />
    <section><h2>Assessment stages</h2><ol className="assessment-stages">{order.map((id,index) => {
      const actor=actors.find(a=>a.id===id);const state=actor?.backendAgentId ? actor.state : 'idle';
      return <li key={id} data-state={state}><button type="button" onClick={()=>onSelect(id)}><span className="stage-dot">{index+1}</span><span>{actor?.name.replace(' Agent','') ?? id}<small>{state}</small></span></button></li>;
    })}</ol></section>
    <details className="system-limits"><summary>System boundaries</summary><p>One shared local Qwen model; role-specific contracts. No fine-tuning or separate helper model. Planner coordinates, specialists execute only through TrustGate.</p><p>No grounding improvement was demonstrated. Preserve this failure.</p></details>
    <a className="evidence-link" href="/review.html">View recorded evidence ↗</a>
  </aside>;
}

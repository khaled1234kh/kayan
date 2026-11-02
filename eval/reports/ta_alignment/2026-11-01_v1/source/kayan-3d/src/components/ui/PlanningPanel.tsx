import { useEffect, useRef, useState } from 'react';
import { apiUrl } from '../../transport';
import { EngagementContextFields, type EngagementContext } from './EngagementContextFields';
import { illustrativeDisclaimer, presentationFor, selectedPresentation, type MitigationReport } from './mitigationPresentation';

interface RiskPlan {
  ranking_basis: string; uncertainty: string; status: string;
  risks: { id: string; title: string; hypothesis: string; reference: { id: string; name: string } }[];
}
async function planningRequest(path: string, context?: EngagementContext) {
  const response = await fetch(apiUrl.replace(/\/$/, '') + path, context === undefined ? undefined : {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ engagement_context: context }),
  });
  const result = await response.json();
  if (!response.ok) throw new Error(typeof result.detail === 'string' ? result.detail : JSON.stringify(result.detail));
  return result;
}

export function MitigationView({ report, selected, onSelection }: {
  report: MitigationReport; selected: string[]; onSelection: (ids: string[]) => void;
}) {
  const [filter, setFilter] = useState('All');
  const plan = report.mitigation_plan;
  const selection = selectedPresentation(report, selected);
  return <section className="mitigation-view">
    <h3>Option {plan.option} · mitigation plan</h3>
    <p>{report.evidence_label ?? plan.evidence_basis}</p>
    <p className="muted">{plan.method}</p><p className="muted">{plan.limits}</p>
    <p className="illustrative-label">{illustrativeDisclaimer}</p>
    <label>Recommendation grouping <select value={filter} onChange={e => setFilter(e.target.value)}>
      <option>All</option><option>Defense in Depth</option><option>Zero Trust</option>
    </select></label>
    <p><strong>{selection.total_illustrative_points} illustrative points</strong> · {selection.selected_ids.length} included recommendations. Filtering does not change inclusion.</p>
    {!plan.recommendations.length && <p>No matched recommendations. This does not establish an absence of risk.</p>}
    {!!plan.recommendations.length && filter !== 'All' && !plan.recommendations.some(item => presentationFor(item).frameworks.includes(filter)) && <p>No recommendations in this grouping. Included recommendations are unchanged.</p>}
    {plan.recommendations.filter(item => filter === 'All' || presentationFor(item).frameworks.includes(filter)).map(item => {
      const display = presentationFor(item);
      return <article key={item.id} className="mitigation-recommendation">
        <label><input type="checkbox" checked={selected.includes(item.id)} onChange={e => onSelection(e.target.checked ? [...selected, item.id] : selected.filter(id => id !== item.id))} /> Include: {item.title}</label>
        <p className="muted">{display.frameworks.join(' · ')} · {display.points} illustrative points</p>
        <p>{item.action}</p><small>Basis: {item.evidence_basis} · {(item.finding_ids.length ? item.finding_ids : item.risk_ids).join(', ')}</small>
        <p className="muted">{item.uncertainty}</p>
        <details><summary>Grounding references</summary>{item.references.map(ref => <p key={ref.id}><strong>{ref.id} · {ref.name}</strong><br />{ref.description}<br /><span className="muted">Source: {ref.source_url}</span></p>)}</details>
      </article>;
    })}
  </section>;
}

export function PlanningPanel({ onClose }: { onClose: () => void }) {
  const dialog = useRef<HTMLDialogElement>(null);
  const [context, setContext] = useState<EngagementContext>({});
  const [plan, setPlan] = useState<RiskPlan | null>(null);
  const [report, setReport] = useState<MitigationReport | null>(null);
  const [selected, setSelected] = useState<string[]>([]);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState('');
  useEffect(() => { if (dialog.current && !dialog.current.open) dialog.current.showModal(); }, []);
  async function request(kind: 'risk' | 'A' | 'B') {
    setPending(true); setError('');
    try {
      if (kind === 'risk') { setPlan(await planningRequest('/planning/risk-plan', context)); setReport(null); }
      else {
        const result: MitigationReport = await planningRequest(kind === 'A' ? '/planning/direct-mitigation' : '/planning/current-mitigation', kind === 'A' ? context : undefined);
        setReport(result); setSelected(result.mitigation_plan.recommendations.map(item => item.id));
      }
    } catch (failure) { setError(String(failure)); }
    finally { setPending(false); }
  }
  function exportReport() {
    if (!report) return;
    const blob = new Blob([JSON.stringify({ ...report, presentation_selection: selectedPresentation(report, selected) }, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob); const link = document.createElement('a');
    link.href = url; link.download = `kayan-mitigation-${report.engagement_id}.json`; link.click();
    window.setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  return <dialog className="planning-dialog" ref={dialog} onCancel={event => { event.preventDefault(); onClose(); }}>
    <header><h2>Risk planning and mitigation</h2><button type="button" className="btn" onClick={onClose}>Close</button></header>
    <p>Phase 1 and Option A read descriptions and local references only. They perform no target testing and produce no verified findings.</p>
    <fieldset disabled={pending}><EngagementContextFields value={context} onChange={value => { setContext(value); setPlan(null); setReport(null); }} /></fieldset>
    <div className="planning-actions">
      <button type="button" className="btn" disabled={pending} onClick={() => void request('risk')}>1. Generate hypothetical Risk Plan</button>
      <button type="button" className="btn" disabled={pending || !plan?.risks.length} onClick={() => void request('A')}>2. Option A · direct mitigation, no testing</button>
      <button type="button" className="btn" disabled={pending} onClick={() => void request('B')}>Option B · load completed assessment mitigation</button>
    </div>
    {pending && <p role="status">Preparing local report…</p>}{error && <p role="alert">{error}</p>}
    {plan && <section><h3>Phase 1 · hypothetical risks</h3><p>{plan.uncertainty}</p><p className="muted">{plan.ranking_basis}</p>
      {!plan.risks.length && <p>Insufficient description or no reference matches. Add relevant infrastructure/touchpoint details.</p>}
      <ol>{plan.risks.map(risk => <li key={risk.id}><strong>{risk.title}</strong><p>{risk.hypothesis}</p><small>Reference: {risk.reference.id} · {risk.reference.name}</small></li>)}</ol>
    </section>}
    {report && <><p className="muted">{report.context_label}</p>
      {!!Object.keys(report.narrative_context).length && <details><summary>Report narrative context</summary>
        {Object.entries(report.narrative_context).map(([key, value]) => <p key={key}><strong>{key.replace(/_/g, ' ')}:</strong> {value}</p>)}
      </details>}
      <MitigationView report={report} selected={selected} onSelection={setSelected} />
      <button type="button" className="btn" onClick={exportReport}>Export report with illustrative selection</button></>}
  </dialog>;
}

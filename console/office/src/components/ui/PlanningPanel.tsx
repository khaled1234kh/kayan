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
  let result;
  try { result = await response.json(); } catch { throw new Error('The console returned an unreadable response. Check the service and retry.'); }
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
    {report.assessment_completion && !report.assessment_completion.complete && <div className="coverage-warning" role="status">
      <strong>{report.assessment_completion.notice}</strong>
      <ul>{report.assessment_completion.specialist_outcomes.map(item => <li key={item.role}>{item.role}: {item.status}{item.error ? ` · ${item.error}` : ''}</li>)}</ul>
    </div>}
    <span className="basis-badge">{plan.option === 'A' ? 'Hypothetical, no testing' : `From saved assessment · ${report.findings.length} verified finding${report.findings.length === 1 ? '' : 's'}`}</span>
    <details className="how-it-works"><summary>How this works</summary><p>{report.evidence_label ?? plan.evidence_basis}</p><p>{plan.method}</p><p>{plan.limits}</p></details>
    <p className="illustrative-label">{illustrativeDisclaimer}</p>
    <label>Recommendation grouping <select value={filter} onChange={e => setFilter(e.target.value)}>
      <option>All</option><option>Defense in Depth</option><option>Zero Trust</option>
    </select></label>
    <div className="selection-summary"><strong>{selection.selected_ids.length} included · {selection.total_illustrative_points} illustrative point{selection.total_illustrative_points === 1 ? '' : 's'}</strong><small>Filtering does not change inclusion.</small></div>
    {!plan.recommendations.length && <p>No matched recommendations. This does not establish an absence of risk.</p>}
    {!!plan.recommendations.length && filter !== 'All' && !plan.recommendations.some(item => presentationFor(item).frameworks.includes(filter)) && <p>No recommendations in this grouping. Included recommendations are unchanged.</p>}
    {plan.recommendations.filter(item => filter === 'All' || presentationFor(item).frameworks.includes(filter)).map(item => {
      const display = presentationFor(item);
      return <article key={item.id} className="mitigation-recommendation">
        <label><input type="checkbox" checked={selected.includes(item.id)} onChange={e => onSelection(e.target.checked ? [...selected, item.id] : selected.filter(id => id !== item.id))} /> Include: {item.title}</label>
        <div className="recommendation-meta">{display.frameworks.map(framework => <span className="reference-chip" key={framework}>{framework}</span>)}<span>{display.points} illustrative point{display.points === 1 ? '' : 's'}</span></div>
        <p>{item.action}</p><details><summary>Evidence and identifiers</summary><small>Basis: {item.evidence_basis} · {(item.finding_ids.length ? item.finding_ids : item.risk_ids).join(', ')}</small></details>
        <p className="muted">{item.uncertainty}</p>
        <details><summary>Grounding references</summary>{item.references.map(ref => <p key={ref.id}><strong>{ref.id} · {ref.name}</strong><br />{ref.description}<br /><span className="muted">Source: {ref.source_url}</span></p>)}</details>
      </article>;
    })}
  </section>;
}

/** Friendly display only. The source technique and ranking remain unchanged. */
export function riskDisplay(reference: {id:string;name:string}) {
  const name=reference.name.toLowerCase();
  if (/customer relationship/.test(name)) return 'Possible exposure of customer information';
  if (/information repositor/.test(name)) return 'Possible access to sensitive information';
  if (/database|stored|repository|data from/.test(name)) return 'Possible exposure of stored data';
  if (/login|credential|identity|account/.test(name)) return 'Possible gaps in account protection';
  if (/application|web|sql|portal/.test(name)) return 'Possible exposure through application features';
  return 'Potential security control gaps to review';
}
export function planningFailure(failure: unknown): string {
  if (failure instanceof TypeError) return 'Console unavailable. Start the console backend and retry. Your inputs are preserved.';
  return failure instanceof Error ? failure.message : 'Unable to prepare this report. Check the console connection and retry.';
}
const sampleContext:EngagementContext = {infrastructure_summary:'Public web application with customer login and relational database.',
  data_storage:'Customer records stored in a relational database.',customer_touchpoints:'Public website and customer account portal.'};

export function PlanningPanel({ onClose }: { onClose: () => void }) {
  const dialog=useRef<HTMLDialogElement>(null);
  const [context,setContext]=useState<EngagementContext>({});
  const [sample,setSample]=useState(false);
  const [plan,setPlan]=useState<RiskPlan|null>(null);
  const [report,setReport]=useState<MitigationReport|null>(null);
  const [selected,setSelected]=useState<string[]>([]);
  const [step,setStep]=useState(1);
  const [option,setOption]=useState<'A'|'B'>('A');
  const [pending,setPending]=useState(false);
  const [error,setError]=useState('');
  useEffect(()=>{if(dialog.current&&!dialog.current.open) dialog.current.showModal();},[]);
  function changeContext(value:EngagementContext) {setContext(value);setPlan(null);setReport(null);setSelected([]);setError('');setSample(false);}
  async function request(kind:'risk'|'A'|'B') {
    setPending(true);setError('');
    if(kind!=='risk') {setReport(null);setSelected([]);}
    try {
      if(kind==='risk') {setPlan(await planningRequest('/planning/risk-plan',context));setReport(null);}
      else {const value:MitigationReport=await planningRequest(kind==='A'?'/planning/direct-mitigation':'/planning/current-mitigation',kind==='A'?context:undefined);
        setReport(value);setSelected(value.mitigation_plan.recommendations.map(item=>item.id));}
    } catch(failure) {setError(planningFailure(failure));}
    finally {setPending(false);}
  }
  function exportReport() {
    if(!report)return;
    const blob=new Blob([JSON.stringify({...report,presentation_selection:selectedPresentation(report,selected)},null,2)],{type:'application/json'});
    const url=URL.createObjectURL(blob);const link=document.createElement('a');link.href=url;link.download=`kayan-mitigation-${report.engagement_id}.json`;link.click();
    window.setTimeout(()=>URL.revokeObjectURL(url),1000);
  }
  const selection=report?selectedPresentation(report,selected):null;
  return <dialog className="planning-dialog planning-workspace" ref={dialog} aria-labelledby="planning-title" onCancel={e=>{e.preventDefault();onClose();}}>
    <header><div><span className="eyebrow">Planning workspace</span><h2 id="planning-title">From context to a clear plan</h2></div><button type="button" className="btn" onClick={onClose}>Close</button></header>
    <nav className="planning-stepper" aria-label="Planning steps">{['Risk Plan','Mitigation','Review & Export'].map((label,index)=><button type="button" key={label}
      aria-current={step===index+1?'step':undefined} disabled={pending || (index===1&&!plan?.risks.length&&option!=='B') || (index===2&&!report)} onClick={()=>setStep(index+1)}><span>{index+1}</span>{label}</button>)}</nav>
    <div className="planning-content" aria-busy={pending}>
    {step===1&&<section><div className="section-title"><div><h3>Start with your context</h3><p>Hypotheses from local references. No target testing or verified findings.</p></div>
      <button type="button" className="btn" disabled={pending} onClick={()=>{changeContext(sampleContext);setSample(true);}}>Use sample</button></div>
      {sample&&<p className="basis-badge">Hypothetical sample context · not facts about your organization</p>}
      <fieldset disabled={pending}><EngagementContextFields value={context} onChange={changeContext}/></fieldset>
      {plan&&<section className="risk-results"><h3>Hypothetical risks</h3><span className="basis-badge">Hypothetical, no testing</span>
        {!plan.risks.length&&<div className="empty-state"><strong>No matching hypotheses yet</strong><p>Add relevant infrastructure, data storage or customer touchpoint details. No matches does not establish safety.</p></div>}
        <div className="risk-cards">{plan.risks.map((risk,index)=><article className="risk-card" key={risk.id}><span className="eyebrow">Risk {index+1}</span><h3>{riskDisplay(risk.reference)}</h3>
          <p>This description may warrant review of {risk.reference.name.toLowerCase()}; applicability has not been tested.</p>
          <div className="risk-meta"><span className="reference-chip" title={risk.reference.name}>{risk.reference.id}</span><span className="hypothesis-badge">Hypothesis, not tested</span></div>
          <details><summary>Original reference and uncertainty</summary><p>{risk.title}</p><p>{risk.hypothesis}</p></details></article>)}</div>
        <details className="how-it-works"><summary>How this works</summary><p>{plan.uncertainty}</p><p>{plan.ranking_basis}</p></details>
      </section>}
    </section>}
    {step===2&&<section><h3>Choose your evidence path</h3><p>Direct planning and saved assessment results have different evidence bases.</p>
      <div className="option-selector" role="group" aria-label="Mitigation path">{(['A','B'] as const).map(value=><button type="button" className={option===value?'is-current':''} aria-pressed={option===value}
        key={value} disabled={pending} onClick={()=>{setOption(value);setReport(null);setSelected([]);setError('');}}>{value==='A'?'Option A · Direct mitigation':'Option B · From assessment'}</button>)}</div>
      {!report&&<div className="empty-state"><strong>{option==='A'?'Plan from hypotheses':'Use the saved governed assessment'}</strong><p>{option==='A'?'No live testing or verified findings.':'Loads a completed actual-model report. This does not start a new assessment.'}</p></div>}
      {report&&<MitigationView report={report} selected={selected} onSelection={setSelected}/>}
    </section>}
    {step===3&&report&&selection&&<section><h3>Review your selected plan</h3><span className="basis-badge">{option==='A'?'Hypothetical, no testing':`From saved assessment · ${report.findings.length} verified findings`}</span>
      <p className="illustrative-label">{illustrativeDisclaimer}</p><div className="selection-summary"><strong>{selection.selected_ids.length} included · {selection.total_illustrative_points} illustrative point{selection.total_illustrative_points===1?'':'s'}</strong></div>
      <ul className="review-selection">{report.mitigation_plan.recommendations.filter(item=>selected.includes(item.id)).map(item=><li key={item.id}><strong>{item.title}</strong><p>{item.action}</p></li>)}</ul>
      {!selected.length&&<p>No recommendations selected. The export retains the original report and records an empty selection.</p>}
      {report.assessment_completion&&!report.assessment_completion.complete&&<p className="coverage-warning">{report.assessment_completion.notice}</p>}
      <details className="how-it-works"><summary>Evidence, context and limits</summary><p>{report.context_label}</p><p>{report.mitigation_plan.limits}</p><p>{report.evidence_label}</p><code>{report.engagement_id}</code></details>
    </section>}
    {pending&&<p role="status" className="loading-state">{step===1?'Matching local references…':'Preparing the mitigation report…'}</p>}
    {error&&<div className="error-state" role="alert"><strong>Unable to load this step</strong><p>{error}</p><p>Check the console connection or the availability of a completed assessment, then retry.</p></div>}
    </div>
    <footer className="planning-footer"><button type="button" className="btn" disabled={pending||step===1} onClick={()=>setStep(value=>value-1)}>Back</button>
      {step===1&&<><button type="button" className="btn" disabled={pending} onClick={()=>{setOption('B');setReport(null);setStep(2);setError('');}}>Use saved assessment</button>
        <button type="button" className="btn btn-primary" disabled={pending} onClick={()=>plan?.risks.length?setStep(2):void request('risk')}>{plan?.risks.length?'Continue to mitigation':'Generate Risk Plan'}</button></>}
      {step===2&&<button type="button" className="btn btn-primary" disabled={pending||(option==='A'&&!plan?.risks.length)} onClick={()=>report?setStep(3):void request(option)}>{report?'Review selection':option==='A'?'Prepare direct mitigation':'Load saved assessment'}</button>}
      {step===3&&<button type="button" className="btn btn-primary" disabled={!report||pending} onClick={exportReport}>Export selected plan</button>}
    </footer>
  </dialog>;
}

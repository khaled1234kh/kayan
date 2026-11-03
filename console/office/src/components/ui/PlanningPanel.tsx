import { useEffect, useRef, useState } from 'react';
import { apiUrl } from '../../transport';
import {contextHasText,invalidContext,replaceContextField,type ContextField,type EngagementContext} from './EngagementContextFields';
import {OrganizationProfile,ContextSummary,planningSamples,readProfileDraft,writeProfileDraft} from './OrganizationProfile';
import { CoverageDetails, coverageRoleLabel } from './CoverageDetails';
import { CoordinationDetails } from './CoordinationDetails';
import { illustrativeDisclaimer, presentationFor, selectedPresentation, type MitigationReport } from './mitigationPresentation';

interface RiskPlan {
  context: EngagementContext;
  context_integrity?: {sha256:string};
  filtered_text_matches?: {id:string;name:string;reason:string}[];
  limitations?: string[];
  supported_scenario_count?:number;
  additional_supported_scenarios?:{scenario_id:string;title:string;reason:string}[];
  ranking_basis: string; uncertainty: string; status: string;
  risks: { id: string; title: string; hypothesis: string; why_relevant?:string;assumptions?:string;context_evidence?:{field:string;excerpt:string}[]; reference: { id: string; name: string } }[];
}
export function sameEnteredContext(expected:EngagementContext,actual:EngagementContext) {
  const snapshot=(value:EngagementContext)=>JSON.stringify(Object.entries(value).filter(([,text])=>text?.trim()).sort(([a],[b])=>a.localeCompare(b)));
  return snapshot(expected)===snapshot(actual);
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
      <ul>{report.assessment_completion.specialist_outcomes.map(item => <li key={item.role}>{coverageRoleLabel(item.role)}: {item.status}{item.error ? ` · ${item.error}` : ''}
        {item.coverage && !item.coverage.complete && <CoverageDetails coverage={item.coverage}/>}</li>)}</ul>
    </div>}
    <CoordinationDetails reviews={report.coordination_reviews ?? []}/>
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
        {item.controls?.length?<ol>{item.controls.map((control,index)=><li key={index}>{control}</li>)}</ol>:<p>{item.action}</p>}
        {!!item.context_evidence?.length&&<details><summary>Context behind this recommendation</summary>{item.context_evidence.map((e,index)=><blockquote key={index}><small>{e.field.replace(/_/g,' ')}</small><p>{e.excerpt}</p></blockquote>)}</details>}
        {!!item.validation_steps?.length&&<details><summary>How to review the control</summary><ul>{item.validation_steps.map((text,index)=><li key={index}>{text}</li>)}</ul></details>}
        <details><summary>Evidence and identifiers</summary><small>Basis: {item.evidence_basis} · {(item.finding_ids.length ? item.finding_ids : item.risk_ids).join(', ')}</small></details>
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
export function PlanningPanel({ onClose }: { onClose: () => void }) {
  const dialog=useRef<HTMLDialogElement>(null);
  const [draft]=useState(readProfileDraft);
  const [context,setContext]=useState<EngagementContext>(draft.context);
  const [sample,setSample]=useState(draft.sample);
  const [preview,setPreview]=useState(false);
  const [sampleIndex,setSampleIndex]=useState(0);
  const previousContext=useRef<{context:EngagementContext;sample:boolean}|null>(null);
  const [canRestore,setCanRestore]=useState(false);
  const [draftSaved,setDraftSaved]=useState(true);
  const [plan,setPlan]=useState<RiskPlan|null>(null);
  const [report,setReport]=useState<MitigationReport|null>(null);
  const [selected,setSelected]=useState<string[]>([]);
  const [step,setStep]=useState(1);
  const [option,setOption]=useState<'A'|'B'>('A');
  const [pending,setPending]=useState(false);
  const [error,setError]=useState('');
  useEffect(()=>{if(dialog.current&&!dialog.current.open) dialog.current.showModal();},[]);
  useEffect(()=>{setDraftSaved(writeProfileDraft(context,sample));},[context,sample]);
  function changeContext(value:EngagementContext) {setContext(value);setPlan(null);setReport(null);setSelected([]);setError('');setSample(false);}
  function editField(key:ContextField,text:string) {setContext(previous=>replaceContextField(previous,key,text));setPlan(null);setReport(null);setSelected([]);setError('');}
  function loadSample() {previousContext.current={context:{...context},sample};setCanRestore(true);changeContext({...planningSamples[sampleIndex].context});setSample(true);setPreview(false);}
  function clearDraft() {previousContext.current={context:{...context},sample};setCanRestore(true);changeContext({});setStep(1);}
  function restoreDraft() {if(previousContext.current){changeContext(previousContext.current.context);setSample(previousContext.current.sample);setCanRestore(false);}}
  async function request(kind:'risk'|'A'|'B') {
    setPending(true);setError('');
    if(kind!=='risk') {setReport(null);setSelected([]);}
    const submitted={...context};
    try {
      if(kind==='risk') {const value:RiskPlan=await planningRequest('/planning/risk-plan',submitted);
        if(!sameEnteredContext(submitted,value.context))throw new Error('The service returned different context. Your draft is preserved; do not export this result.');
        setPlan(value);setReport(null);setStep(2);}
      else {const value:MitigationReport=await planningRequest(kind==='A'?'/planning/direct-mitigation':'/planning/current-mitigation',kind==='A'?context:undefined);
        if(kind==='A'&&!sameEnteredContext(submitted,value.risk_plan?.context??{}))throw new Error('Returned report context differs from your draft. No report was accepted for export.');
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
    <header><div><span className="eyebrow">Planning workspace · offline by design</span><h2 id="planning-title">Security planning</h2></div><button type="button" className="btn" onClick={onClose}>Close</button></header>
    <nav className="planning-stepper" aria-label="Planning steps">{['Organization','Hypotheses','Mitigation','Review & Export'].map((label,index)=><button type="button" key={label}
      aria-current={step===index+1?'step':undefined} disabled={pending || (index===1&&!plan) || (index===2&&!plan?.risks.length&&option!=='B') || (index===3&&!report)} onClick={()=>setStep(index+1)}><span>{index+1}</span>{label}</button>)}</nav>
    <div className="planning-content" aria-busy={pending}>
    {step===1&&<section><div className="planning-paths"><div className="context-path"><span className="eyebrow">Option A · from your description</span><h3>Organization profile</h3><p>Hypotheses and review actions. No target testing.</p></div>
      <details className="saved-path"><summary>Option B · use saved assessment</summary><p>Build recommendations from verified results of an existing governed run. No new assessment starts.</p><button type="button" className="btn" disabled={pending} onClick={()=>{setOption('B');setReport(null);setStep(3);setError('');}}>Review saved assessment</button></details></div>
      <div className="profile-toolbar"><span className="basis-badge">Descriptive only · zero policy weight</span>{sample&&<small className="sample-origin">Started from fictional data · review edited fields</small>}<button type="button" className="btn" disabled={pending} onClick={()=>setPreview(value=>!value)}>Use sample</button>
        {contextHasText(context)&&<button type="button" className="btn" disabled={pending} onClick={clearDraft}>Clear draft</button>}
        {canRestore&&<button type="button" className="btn" disabled={pending} onClick={restoreDraft}>Restore previous inputs</button>}</div>
      {preview&&<section className="sample-preview" aria-label="Fictional sample preview"><h3>Preview fictional demonstration data</h3><label>Sample organization <select aria-label="Sample organization" value={sampleIndex} disabled={pending} onChange={event=>setSampleIndex(Number(event.target.value))}>{planningSamples.map((item,index)=><option key={item.name} value={index}>{item.name}</option>)}</select></label>
        <p>{planningSamples[sampleIndex].summary}</p><ContextSummary context={planningSamples[sampleIndex].context} title="Preview sample fields"/>
        <p>{contextHasText(context)?'Your existing fields will be replaced only when you choose Replace below. You can restore them afterward.':'Loading this sample fills all six fields with fictional data; you can edit every field.'}</p>
        <button type="button" className="btn btn-primary" disabled={pending} onClick={loadSample}>{contextHasText(context)?'Replace all inputs with sample':'Load fictional sample'}</button><button type="button" className="btn" disabled={pending} onClick={()=>setPreview(false)}>Cancel sample</button></section>}
      <OrganizationProfile value={context} onFieldChange={editField} disabled={pending}/>
      <ContextSummary context={context} title="Review exact input before analysis"/>
      <p className="muted draft-notice">{draftSaved?'Draft retained in this browser session when you close the workspace. Results are regenerated when reopened.':'Browser draft storage is unavailable; keep this workspace open to retain unsaved inputs.'}</p>
    </section>}
    {step===2&&plan&&<section className="risk-results"><div className="section-title"><div><span className="eyebrow">From the supplied organization profile</span><h3>Hypotheses to review</h3></div><span className="basis-badge">Hypothetical, no testing</span></div>
        <p>Ordered by context relevance. Severity, likelihood, impact and mitigation urgency have not been assessed.</p>
        {!plan.risks.length&&<div className="empty-state"><strong>Insufficient support for a specific scenario</strong><p>Add relevant assets, interfaces and known control concerns. We do not fill empty slots with weak text matches. No matches does not establish safety.</p></div>}
        <div className="risk-cards">{plan.risks.map((risk,index)=><article className="risk-card" key={risk.id}><span className="eyebrow">Relevance {index+1}</span><h3>{risk.title}</h3>
          <p>{risk.hypothesis}</p><details><summary>Why this fits your description</summary><p>{risk.why_relevant}</p>{risk.context_evidence?.map((item,i)=><blockquote key={i}><small>{item.field.replace(/_/g,' ')}</small><p>{item.excerpt}</p></blockquote>)}<p className="muted">{risk.assumptions}</p></details>
          <div className="risk-meta"><span className="reference-chip" title={risk.reference.name}>{risk.reference.id}</span><span className="hypothesis-badge">Hypothesis, not tested</span></div>
          </article>)}</div>
        <ContextSummary context={plan.context} title="Submitted context"/>
        <details className="how-it-works"><summary>How this works</summary><p>{plan.uncertainty}</p><p>{plan.ranking_basis}</p></details>
        {!!plan.filtered_text_matches?.length&&<details><summary>Excluded text-only matches</summary>{plan.filtered_text_matches.map(item=><p key={item.id}><strong>{item.id} · {item.name}</strong>: {item.reason}</p>)}</details>}
        {!!plan.additional_supported_scenarios?.length&&<details><summary>Additional supported context areas ({plan.additional_supported_scenarios.length})</summary><p>This view displays up to three relevance suggestions; it is not a complete risk inventory.</p>{plan.additional_supported_scenarios.map(item=><p key={item.scenario_id}><strong>{item.title}</strong>: {item.reason}</p>)}</details>}
      </section>}
    {step===3&&<section><h3>Choose your evidence path</h3><p>Direct planning and saved assessment results have different evidence bases.</p>
      <div className="option-selector" role="group" aria-label="Mitigation path">{(['A','B'] as const).map(value=><button type="button" className={option===value?'is-current':''} aria-pressed={option===value}
        key={value} disabled={pending} onClick={()=>{setOption(value);setReport(null);setSelected([]);setError('');}}>{value==='A'?'Option A · Direct mitigation':'Option B · From assessment'}</button>)}</div>
      {!report&&<div className="empty-state"><strong>{option==='A'?'Plan from hypotheses':'Use the saved governed assessment'}</strong><p>{option==='A'?'No live testing or verified findings.':'Loads a completed actual-model report. This does not start a new assessment.'}</p></div>}
      {report&&<MitigationView report={report} selected={selected} onSelection={setSelected}/>}
    </section>}
    {step===4&&report&&selection&&<section><h3>Review your selected plan</h3><span className="basis-badge">{option==='A'?'Hypothetical, no testing':`From saved assessment · ${report.findings.length} verified findings`}</span>
      <ContextSummary context={report.risk_plan?.context??report.narrative_context} title={option==='A'?'Exact context included in this export':'Context from the saved assessment'}/>
      {report.risk_plan?.context_integrity?.sha256&&<details><summary>Context integrity fingerprint</summary><code className="context-fingerprint">{report.risk_plan.context_integrity.sha256}</code><p>SHA-256 of the submitted nonblank fields. This is an integrity fingerprint, not a security assessment.</p></details>}
      <p className="illustrative-label">{illustrativeDisclaimer}</p><div className="selection-summary"><strong>{selection.selected_ids.length} included · {selection.total_illustrative_points} illustrative point{selection.total_illustrative_points===1?'':'s'}</strong></div>
      <ul className="review-selection">{report.mitigation_plan.recommendations.filter(item=>selected.includes(item.id)).map(item=><li key={item.id}><strong>{item.title}</strong><p>{item.action}</p></li>)}</ul>
      {!selected.length&&<p>No recommendations selected. The export retains the original report and records an empty selection.</p>}
      {report.assessment_completion&&!report.assessment_completion.complete&&<p className="coverage-warning">{report.assessment_completion.notice}</p>}
      <details className="how-it-works"><summary>Evidence, context and limits</summary><p>{report.context_label}</p><p>{report.mitigation_plan.limits}</p><p>{report.evidence_label}</p><code>{report.engagement_id}</code></details>
    </section>}
    {pending&&<p role="status" className="loading-state">{step===1?'Matching local scenarios…':'Preparing the mitigation report…'}</p>}
    {error&&<div className="error-state" role="alert"><strong>Unable to load this step</strong><p>{error}</p><p>Check the console connection or the availability of a completed assessment, then retry.</p></div>}
    </div>
    <footer className="planning-footer"><button type="button" className="btn" disabled={pending||step===1} onClick={()=>setStep(value=>value===3&&!plan?1:value-1)}>Back</button>
      {step===1&&<button type="button" className="btn btn-primary" disabled={pending||invalidContext(context)} onClick={()=>{setOption('A');void request('risk');}}>Generate Risk Plan</button>}
      {step===2&&<button type="button" className="btn btn-primary" disabled={!plan?.risks.length||pending} onClick={()=>{setOption('A');setStep(3);}}>Continue to mitigation</button>}
      {step===3&&<button type="button" className="btn btn-primary" disabled={pending||(option==='A'&&!plan?.risks.length)} onClick={()=>report?setStep(4):void request(option)}>{report?'Review selection':option==='A'?'Prepare direct mitigation':'Load saved assessment'}</button>}
      {step===4&&<button type="button" className="btn btn-primary" disabled={!report||pending} onClick={exportReport}>Export selected plan</button>}
    </footer>
  </dialog>;
}

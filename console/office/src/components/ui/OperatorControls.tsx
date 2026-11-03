import { useEffect, useRef, useState, type FormEvent } from 'react';
import { createPortal } from 'react-dom';
import type { Actor } from '../../types';
import { apiUrl } from '../../transport';
import { EngagementContextFields, invalidContext, type EngagementContext } from './EngagementContextFields';
import { PlanningWorkspace } from './PlanningWorkspace';

async function send(path: string, body: object) {
  const response = await fetch(apiUrl.replace(/\/$/, '') + path, {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
  });
  const data = await response.json();
  if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail ?? data));
  return data;
}

export function assessmentCanStart(operator:string,authorized:boolean,running:boolean,sending:boolean,gateAvailable:boolean,context:EngagementContext) {
  return !!operator.trim() && authorized && !running && !sending && gateAvailable && !invalidContext(context);
}

export function AssessmentSetup({operator,onOperator,context,onContext,authorized,onAuthorize,running,sending,gateAvailable,notice,onClose,onSubmit}: {
  operator:string;onOperator:(value:string)=>void;context:EngagementContext;onContext:(value:EngagementContext)=>void;
  authorized:boolean;onAuthorize:(value:boolean)=>void;running:boolean;sending:boolean;gateAvailable:boolean;notice:string;
  onClose:()=>void;onSubmit:(event:FormEvent)=>void;
}) {
  const dialog=useRef<HTMLDialogElement>(null);
  const operatorInput=useRef<HTMLInputElement>(null);
  useEffect(()=>{const view=dialog.current;view?.showModal();operatorInput.current?.focus();return()=>view?.close();},[]);
  const content=<dialog ref={dialog} className="assessment-dialog" aria-labelledby="assessment-title" onCancel={event=>{event.preventDefault();if(!sending)onClose();}}>
    <header className="modal-heading"><div><span className="eyebrow">Authorized lab assessment</span><h2 id="assessment-title">Set up an assessment</h2></div><button type="button" className="btn" disabled={sending} onClick={onClose}>Close setup</button></header>
    <form onSubmit={onSubmit}>
      <div className="assessment-body">
        <p className="setup-intro">Coordinate the five-agent workflow against the owned local lab. Review the scope before requesting a run.</p>
        <section className="setup-basics"><label>Operator name<input ref={operatorInput} aria-label="Operator name" value={operator} maxLength={100} required disabled={sending} onChange={event=>onOperator(event.target.value)}/><small>Recorded with the assessment request.</small></label>
          <div className="setup-target"><span className="eyebrow">Fixed target</span><strong>127.0.0.1:8888</strong><small>Owned vulnerable lab · no external targets</small></div></section>
        <fieldset className="assessment-context" disabled={sending}><EngagementContextFields value={context} onChange={onContext}/></fieldset>
        <section className="authorization-review"><h3>Scope & authorization</h3><p>Signed rules of engagement govern the lab-only techniques, time window and forbidden actions. TrustGate evaluates each requested action. Descriptive context cannot grant permission.</p>
          <label className="scope-confirmation"><input type="checkbox" checked={authorized} disabled={sending} onChange={event=>onAuthorize(event.target.checked)}/><span>I authorize assessment of this local lab.</span></label></section>
        {!gateAvailable&&<p role="status" className="coverage-warning">Gate unavailable. Inspect saved evidence or reconnect before requesting an assessment.</p>}
        {notice&&<p role="alert" className="operator-notice">{notice}</p>}
      </div>
      <footer className="modal-actions"><button type="button" className="btn" disabled={sending} onClick={onClose}>Cancel</button><span>Local model + per-action authorization</span><button type="submit" className="btn btn-primary" disabled={!assessmentCanStart(operator,authorized,running,sending,gateAvailable,context)}>{sending?'Requesting…':running?'Assessment active':'Start assessment'}</button></footer>
    </form>
  </dialog>;
  // Keep the modal outside a collapsed/hidden operations rail, including during resize.
  return typeof document==='undefined'?content:createPortal(content,document.body);
}

export function EngagementLauncher({running,hidePlanning=false,gateAvailable=true}: {running:boolean;hidePlanning?:boolean;gateAvailable?:boolean}) {
  const [expanded,setExpanded]=useState(false),[authorized,setAuthorized]=useState(false);
  const [operator,setOperator]=useState('Local operator'),[context,setContext]=useState<EngagementContext>({});
  const [planning,setPlanning]=useState(false),[sending,setSending]=useState(false),[notice,setNotice]=useState('');
  function close(){setExpanded(false);setAuthorized(false);setNotice('');}
  async function start(event:FormEvent){
    event.preventDefault();
    if(!assessmentCanStart(operator,authorized,running,sending,gateAvailable,context))return;
    setSending(true);setNotice('');
    try{
      await send('/engagement/start',{operator_id:operator,authorization:'I_AUTHORIZE_OWNED_LAB',engagement_context:context});
      setNotice('Assessment requested. Live state will appear as the runtime starts.');setAuthorized(false);setExpanded(false);
    }catch(error){setNotice(error instanceof Error?error.message:String(error));}finally{setSending(false);}
  }
  return <><div className="engagement-launcher"><div className="lab-target"><span className="eyebrow">Assessment scope</span><strong>Owned local lab</strong><code>127.0.0.1:8888</code></div>
    <button type="button" className="btn btn-primary" disabled={running||sending||!gateAvailable} onClick={()=>{setAuthorized(false);setNotice('');setExpanded(true);}}>{running?'Assessment active':'New assessment'}</button>
    {!expanded&&notice&&<p className="operator-notice" role="status">{notice}</p>}
    {!hidePlanning&&<button type="button" className="btn" onClick={()=>setPlanning(true)}>Risk planning / mitigation</button>}
  </div>{expanded&&<AssessmentSetup operator={operator} onOperator={setOperator} context={context} onContext={setContext} authorized={authorized} onAuthorize={setAuthorized} running={running} sending={sending} gateAvailable={gateAvailable} notice={notice} onClose={close} onSubmit={start}/>}
    {planning&&<PlanningWorkspace onClose={()=>setPlanning(false)}/>}</>;
}

export function AgentMessageComposer({ actor, gateAvailable = true }: { actor: Actor; gateAvailable?: boolean }) {
  const [kind, setKind] = useState<'status' | 'instruction'>('status');
  const [text, setText] = useState('');
  const [sending, setSending] = useState(false);
  const [notice, setNotice] = useState('');
  const canSend = gateAvailable && !!actor.backendAgentId && !!actor.engagementId && (kind === 'status' || actor.state !== 'completed');
  async function submit(event: FormEvent) {
    event.preventDefault(); setSending(true); setNotice('');
    try {
      const result = await send(`/agents/${encodeURIComponent(actor.backendAgentId!)}/messages`, {
        engagement_id: actor.engagementId, kind, text, operator_id: 'Local operator', source: 'operator',
      });
      setNotice(result.status === 'queued' ? 'Instruction queued for the next safe task boundary.' : 'Status question accepted. The governed reply will appear in this session.');
      setText('');
    } catch (error) { setNotice(String(error)); }
    finally { setSending(false); }
  }
  return <form className="operator-composer" onSubmit={submit}>
    <h3>Message this agent</h3>
    <label>Delivery <select value={kind} onChange={e => setKind(e.target.value as typeof kind)}>
      <option value="status">Status question · live</option><option value="instruction">Instruction · next safe boundary</option>
    </select></label>
    <textarea aria-label={`Message ${actor.name}`} placeholder="Ask about recorded progress or queue an instruction…" value={text} maxLength={2000} required rows={3} onChange={e => setText(e.target.value)} />
    <button className="btn" disabled={!canSend || sending}>{sending ? 'Submitting…' : 'Send through TrustGate'}</button>
    {!canSend && <p className="muted">{!gateAvailable ? 'Gate unavailable. Messages require live authorization; you can inspect saved records.' : !actor.backendAgentId ? 'Start an assessment to open a session.' : 'This agent has completed its tasks; status questions remain available.'}</p>}
    {notice && <p className="operator-notice" role="status">{notice}</p>}
  </form>;
}

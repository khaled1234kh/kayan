import { useState, type FormEvent } from 'react';
import type { Actor } from '../../types';
import { apiUrl } from '../../transport';
import { EngagementContextFields, type EngagementContext } from './EngagementContextFields';
import { PlanningPanel } from './PlanningPanel';

async function send(path: string, body: object) {
  const response = await fetch(apiUrl.replace(/\/$/, '') + path, {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
  });
  const data = await response.json();
  if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail ?? data));
  return data;
}

export function EngagementLauncher({ running }: { running: boolean }) {
  const [expanded, setExpanded] = useState(false);
  const [authorized, setAuthorized] = useState(false);
  const [operator, setOperator] = useState('Local operator');
  const [context, setContext] = useState<EngagementContext>({});
  const [planning, setPlanning] = useState(false);
  const [sending, setSending] = useState(false);
  const [notice, setNotice] = useState('');
  async function start(event: FormEvent) {
    event.preventDefault(); setSending(true); setNotice('');
    try {
      await send('/engagement/start', { operator_id: operator, authorization: 'I_AUTHORIZE_OWNED_LAB', engagement_context: context });
      setNotice('Assessment requested. Live state will appear as the runtime starts.'); setAuthorized(false); setExpanded(false);
    } catch (error) { setNotice(String(error)); }
    finally { setSending(false); }
  }
  return <><form className="engagement-launcher" onSubmit={start}>
    <strong>Security operations</strong><span className="muted">Owned lab · 127.0.0.1:8888</span>
    {!expanded ? <button type="button" className="btn" disabled={running || sending} onClick={() => setExpanded(true)}>{running ? 'Assessment active' : 'New assessment'}</button> : <>
    <label>Operator <input value={operator} maxLength={100} required onChange={e => setOperator(e.target.value)} /></label>
    <EngagementContextFields value={context} onChange={setContext} />
    <label className="scope-confirmation"><input type="checkbox" checked={authorized} onChange={e => setAuthorized(e.target.checked)} /> I authorize assessment of this local lab.</label>
    <button className="btn btn-primary" disabled={!authorized || sending || running}>{sending ? 'Requesting…' : running ? 'Assessment active' : 'Start assessment'}</button>
    <button type="button" className="btn" onClick={() => setExpanded(false)}>Cancel</button>
    </>}
    {notice && <p className="operator-notice" role="status">{notice}</p>}
    <button type="button" className="btn" onClick={() => setPlanning(true)}>Risk planning / mitigation</button>
  </form>{planning && <PlanningPanel onClose={() => setPlanning(false)} />}</>;
}

export function AgentMessageComposer({ actor }: { actor: Actor }) {
  const [kind, setKind] = useState<'status' | 'instruction'>('status');
  const [text, setText] = useState('');
  const [sending, setSending] = useState(false);
  const [notice, setNotice] = useState('');
  const canSend = !!actor.backendAgentId && !!actor.engagementId && (kind === 'status' || actor.state !== 'completed');
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
    {!canSend && <p className="muted">{!actor.backendAgentId ? 'Start an assessment to open a session.' : 'This agent has completed its tasks; status questions remain available.'}</p>}
    {notice && <p className="operator-notice" role="status">{notice}</p>}
  </form>;
}

import { useMemo, useState } from 'react';
import type { Actor, Task } from '../../types';
import { EVENT_DEFS, eventMessage, type KayanEvent } from '../../types/events';
import type { AgentMessage } from '../../agents/agentMessages';
import type { AgentHandoff } from '../../agents/handoffs';
import { AGENT_PROFILES, EXTERNAL_SENDERS } from '../../agents/agentProfiles';
import {
  buildAuditRows,
  buildSecurityEvidence,
  filterRows,
  findCollaborationEvidence,
  formatClock,
  type AuditFilter,
} from '../../audit/derive';
import { buildAuditCsv, buildAuditJson, downloadText } from '../../audit/exporters';

/**
 * Audit and evidence surface.
 *
 * Complements the actor inspector rather than replacing it: the inspector answers
 * "what is this seat doing now", this answers "what happened, in what order, and
 * why". Every value shown is derived from the live event stream.
 */

const FILTERS: Array<{ id: AuditFilter; label: string }> = [
  { id: 'all', label: 'All' },
  { id: 'security', label: 'Security' },
  { id: 'collaboration', label: 'Collaboration' },
  { id: 'task', label: 'Tasks' },
{ id: 'approval', label: 'Approvals' },
  { id: 'governance', label: 'Governance' },
];

const AGENT_NAMES: Record<string, string> = {
  ...Object.fromEntries(AGENT_PROFILES.map((p) => [p.id, p.name])),
  ...EXTERNAL_SENDERS,
};

function nameOf(id: string): string {
  return AGENT_NAMES[id] ?? id;
}

export function AuditView({
  events,
  messages,
  handoffs,
  actors,
  tasks,
  onClose,
}: {
  events: KayanEvent[];
  messages: AgentMessage[];
  handoffs: AgentHandoff[];
  actors: Actor[];
  tasks: Task[];
  onClose: () => void;
}) {
  const [filter, setFilter] = useState<AuditFilter>('all');
  const [selectedId, setSelectedId] = useState<string | null>(null);

  // Derived once per stream change, not per render.
  const rows = useMemo(() => buildAuditRows(events, EVENT_DEFS), [events]);
  const visible = useMemo(() => filterRows(rows, filter), [rows, filter]);
  const evidence = useMemo(() => buildSecurityEvidence(events), [events]);
  const messageById = useMemo(() => {
    const m = new Map<string, AgentMessage>();
    messages.forEach((x) => m.set(x.id, x));
    return m;
  }, [messages]);
  const handoffById = useMemo(() => {
    const h = new Map<string, AgentHandoff>();
    handoffs.forEach((x) => h.set(x.id, x));
    return h;
  }, [handoffs]);

const selected = rows.find((r) => r.eventId === selectedId) ?? null;
  const completed = tasks.length > 0 && tasks.every((t) => t.status === 'completed');

  function exportJson(): void {
    const data = buildAuditJson({
      events,
      messages,
      handoffs,
      actors,
      tasks,
      generatedAt: new Date().toISOString(),
    });
    downloadText('kayan-audit.json', JSON.stringify(data, null, 2), 'application/json');
  }

  function exportCsv(): void {
    const csv = buildAuditCsv({
      events,
      messages,
      handoffs,
      actors,
      tasks,
      generatedAt: new Date().toISOString(),
    });
    downloadText('kayan-audit.csv', csv, 'text/csv');
  }

  return (
    <div className="audit-overlay" data-testid="audit-view">
      <div className="audit-panel">
        <header className="audit-head">
          <div>
            <div className="panel-label">Audit</div>
            <div className="audit-title" data-testid="audit-title">
              Demo Order #1042
            </div>
            <div className="audit-meta" data-testid="audit-meta">
              {events.length} events Â· {messages.length} messages Â· {handoffs.length} handoffs Â·{' '}
              {evidence.length} security decision{evidence.length === 1 ? '' : 's'} Â·{' '}
              {completed ? 'Order completed' : 'In progress'}
            </div>
          </div>
          <div className="audit-actions">
            <button type="button" className="btn" onClick={exportJson} data-testid="export-json">
              Export JSON
            </button>
            <button type="button" className="btn" onClick={exportCsv} data-testid="export-csv">
              Export CSV
            </button>
            <button type="button" className="btn btn-primary" onClick={onClose} data-testid="audit-close">
              Close
            </button>
          </div>
        </header>

        <div className="audit-filters" role="tablist" aria-label="Audit filters">
          {FILTERS.map((f) => (
            <button
              key={f.id}
              type="button"
              role="tab"
              aria-selected={filter === f.id}
              className={`tab${filter === f.id ? ' is-active' : ''}`}
              onClick={() => setFilter(f.id)}
              data-testid={`filter-${f.id}`}
            >
              {f.label}
              <span className="tab-count">
                {f.id === 'all' ? rows.length : rows.filter((r) => r.category === f.id).length}
              </span>
            </button>
          ))}
        </div>

        <div className="audit-body">
          <div className="audit-table-wrap">
            <table className="audit-table" data-testid="audit-table">
              <thead>
                <tr>
                  <th>Time</th>
                  <th>Event</th>
                  <th>Actor</th>
                  <th>Target</th>
                  <th>Result</th>
                </tr>
              </thead>
              <tbody>
                {visible.map((r) => (
                  <tr
                    key={r.eventId}
                    className={`audit-row${r.eventId === selectedId ? ' is-selected' : ''}`}
                    onClick={() => setSelectedId(r.eventId)}
                    data-testid="audit-row"
                    data-event-type={r.event.type}
                  >
                    <td className="mono">{r.time}</td>
                    <td>{r.title}</td>
                    <td>{nameOf(r.actor)}</td>
                    <td>{r.target ? nameOf(r.target) : 'â€”'}</td>
                    <td className={r.result ? `result result-${r.result.toLowerCase()}` : ''}>
                      {r.result || 'â€”'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <aside className="audit-detail" data-testid="audit-detail">
            {!selected ? (
              <p className="muted">Select an event to inspect its evidence.</p>
            ) : (
              <EvidenceDetail
                row={selected}
                evidence={evidence}
                messageById={messageById}
                handoffById={handoffById}
                events={events}
                onSelect={setSelectedId}
              />
            )}
          </aside>
        </div>
      </div>
    </div>
  );
}

function EvidenceDetail({
  row,
  evidence,
  messageById,
  handoffById,
  events,
  onSelect,
}: {
  row: ReturnType<typeof buildAuditRows>[number];
  evidence: ReturnType<typeof buildSecurityEvidence>;
  messageById: Map<string, AgentMessage>;
  handoffById: Map<string, AgentHandoff>;
  events: KayanEvent[];
  onSelect: (id: string) => void;
}) {
  const event = row.event;

  // ---- security evidence: the causal chain ------------------------------
  const chain = evidence.find((e) => e.decisionEventId === event.id);
  if (chain) {
    const blocked = chain.blockedEventId
      ? events.find((e) => e.id === chain.blockedEventId)
      : null;
    const recovery = chain.recoveryEventIds
      .map((id) => events.find((e) => e.id === id))
      .filter((e): e is KayanEvent => Boolean(e));
    const recoveryMessage = chain.recoveryMessageId
      ? messageById.get(chain.recoveryMessageId)
      : undefined;

    return (
      <div data-testid="evidence-security">
        <div className="panel-label">TrustGate evidence</div>
        <div className="evidence-verdict">
          <span className={`chip ${chain.decision.decision === 'allow' ? 'chip-active' : 'chip-danger'}`} data-testid="evidence-decision">
            {chain.decision.decision === 'allow' ? 'Allowed' : 'Denied'}
          </span>
        </div>
        <div className="kv"><span className="k">Agent</span><span className="v">{chain.decision.subject}</span></div>
        <div className="kv"><span className="k">Intent</span><span className="v mono">{chain.intent.action}</span></div>
        <div className="kv"><span className="k">Resource</span><span className="v mono">{chain.intent.resource}</span></div>
        <div className="kv"><span className="k">Source</span><span className="v">{chain.intent.source}</span></div>
        <div className="kv"><span className="k">Policy</span><span className="v">{chain.decision.policy}</span></div>
        <div className="kv"><span className="k">Reason</span><span className="v">{chain.decision.reason}</span></div>

        <div className="block-label">Causal chain</div>
        <ol className="chain" data-testid="evidence-chain">
          <li className="chain-step">
            <span className="chain-n">1</span>
            <span className="chain-text">
              Intent â€” <span className="mono">{chain.intent.action}</span> on{' '}
              <span className="mono">{chain.intent.resource}</span>
            </span>
          </li>
          <li className="chain-step">
            <span className="chain-n">2</span>
            <span className="chain-text">
              TrustGate decision â€” {chain.decision.policy} Â·{' '}
              <strong>{chain.decision.decision.toUpperCase()}</strong>
            </span>
          </li>
          <li className="chain-step">
            <span className="chain-n">3</span>
            <button type="button" className="chain-link" onClick={() => onSelect(chain.decisionEventId)}>
              policy_denied
            </button>
          </li>
          <li className="chain-step">
            <span className="chain-n">4</span>
            {blocked ? (
              <button type="button" className="chain-link" onClick={() => onSelect(blocked.id)}>
                blocked â€” {chain.decision.subject} {String(blocked.payload?.message ?? '')}
              </button>
            ) : (
              <span className="chain-text">blocked â€” {chain.decision.subject}</span>
            )}
          </li>
          <li className="chain-step">
            <span className="chain-n">5</span>
            {recovery.length > 0 ? (
              <button type="button" className="chain-link" onClick={() => onSelect(recovery[0].id)}>
                authorized recovery â€” {eventMessage(recovery[0])}
              </button>
            ) : (
              <span className="chain-text">authorized recovery</span>
            )}
          </li>
        </ol>

        {recoveryMessage && (
          <div className="kv"><span className="k">Recovery result</span><span className="v">{recoveryMessage.instructions}</span></div>
        )}
      </div>
    );
  }

  // ---- collaboration evidence ------------------------------------------
  const collab = findCollaborationEvidence(event, [...handoffById.values()]);
  if (collab) {
    const message = messageById.get(collab.messageId);
    const handoff = collab.handoffId ? handoffById.get(collab.handoffId) : undefined;
    const reply = collab.replyToMessageId ? messageById.get(collab.replyToMessageId) : undefined;
    return (
      <div data-testid="evidence-collaboration">
        <div className="panel-label">Collaboration evidence</div>
        {message && (
          <>
            <div className="kv"><span className="k">From</span><span className="v">{nameOf(message.fromAgentId)}</span></div>
            <div className="kv"><span className="k">To</span><span className="v">{nameOf(message.toAgentId)}</span></div>
            <div className="kv"><span className="k">Type</span><span className="v">{message.type}</span></div>
            <div className="kv"><span className="k">Subject</span><span className="v">{message.subject}</span></div>
            {message.instructions && (
              <div className="kv"><span className="k">Request</span><span className="v">{message.instructions}</span></div>
            )}
            <div className="kv"><span className="k">Message id</span><span className="v mono">{message.id}</span></div>
            {message.expectedOutput && (
              <div className="kv"><span className="k">Expected output</span><span className="v">{message.expectedOutput}</span></div>
            )}
            {collab.replyToMessageId && (
              <div className="kv">
                <span className="k">Replies to</span>
                <span className="v mono">{collab.replyToMessageId}</span>
              </div>
            )}
            {reply && (
              <div className="kv">
                <span className="k">Answered by</span>
                <span className="v">{nameOf(reply.fromAgentId)}: {reply.instructions ?? reply.subject}</span>
              </div>
            )}
          </>
        )}
        {handoff && (
          <>
            <div className="block-label">Handoff</div>
            <div className="kv"><span className="k">Objective</span><span className="v">{handoff.objective}</span></div>
            <div className="kv"><span className="k">Task</span><span className="v mono">{handoff.taskId}</span></div>
            <div className="kv"><span className="k">Expected</span><span className="v">{handoff.expectedOutput}</span></div>
            <div className="kv"><span className="k">Status</span><span className="v">{handoff.status}</span></div>
            <div className="kv">
              <span className="k">Constraints</span>
              <span className="v">{handoff.constraints.join('; ')}</span>
            </div>
          </>
        )}
      </div>
    );
  }

  // ---- generic event detail --------------------------------------------
  return (
    <div data-testid="evidence-event">
      <div className="panel-label">Event</div>
      <div className="kv"><span className="k">Type</span><span className="v mono">{event.type}</span></div>
      <div className="kv"><span className="k">Event id</span><span className="v mono">{event.id}</span></div>
      <div className="kv"><span className="k">Actor</span><span className="v">{nameOf(event.actorId ?? 'System')}</span></div>
      <div className="kv"><span className="k">Task</span><span className="v mono">{event.taskId ?? 'â€”'}</span></div>
      <div className="kv"><span className="k">Time</span><span className="v mono">{formatClock(event.timestamp)}</span></div>
      <div className="kv"><span className="k">Detail</span><span className="v">{eventMessage(event)}</span></div>
    </div>
  );
}

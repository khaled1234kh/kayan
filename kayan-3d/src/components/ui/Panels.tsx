import { useState } from 'react';
import { COLORS, STATE_LABEL } from '../../data/layout';
import type { Actor, Task } from '../../types';
import { eventLevel, eventMessage, type KayanEvent } from '../../types/events';
import type { SecurityDecisionView as KayanSecurityDecision } from '../../security/policyTypes';
import type { AgentMessage } from '../../agents/agentMessages';
import type { AgentHandoff } from '../../agents/handoffs';
import type { AgentMailboxView } from '../../state/eventReducer';
import { getAgentProfile, AGENT_PROFILES, EXTERNAL_SENDERS } from '../../agents/agentProfiles';
import type { ConnectionState, EventSourceKind } from '../../transport';

/** Events the feed hides as transport/bookkeeping detail. */
const FEED_HIDDEN = new Set<KayanEvent['type']>(['agent_message_sent', 'agent_message_received']);

/** Events the feed hides as pure bookkeeping. */
const FEED_FILTERED = FEED_HIDDEN;

/** KAYAN branding + environment chip. */
export function TopBar({
  onAudit,
  onExperiment,
  onTasks,
  connection,
  sourceKind,
}: {
  onAudit: () => void;
  onExperiment: () => void;
  onTasks: () => void;
  /** Backend transport state; ignored in mock mode. */
  connection?: ConnectionState;
  sourceKind?: EventSourceKind;
}) {
  const chip =
    sourceKind === 'backend'
      ? {
          connected: { label: 'Backend connected', tone: 'ok' },
          connecting: { label: 'Connecting to backend', tone: 'wait' },
          reconnecting: { label: 'Reconnecting to backend', tone: 'wait' },
          disconnected: { label: 'Backend disconnected', tone: 'bad' },
          error: { label: 'Backend error', tone: 'bad' },
          idle: { label: 'Backend idle', tone: 'wait' },
        }[connection ?? 'idle']
      : { label: 'Local simulation', tone: 'ok' };

  return (
    <header className="topbar">
      <div className="brand">KAYAN</div>
      <div className="crumb">Operations / Office Floor</div>
      <div className="top-right">
        <span className="conn" data-testid="connection" data-connection={chip.tone}>
          <span className="conn-dot" />
          {chip.label}
        </span>
        <button type="button" className="btn" onClick={onTasks} data-testid="open-tasks">
          TASKS
        </button>
        <button type="button" className="btn" onClick={onExperiment} data-testid="open-experiment">
          EXPERIMENT
        </button>
        <button type="button" className="btn" onClick={onAudit} data-testid="open-audit">
          AUDIT
        </button>
      </div>
    </header>
  );
}

/** Primary demo control, plus the dev-only replay of the recorded run. */
export function DemoControls({
  running,
  canReplay,
  onRun,
  onReplay,
}: {
  running: boolean;
  canReplay: boolean;
  onRun: () => void;
  onReplay: () => void;
}) {
  return (
    <div className="demo-bar">
      <button type="button" className="btn btn-primary" onClick={onRun} disabled={running} data-testid="run-demo">
        {running ? 'Workflow runningâ€¦' : 'Run Demo Order'}
      </button>
      {import.meta.env.DEV && (
        <button
          type="button"
          className="btn"
          onClick={onReplay}
          disabled={running || !canReplay}
          data-testid="replay-demo"
          title="Development only: re-emit the last recorded event sequence"
        >
          Replay Demo
        </button>
      )}
      <span className="demo-hint">
        Scripted local workflow â€” every state change is driven by an emitted event.
      </span>
    </div>
  );
}

function stateChipClass(state: string): string {
  if (state === 'working' || state === 'completed') return 'chip chip-exec';
  if (state === 'waiting' || state === 'awaiting_approval') return 'chip chip-warn';
  if (state === 'blocked') return 'chip chip-danger';
  return 'chip chip-neutral';
}

/** Actor inspector. Plain React overlay â€” no text is drawn inside the 3D scene. */
/**
 * Activity panel â€” a pure view over the centralized event stream.
 *
 * It renders whatever events the store holds; there is no separate activity list
 * to keep in sync. Level and text come from the event catalogue.
 */
export function EventFeed({ events }: { events: KayanEvent[] }) {
  // Read straight from the event history. Transport-level message events are
  // filtered so the feed reads as a sequence of actions rather than raw traffic.
  const visible = events.filter((e) => !FEED_FILTERED.has(e.type));
  return (
    <aside className="panel panel-events" data-testid="event-feed">
      <div className="panel-label">Activity</div>
      {visible.length === 0 ? (
        <p className="muted">No events yet. Run the demo order to populate the feed.</p>
      ) : (
        <ul className="events">
          {visible.slice(0, 8).map((e) => (
            <li key={e.id} className={`event event-${eventLevel(e)}`} data-event-type={e.type}>
              <span className="event-time mono">
                {new Date(e.timestamp).toLocaleTimeString('en-GB', { hour12: false })}
              </span>
              <span className="event-msg">{eventMessage(e)}</span>
            </li>
          ))}
        </ul>
      )}
    </aside>
  );
}

/** One transcript line, derived from an actual message. */
function TranscriptLine({
  message,
  viewerId,
  nameById,
}: {
  message: AgentMessage;
  viewerId: string;
  nameById: Record<string, string>;
}) {
  const outgoing = message.fromAgentId === viewerId;
  const other = outgoing ? message.toAgentId : message.fromAgentId;
  return (
    <li className={`transcript-line${outgoing ? ' is-outgoing' : ''}`}>
      <span className="transcript-who">{nameById[message.fromAgentId] ?? message.fromAgentId}:</span>{' '}
      <span className="transcript-text">
        {message.instructions ?? message.subject}
      </span>
      {outgoing && <span className="transcript-arrow"> â†’ {nameById[other] ?? other}</span>}
    </li>
  );
}

/**
 * Agent inspector with collaboration sections.
 *
 * Every value shown here is read from reducer-derived state â€” inbox/outbox
 * counts, the active handoff and the transcript all come from the message
 * objects recorded in the event stream.
 */
export function Inspector({
  actor,
  task,
  messages,
  handoffs,
  mailbox,
  decision,
}: {
  actor: Actor | null;
  task: Task | null;
  messages: AgentMessage[];
  handoffs: AgentHandoff[];
  mailbox: AgentMailboxView | null;
  decision: KayanSecurityDecision | null;
}) {
  const [tab, setTab] = useState<'overview' | 'task' | 'inbox' | 'outbox' | 'activity'>('overview');

  if (!actor) {
    return (
      <aside className="panel panel-inspector" data-testid="inspector">
        <div className="panel-label">Actor</div>
        <p className="muted">Select an actor on the floor to inspect their state, authority and current task.</p>
      </aside>
    );
  }

  const nameById: Record<string, string> = {};
  AGENT_PROFILES.forEach((p) => {
    nameById[p.id] = p.name;
  });
  // External, non-seat senders appear in the transcript by name too.
  Object.entries(EXTERNAL_SENDERS).forEach(([id, name]) => {
    nameById[id] = name;
  });

  const transcript = messages.filter((m) => m.fromAgentId === actor.id || m.toAgentId === actor.id);
  const inbox = transcript.filter((m) => m.toAgentId === actor.id);
  const outbox = transcript.filter((m) => m.fromAgentId === actor.id);
  const activeHandoff = handoffs.find((h) => h.id === mailbox?.activeHandoffId) ?? null;
  const latestIncoming = [...handoffs].reverse().find((h) => h.toAgentId === actor.id) ?? null;
  const shownHandoff = activeHandoff ?? latestIncoming;

  const tabs: Array<{ id: typeof tab; label: string; count?: number }> = [
    { id: 'overview', label: 'Overview' },
    { id: 'task', label: 'Task' },
    { id: 'inbox', label: 'Inbox', count: inbox.length },
    { id: 'outbox', label: 'Outbox', count: outbox.length },
    { id: 'activity', label: 'Activity', count: transcript.length },
  ];

  return (
    <aside className="panel panel-inspector" data-testid="inspector">
      <div className="panel-label">Actor</div>
      <h2 className="panel-title" data-testid="actor-name">{actor.name}</h2>

      <div className="tabs" role="tablist">
        {tabs.map((t) => (
          <button
            key={t.id}
            type="button"
            role="tab"
            aria-selected={tab === t.id}
            className={`tab${tab === t.id ? ' is-active' : ''}`}
            onClick={() => setTab(t.id)}
            data-testid={`tab-${t.id}`}
          >
            {t.label}
            {t.count !== undefined && <span className="tab-count">{t.count}</span>}
          </button>
        ))}
      </div>

      {tab === 'overview' && (
        <>
          <div className="kv">
            <span className="k">Type</span>
            <span className="v">{actor.kind === 'human' ? 'Human' : 'AI Agent'}</span>
          </div>
          <div className="kv">
            <span className="k">Status</span>
            <span className={`chip ${stateChipClass(actor.state)}`} data-testid="actor-state">
              {STATE_LABEL[actor.state]}
            </span>
          </div>
          <div className="kv">
            <span className="k">Authority</span>
            <span className="v">{actor.authority}</span>
          </div>
          <div className="kv">
            <span className="k">Objective</span>
            <span className="v">{getAgentProfile(actor.id)?.objective}</span>
          </div>
{shownHandoff && (
            <div className="handoff-card" data-testid="active-handoff">
              <div className="handoff-head">
                <span className="k">Active handoff</span>
                <span className="handoff-status">{shownHandoff.status}</span>
              </div>
              <div className="handoff-path mono">
                {shownHandoff.fromAgentId} → {shownHandoff.toAgentId}
              </div>
              <div className="handoff-objective">{shownHandoff.objective}</div>
            </div>
          )}
          {/* TrustGate decision that concerns this seat, as operational state. */}
          {decision && decision.subject === actor.name && (
            <div className="security-inline" data-testid="actor-security">
              <div className="security-verdict">
                <span className="panel-title security-title">TrustGate</span>
                <span className={`chip ${decision.decision === 'deny' ? 'chip-danger' : 'chip-active'}`} data-testid="actor-security-decision">
                  {decision.decision === 'deny' ? 'Denied' : 'Allowed'}
                </span>
              </div>
              <div className="kv">
                <span className="k">Policy</span>
                <span className="v">{decision.policy}</span>
              </div>
              <div className="kv">
                <span className="k">Action</span>
                <span className="v">{decision.action}</span>
              </div>
              <div className="kv">
                <span className="k">Resource</span>
                <span className="v mono">{decision.resource}</span>
              </div>
              <div className="kv">
                <span className="k">Reason</span>
                <span className="v">{decision.reason}</span>
              </div>
            </div>
          )}
        </>
      )}

      {tab === 'task' && (
        <>
          <div className="kv">
            <span className="k">Current task</span>
            <span className="v">{task ? task.title : 'No active task'}</span>
          </div>
          <div className="kv">
            <span className="k">Task id</span>
            <span className="v mono">{actor.taskId ?? 'â€”'}</span>
          </div>
          <div className="kv">
            <span className="k">Activity</span>
            <span className="v">{actor.activity}</span>
          </div>
          <div className="block-label">Capabilities</div>
          <ul className="cap-list">
            {(getAgentProfile(actor.id)?.capabilities ?? []).map((c) => (
              <li key={c}>{c}</li>
            ))}
          </ul>
          <div className="block-label">Restrictions</div>
          <ul className="cap-list is-muted">
            {(getAgentProfile(actor.id)?.restrictions ?? []).map((c) => (
              <li key={c}>{c}</li>
            ))}
          </ul>
        </>
      )}

      {(tab === 'inbox' || tab === 'outbox') && (
        <div className="transcript" data-testid={`${tab}-list`}>
          {tab === 'inbox' && (
            <div className="kv">
              <span className="k">Inbox</span>
              <span className="v" data-testid="inbox-count">{inbox.length} message{inbox.length === 1 ? '' : 's'}</span>
            </div>
          )}
          {tab === 'outbox' && (
            <div className="kv">
              <span className="k">Outbox</span>
              <span className="v" data-testid="outbox-count">{outbox.length} message{outbox.length === 1 ? '' : 's'}</span>
            </div>
          )}
          {(tab === 'inbox' ? inbox : outbox).length === 0 ? (
            <p className="muted">No messages.</p>
          ) : (
            <ul className="transcript-list">
              {(tab === 'inbox' ? inbox : outbox).map((m) => (
                <TranscriptLine key={m.id} message={m} viewerId={actor.id} nameById={nameById} />
              ))}
            </ul>
          )}
        </div>
      )}

      {tab === 'activity' && (
        <div className="transcript">
          {transcript.length === 0 ? (
            <p className="muted">No collaboration traffic yet.</p>
          ) : (
            <ul className="transcript-list" data-testid="transcript">
              {transcript.map((m) => (
                <TranscriptLine key={m.id} message={m} viewerId={actor.id} nameById={nameById} />
              ))}
            </ul>
          )}
        </div>
      )}
    </aside>
  );
}

/**
 * TrustGate decision panel.
 *
 * Renders the latest decision lifted from the event stream by the reducer. It is
 * a read-only projection of history â€” there is no separate security channel, so a
 * denial always appears in the activity feed as well.
 */
export function TrustGatePanel({ decision }: { decision: KayanSecurityDecision | null }) {
  const denied = decision?.decision === 'deny';
  return (
    <aside className="panel panel-security" data-testid="trustgate-panel">
      <div className="panel-label">TrustGate</div>
      {!decision ? (
        <p className="muted" data-testid="security-empty">
          No security decisions yet.
        </p>
      ) : (
        <>
          <div className="security-verdict">
            <span className="panel-title security-title">Decision</span>
            <span
              className={`chip ${denied ? 'chip-danger' : 'chip-active'}`}
              data-testid="security-decision"
            >
              {denied ? 'Denied' : 'Allowed'}
            </span>
          </div>
          <div className="kv">
            <span className="k">Policy</span>
            <span className="v" data-testid="security-policy">{decision.policy}</span>
          </div>
          <div className="kv">
            <span className="k">Subject</span>
            <span className="v">{decision.subject}</span>
          </div>
          <div className="kv">
            <span className="k">Action</span>
            <span className="v">{decision.action}</span>
          </div>
          <div className="kv">
            <span className="k">Resource</span>
            <span className="v mono">{decision.resource}</span>
          </div>
          <div className="kv">
            <span className="k">Reason</span>
            <span className="v" data-testid="security-reason">{decision.reason}</span>
          </div>
        </>
      )}
    </aside>
  );
}

/** Legend so the colour language is readable without hovering. */
export function Legend() {
  const items: Array<[string, string]> = [
    [COLORS.teal, 'Working / completed'],
    [COLORS.orange, 'Waiting / approval'],
    [COLORS.red, 'Blocked'],
    [COLORS.muted, 'Idle'],
  ];
  return (
    <div className="legend">
      {items.map(([c, label]) => (
        <span className="legend-item" key={label}>
          <span className="legend-dot" style={{ background: c }} />
          {label}
        </span>
      ))}
    </div>
  );
}

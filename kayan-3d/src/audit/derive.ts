import type { Actor } from '../types';
import type { KayanEvent } from '../types/events';
import type { AgentMessage } from '../agents/agentMessages';
import type { AgentHandoff } from '../agents/handoffs';
import type { AgentIntent, PolicyDecision } from '../security/policyTypes';

/**
 * Audit / evidence derivation.
 *
 * Everything here is a pure projection of state that already exists: the event
 * stream, the message log, the handoffs and the actor list. No audit database, no
 * separate security log, no cached evidence. Delete the history and the audit
 * view correctly shows nothing â€” which is what makes it replay-safe.
 */

/** One row of the audit table. */
export interface AuditRow {
  /** Stable reference back into the event stream. */
  eventId: string;
  event: KayanEvent;
  time: string;
  title: string;
  actor: string;
  target: string;
  result: string;
  category: string;
}

/** The full causal chain behind one TrustGate denial. */
export interface SecurityEvidence {
  /** Event that carried the denial. The entry point of the chain. */
  decisionEventId: string;
  intent: AgentIntent;
  decision: PolicyDecision;
  /** `blocked` event that followed the denial, if any. */
  blockedEventId: string | null;
  /** Recovery: the authorized action the agent switched to. */
  recoveryEventIds: string[];
  /** The result the agent returned after recovering, if any. */
  recoveryMessageId: string | null;
}

/** Evidence for one collaboration event. */
export interface CollaborationEvidence {
  messageId: string;
  /** The message this one answers, when it is a reply. */
  replyToMessageId: string | null;
  /** Handoff carried by this message, if any. */
  handoffId: string | null;
}

export type AuditFilter =
  | 'all'
  | 'security'
  | 'collaboration'
  | 'task'
  | 'approval'
  | 'governance';

function pad(n: number): string {
  return n < 10 ? `0${n}` : String(n);
}

export function formatClock(timestamp: number): string {
  const d = new Date(timestamp);
  return `${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
}

function policyDecision(event: KayanEvent): PolicyDecision | null {
  const d = event.payload?.policyDecision as PolicyDecision | undefined;
  return d && typeof d.decision === 'string' ? d : null;
}

/**
 * Reads an `AgentMessage` out of a payload.
 *
 * The runtime stores the typed object under `agentMessage` and the human headline
 * under `message`, so both are checked. Lifecycle events that carry no message
 * return null instead of a headline string being mistaken for a message.
 */
function readAgentMessage(payload: Record<string, unknown> | undefined): AgentMessage | null {
  const candidates = [payload?.agentMessage, payload?.message];
  for (const c of candidates) {
    if (c && typeof c === 'object' && typeof (c as AgentMessage).id === 'string') {
      return c as AgentMessage;
    }
  }
  return null;
}

function readHandoff(payload: Record<string, unknown> | undefined): AgentHandoff | null {
  const h = payload?.handoff as unknown;
  return h && typeof h === 'object' && typeof (h as AgentHandoff).id === 'string'
    ? (h as AgentHandoff)
    : null;
}

/** Result column: the gate's verdict when there is one, else the catalogue level. */
function resultOf(event: KayanEvent): string {
  const decision = policyDecision(event);
  if (decision) return decision.decision === 'allow' ? 'ALLOW' : 'DENY';
  return '';
}

/** Target column: whoever or whatever the event acted on. */
function targetOf(event: KayanEvent): string {
  const message = readAgentMessage(event.payload);
  if (message && message.toAgentId) return message.toAgentId;
  const handoff = readHandoff(event.payload);
  if (handoff) return handoff.toAgentId;
  const intent = event.payload?.intent as AgentIntent | undefined;
  if (intent) return intent.resource;
  return event.taskId ?? '—';
}

/**
 * Audit rows, oldest first.
 *
 * The store keeps events newest-first for the activity feed; the audit view is a
 * chronological record, so it reverses a copy rather than mutating the store.
 */
export function buildAuditRows(events: KayanEvent[], defs: Record<string, { label: string; category: string }>): AuditRow[] {
  return [...events]
    .reverse()
    .map((event) => ({
      eventId: event.id,
      event,
      time: formatClock(event.timestamp),
      title: defs[event.type]?.label ?? event.type,
      actor: event.actorId ?? 'System',
      target: targetOf(event),
      result: resultOf(event),
      category: defs[event.type]?.category ?? 'task',
    }));
}

export function filterRows(rows: AuditRow[], filter: AuditFilter): AuditRow[] {
  if (filter === 'all') return rows;
  return rows.filter((r) => r.category === filter);
}

/**
 * Rebuilds one evidence chain per `policy_denied` event.
 *
 * Everything is located by typed references (event ids, message ids, intent
 * fields) rather than by matching message text.
 */
export function buildSecurityEvidence(events: KayanEvent[]): SecurityEvidence[] {
  const ordered = [...events].reverse();
  const out: SecurityEvidence[] = [];

  ordered.forEach((event, index) => {
    if (event.type !== 'policy_denied') return;
    const decision = policyDecision(event);
    const intent = event.payload?.intent as AgentIntent | undefined;
    if (!decision || !intent) return;

    const after = ordered.slice(index + 1);
    const sameActor = after.filter((e) => e.actorId === event.actorId);

    // Explicit `blocked` consequence.
    const blocked = sameActor.find((e) => e.type === 'blocked') ?? null;

    // Recovery: the agent resumes work after being blocked.
    const recovery: KayanEvent[] = [];
    if (blocked) {
      const afterBlock = after.slice(after.indexOf(blocked) + 1);
      for (const e of afterBlock) {
        if (e.actorId !== event.actorId) continue;
        if (e.type === 'task_started') {
          recovery.push(e);
          continue;
        }
        if (e.type === 'information_provided' || e.type === 'agent_response') {
          recovery.push(e);
          break;
        }
      }
    }

const recoveryMessage = recovery
      .map((e) => readAgentMessage(e.payload))
      .find((m): m is AgentMessage => m !== null);

    out.push({
      decisionEventId: event.id,
      intent,
      decision,
      blockedEventId: blocked?.id ?? null,
      recoveryEventIds: recovery.map((e) => e.id),
      recoveryMessageId: recoveryMessage?.id ?? null,
    });
  });

  return out;
}

/**
 * Resolves collaboration evidence for an event.
 *
 * Handles both shapes: a message carried in the payload, and a handoff-only event
 * (a delegation) whose originating message is referenced by `sourceMessageId`.
 */
export function findCollaborationEvidence(
  event: KayanEvent,
  handoffs: AgentHandoff[],
): CollaborationEvidence | null {
  const message = readAgentMessage(event.payload);
  const handoff = readHandoff(event.payload);
  const messageId =
    message?.id ?? handoff?.sourceMessageId ?? (typeof event.payload?.messageId === 'string' ? (event.payload.messageId as string) : undefined);
  const resolvedHandoff =
    handoff ??
    handoffs.find((h) => h.sourceMessageId === messageId) ??
    (typeof event.payload?.handoffId === 'string'
      ? handoffs.find((h) => h.id === (event.payload?.handoffId as string)) ?? null
      : null);
  if (!messageId) return null;
  return {
    messageId,
    replyToMessageId: message?.replyToMessageId ?? null,
    handoffId: resolvedHandoff?.id ?? null,
  };
}

/** Actor state at the end of the run, for the evidence panel's "current outcome". */
export function currentStates(actors: Actor[]): Record<string, string> {
  const out: Record<string, string> = {};
  actors.forEach((a) => {
    out[a.id] = a.state;
  });
  return out;
}

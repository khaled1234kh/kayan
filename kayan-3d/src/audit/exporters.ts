import type { Actor, Task } from '../types';
import type { KayanEvent } from '../types/events';
import type { AgentMessage } from '../agents/agentMessages';
import type { AgentHandoff } from '../agents/handoffs';
import { eventMessage } from '../types/events';
import type { PolicyDecision } from '../security/policyTypes';
import { buildSecurityEvidence, type SecurityEvidence } from './derive';

/**
 * Audit export.
 *
 * Both exporters are pure functions of the current run snapshot. They never
 * regenerate the workflow, never mutate state and never invent timestamps — the
 * output is exactly what the event stream already contains.
 */

export interface AuditExportInput {
  events: KayanEvent[];
  messages: AgentMessage[];
  handoffs: AgentHandoff[];
  actors: Actor[];
  tasks: Task[];
  /** ISO timestamp of when the export was requested. */
  generatedAt: string;
}

export interface AuditJson {
  run: {
    generatedAt: string;
    eventCount: number;
    messageCount: number;
    handoffCount: number;
    securityDecisionCount: number;
    taskIds: string[];
    workflowCompleted: boolean;
    /** Final actor states at export time. */
    actorStates: Record<string, string>;
  };
  events: Array<{
    id: string;
    type: string;
    timestamp: string;
    actorId: string | null;
    taskId: string | null;
    message: string;
  }>;
  messages: AgentMessage[];
  handoffs: AgentHandoff[];
  securityDecisions: SecurityEvidence[];
}

export function buildAuditJson(input: AuditExportInput): AuditJson {
  const ordered = [...input.events].reverse();
  const evidence = buildSecurityEvidence(input.events);
  const states: Record<string, string> = {};
  input.actors.forEach((a) => {
    states[a.id] = a.state;
  });

  return {
    run: {
      generatedAt: input.generatedAt,
      eventCount: input.events.length,
      messageCount: input.messages.length,
      handoffCount: input.handoffs.length,
      securityDecisionCount: evidence.length,
      taskIds: input.tasks.map((t) => t.id),
      workflowCompleted: input.tasks.every((t) => t.status === 'completed'),
      actorStates: states,
    },
    events: ordered.map((e) => ({
      id: e.id,
      type: e.type,
      timestamp: new Date(e.timestamp).toISOString(),
      actorId: e.actorId ?? null,
      taskId: e.taskId ?? null,
      message: eventMessage(e),
    })),
    messages: input.messages,
    handoffs: input.handoffs,
    securityDecisions: evidence,
  };
}

const CSV_COLUMNS = [
  'timestamp',
  'event_id',
  'event_type',
  'actor_id',
  'target_id',
  'task_id',
  'result',
  'message',
  'decision',
  'policy',
  'action',
  'resource',
  'reason',
] as const;

function csvCell(value: unknown): string {
  if (value === null || value === undefined) return '';
  const s = String(value);
  return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
}

export function buildAuditCsv(input: AuditExportInput): string {
  const ordered = [...input.events].reverse();
  const lines = [CSV_COLUMNS.join(',')];

  ordered.forEach((event) => {
    const decision = event.payload?.policyDecision as PolicyDecision | undefined;
    const candidates = [event.payload?.agentMessage, event.payload?.message];
    let message: AgentMessage | undefined;
    for (const c of candidates) {
      if (c && typeof c === 'object' && typeof (c as AgentMessage).id === 'string') {
        message = c as AgentMessage;
        break;
      }
    }
    const rawHandoff = event.payload?.handoff as unknown;
    const handoff =
      rawHandoff && typeof rawHandoff === 'object' && typeof (rawHandoff as AgentHandoff).id === 'string'
        ? (rawHandoff as AgentHandoff)
        : undefined;
    const target =
      message?.toAgentId ??
      handoff?.toAgentId ??
      (event.payload?.intent as { resource?: string } | undefined)?.resource ??
      '';

    lines.push(
      [
        new Date(event.timestamp).toISOString(),
        event.id,
        event.type,
        event.actorId ?? '',
        target,
        event.taskId ?? '',
        decision ? (decision.decision === 'allow' ? 'ALLOW' : 'DENY') : '',
        eventMessage(event),
        decision?.decision ?? '',
        decision?.policy ?? '',
        decision?.action ?? '',
        decision?.resource ?? '',
        decision?.reason ?? '',
      ]
        .map(csvCell)
        .join(','),
    );
  });

  return lines.join('\n');
}

/** Triggers a browser download without touching application state. */
export function downloadText(filename: string, contents: string, mime: string): void {
  const blob = new Blob([contents], { type: mime });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  document.body.removeChild(anchor);
  URL.revokeObjectURL(url);
}
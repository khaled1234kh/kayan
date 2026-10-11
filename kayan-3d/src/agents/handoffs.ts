/**
 * Handoff contract.
 *
 * A handoff is not a message: it is the explicit transfer of an objective from
 * one agent to another, with the context, constraints and expected output that
 * travel with it. This object is the future integration point for real agents.
 */

export type HandoffStatus = 'sent' | 'accepted' | 'completed' | 'rejected';

export interface AgentHandoff {
  id: string;
  fromAgentId: string;
  toAgentId: string;
  taskId: string;
  /** What the receiving agent is being asked to achieve. */
  objective: string;
  /** Everything the receiving agent needs to start. */
  context: Record<string, unknown>;
  /** Hard limits the receiving agent must respect. */
  constraints: string[];
  /** The artefact the receiving agent must return. */
  expectedOutput: string;
  status: HandoffStatus;
  /** Message that carried this handoff. */
  sourceMessageId?: string;
  timestamp: number;
}

export interface HandoffDraft {
  fromAgentId: string;
  toAgentId: string;
  taskId: string;
  objective: string;
  context?: Record<string, unknown>;
  constraints?: string[];
  expectedOutput: string;
  sourceMessageId?: string;
}

let handoffSeq = 0;

/** Creates a handoff in the `sent` state. */
export function createHandoff(draft: HandoffDraft, now: number): AgentHandoff {
  handoffSeq += 1;
  return {
    id: `hnd-${String(handoffSeq).padStart(4, '0')}`,
    fromAgentId: draft.fromAgentId,
    toAgentId: draft.toAgentId,
    taskId: draft.taskId,
    objective: draft.objective,
    context: draft.context ?? {},
    constraints: draft.constraints ?? [],
    expectedOutput: draft.expectedOutput,
    status: 'sent',
    sourceMessageId: draft.sourceMessageId,
    timestamp: now,
  };
}

/** Advances a handoff, returning a new object (never mutates). */
export function withHandoffStatus(
  handoff: AgentHandoff,
  status: HandoffStatus,
): AgentHandoff {
  return { ...handoff, status };
}
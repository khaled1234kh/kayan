/**
 * Agent-to-agent message contract.
 *
 * Messages are structured data, never display strings. The transcript and the
 * activity feed are both rendered from these objects, so copy can never drift
 * from the actual collaboration traffic.
 */

/** What a message is doing in the collaboration. */
export type AgentMessageType =
  | 'task'
  | 'question'
  | 'response'
  | 'handoff'
  | 'instruction'
  | 'approval_request'
  | 'approval_response';

export interface AgentMessage {
  id: string;
  fromAgentId: string;
  toAgentId: string;
  type: AgentMessageType;
  /** Short headline, e.g. "Request inventory information". */
  subject: string;
  /** Optional explicit instructions for the recipient. */
  instructions?: string;
  /** Structured payload the recipient acts on. */
  context?: Record<string, unknown>;
  /** What the sender expects back. */
  expectedOutput?: string;
  /** Set when this message answers an earlier one. */
  replyToMessageId?: string;
  /** Epoch ms. */
  timestamp: number;
  /** Delivery state, advanced by `agent_message_received`. */
  delivered: boolean;
}

export interface MessageDraft {
  fromAgentId: string;
  toAgentId: string;
  type: AgentMessageType;
  subject: string;
  instructions?: string;
  context?: Record<string, unknown>;
  expectedOutput?: string;
  replyToMessageId?: string;
}

let messageSeq = 0;

/** Creates a message with a stable, human-readable id. */
export function createMessage(draft: MessageDraft, now: number): AgentMessage {
  messageSeq += 1;
  return {
    id: `msg-${String(messageSeq).padStart(4, '0')}`,
    fromAgentId: draft.fromAgentId,
    toAgentId: draft.toAgentId,
    type: draft.type,
    subject: draft.subject,
    instructions: draft.instructions,
    context: draft.context,
    expectedOutput: draft.expectedOutput,
    replyToMessageId: draft.replyToMessageId,
    timestamp: now,
    delivered: false,
  };
}

/** Sender label used by the transcript. */
export function transcriptSpeaker(agentId: string, nameById: Record<string, string>): string {
  return nameById[agentId] ?? agentId;
}
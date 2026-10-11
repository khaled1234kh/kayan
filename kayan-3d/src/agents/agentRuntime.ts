import { createMessage, type AgentMessage, type AgentMessageType, type MessageDraft } from './agentMessages';
import { createHandoff, withHandoffStatus, type AgentHandoff, type HandoffDraft } from './handoffs';
import { isSeat } from './agentProfiles';
import type { KayanEventType } from '../types/events';
import type { AgentIntent, IntentSource } from '../security/policyTypes';

/**
 * Mock agent runtime.
 *
 * Owns collaboration behaviour: who talks to whom, what a handoff contains, and
 * the sequence of events that results. It deliberately does NOT know about actor
 * states, the reducer, Zustand or the 3D scene — it emits events and stops.
 *
 * Everything is deterministic and local. Replacing this with a real runtime
 * (prompt → model → parse → decide → send) means reimplementing this class, not
 * the UI: the event contract stays identical.
 */

/** How the runtime asks the application to publish an event. */
export type EventEmitter = (
  type: KayanEventType,
  actorId: string | undefined,
  payload?: Record<string, unknown>,
) => void;

/** Per-agent collaboration state. */
export interface AgentMailbox {
  inbox: AgentMessage[];
  outbox: AgentMessage[];
  /** Handoff currently owned by this agent, if any. */
  activeHandoffId: string | null;
  currentTaskId: string | null;
}

/**
 * Maps a message type onto the event that carries it. Kept here so the mapping
 * lives with the collaboration logic rather than being scattered in the reducer.
 */
const MESSAGE_EVENT: Record<AgentMessageType, KayanEventType> = {
  task: 'task_delegated',
  handoff: 'task_handoff',
  question: 'information_requested',
  response: 'information_provided',
  instruction: 'agent_question',
  approval_request: 'approval_requested',
  approval_response: 'approval_response',
};

export class MockAgentRuntime {
  private mailboxes = new Map<string, AgentMailbox>();
  private handoffs = new Map<string, AgentHandoff>();
  private messages = new Map<string, AgentMessage>();
  private intents: AgentIntent[] = [];

  constructor(
    agentIds: string[],
    private readonly emit: EventEmitter,
    private readonly now: () => number = () => Date.now(),
  ) {
    agentIds.forEach((id) => {
      this.mailboxes.set(id, { inbox: [], outbox: [], activeHandoffId: null, currentTaskId: null });
    });
  }

  /** Canonical message log, oldest first. Used for routing and inspection. */
  messageLog(): AgentMessage[] {
    return [...this.messages.values()].sort((a, b) => a.timestamp - b.timestamp);
  }

  handoffLog(): AgentHandoff[] {
    return [...this.handoffs.values()].sort((a, b) => a.timestamp - b.timestamp);
  }

  mailbox(agentId: string): AgentMailbox {
    const mb = this.mailboxes.get(agentId);
    if (!mb) throw new Error(`Unknown agent: ${agentId}`);
    return mb;
  }

  /**
   * Records an agent's intent to act, before any execution.
   *
   * Creating an intent is the agent's job; deciding it is TrustGate's job. The
   * runtime deliberately does not evaluate the intent here.
   */
  createIntent(
    agentId: string,
    action: string,
    resource: string,
    source: IntentSource,
    context?: Record<string, unknown>,
  ): AgentIntent {
    const intent: AgentIntent = { agentId, action, resource, source, context };
    this.intents.push(intent);
    return intent;
  }

  intentLog(): AgentIntent[] {
    return [...this.intents];
  }

  /** Current task an agent is working on, as tracked by delegation. */
  currentTaskOf(agentId: string): string | null {
    return this.mailbox(agentId).currentTaskId;
  }

  activeHandoffOf(agentId: string): AgentHandoff | null {
    const id = this.mailbox(agentId).activeHandoffId;
    return id ? this.handoffs.get(id) ?? null : null;
  }

  /**
   * Sends a structured message and emits the matching events.
   *
   * Emits `agent_message_sent` (transport) plus the semantic event for the
   * message type, so the activity feed reads as an action and the event stream
   * still records the raw message.
   */
  sendMessage(draft: MessageDraft): AgentMessage {
    const message = createMessage(draft, this.now());
    this.messages.set(message.id, message);
    // External senders (e.g. a supplier) have no mailbox of their own.
    if (isSeat(draft.fromAgentId)) {
      this.mailbox(draft.fromAgentId).outbox.push(message);
    }
    if (isSeat(draft.toAgentId)) {
      this.mailbox(draft.toAgentId).inbox.push(message);
    }

    // `message` is the feed headline; `agentMessage` is the typed object. The
    // keys are separate because a draft's context also carries a `message`
    // string, which would otherwise overwrite the object.
    this.emit('agent_message_sent', draft.fromAgentId, {
      message: draft.context?.message,
      agentMessage: message,
    });
    this.emit(MESSAGE_EVENT[draft.type], draft.fromAgentId, {
      ...(draft.context ?? {}),
      agentMessage: message,
    });
    return message;
  }

  /** Records delivery of a message to its recipient. */
  receiveMessage(messageId: string): void {
    const message = this.messages.get(messageId);
    if (!message || message.delivered) return;
    message.delivered = true;
    this.emit('agent_message_received', message.toAgentId, { messageId: message.id });
  }

  /** Answers an earlier message, threading the reply. */
  answerMessage(original: AgentMessage, response: Omit<MessageDraft, 'replyToMessageId'>): AgentMessage {
    return this.sendMessage({ ...response, replyToMessageId: original.id });
  }

  /**
   * Transfers an objective to another agent: creates the handoff, sends the
   * message that carries it, and marks the sender's involvement complete.
   */
  createHandoff(draft: HandoffDraft): AgentHandoff {
    const handoff = createHandoff(draft, this.now());
    this.handoffs.set(handoff.id, handoff);
    this.mailbox(handoff.toAgentId).currentTaskId = handoff.taskId;

    const message = this.sendMessage({
      fromAgentId: handoff.fromAgentId,
      toAgentId: handoff.toAgentId,
      type: 'handoff',
      subject: handoff.objective,
      instructions: handoff.constraints.join(' '),
      context: {
        handoffId: handoff.id,
        taskId: handoff.taskId,
        expectedOutput: handoff.expectedOutput,
        ...handoff.context,
      },
      expectedOutput: handoff.expectedOutput,
    });
    handoff.sourceMessageId = message.id;
    this.emit('task_delegated', handoff.fromAgentId, { handoff, taskId: handoff.taskId });
    return handoff;
  }

  /** Convenience wrapper: delegate work as an objective-carrying handoff. */
  delegateTask(draft: HandoffDraft): AgentHandoff {
    return this.createHandoff(draft);
  }

  /** The receiving agent accepts the handoff and starts work. */
  acceptHandoff(handoffId: string): AgentHandoff | null {
    const handoff = this.handoffs.get(handoffId);
    if (!handoff) return null;
    const accepted = withHandoffStatus(handoff, 'accepted');
    this.handoffs.set(handoffId, accepted);
    this.mailbox(accepted.toAgentId).activeHandoffId = accepted.id;
    this.emit('task_accepted', accepted.toAgentId, { handoff: accepted, taskId: accepted.taskId });
    return accepted;
  }

  /** The receiving agent returns the requested artefact. */
  completeHandoff(handoffId: string): AgentHandoff | null {
    const handoff = this.handoffs.get(handoffId);
    if (!handoff) return null;
    const done = withHandoffStatus(handoff, 'completed');
    this.handoffs.set(handoffId, done);
    const mb = this.mailbox(done.toAgentId);
    if (mb.activeHandoffId === done.id) mb.activeHandoffId = null;
    return done;
  }

  /** Clears per-agent collaboration state between runs. */
  reset(): void {
    this.messages.clear();
    this.handoffs.clear();
    this.intents = [];
    this.mailboxes.forEach((mb) => {
      mb.inbox = [];
      mb.outbox = [];
      mb.activeHandoffId = null;
      mb.currentTaskId = null;
    });
  }
}
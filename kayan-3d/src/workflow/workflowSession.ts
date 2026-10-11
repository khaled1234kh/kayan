import type { KayanEvent, KayanEventType } from '../types/events';
import type { CollabStep } from './collabWorkflow';
import { MockAgentRuntime } from '../agents/agentRuntime';
import { AGENT_IDS } from '../agents/agentProfiles';
import { authorizeIntent } from '../security/trustGate';
import type { PolicyDecision } from '../security/policyTypes';

/**
 * Workflow execution session.
 *
 * One workflow definition, executed two ways:
 *
 * - **Live demo** — `MockEventSource` schedules these steps with real timers and
 *   publishes to the store.
 * - **Experiment harness** — runs the identical steps synchronously on a virtual
 *   clock so repeated runs are fast and deterministic.
 *
 * The single experimental variable lives here: the policy mode applied when an
 * agent's intent reaches TrustGate.
 */
export type PolicyMode = 'enforced' | 'baseline';

/** Emits one event. Supplied by the caller so timing and recording stay external. */
export type StepEmitter = (
  type: KayanEventType,
  actorId: string | undefined,
  payload?: Record<string, unknown>,
) => void;

/**
 * Baseline decision for the simulated malicious action.
 *
 * Nothing is accessed: the unauthorized action is *recorded as allowed* so the
 * difference between conditions is observable. No policy_denied, no blocked.
 */
function simulatedAllow(
  agentId: string,
  action: string,
  resource: string,
): PolicyDecision {
  return {
    decision: 'allow',
    policy: 'Baseline · enforcement disabled',
    subject: agentId,
    action,
    resource,
    reason: 'Unauthorized action simulated as allowed — enforcement disabled for this condition',
  };
}

export class WorkflowSession {
  readonly runtime: MockAgentRuntime;
  private taskSeq = 0;
  private lastMessageId: string | null = null;
  private lastHandoffId: string | null = null;

  /**
   * The emitter is bound to the runtime so that every message the runtime sends
   * is recorded by the caller — including the `agent_message_sent` and semantic
   * message events. A no-op emitter here would silently drop them.
   */
  private readonly mode: PolicyMode;
  private readonly emit: StepEmitter;

  constructor(mode: PolicyMode, emit: StepEmitter) {
    this.mode = mode;
    this.emit = emit;
    this.runtime = new MockAgentRuntime(AGENT_IDS, this.emit);
  }

  /** Starts a new run and returns its task id. */
  beginRun(): string {
    this.taskSeq += 1;
    this.runtime.reset();
    this.lastMessageId = null;
    this.lastHandoffId = null;
    return this.currentTaskId();
  }

  currentTaskId(): string {
    return `TASK-${String(Math.max(1, this.taskSeq)).padStart(4, '0')}`;
  }

  /** Executes one workflow step, emitting through the bound emitter. */
  execute(step: CollabStep): void {
    switch (step.kind) {
      case 'event':
        this.emit(step.emit, step.actorId, { ...(step.payload ?? {}), message: step.message });
        return;

      case 'delegate': {
        const handoff = this.runtime.delegateTask({
          ...step.handoff,
          taskId: this.currentTaskId(),
        });
        this.lastHandoffId = handoff.id;
        this.emit('task_handoff', step.handoff.fromAgentId, { handoff, message: step.message });
        this.emit('plan_validated', step.handoff.fromAgentId, { message: 'Manager validated the plan' });
        return;
      }

      case 'accept': {
        if (!this.lastHandoffId) return;
        const handoff = this.runtime.acceptHandoff(this.lastHandoffId);
        if (handoff) {
          if (handoff.sourceMessageId) {
            this.runtime.receiveMessage(handoff.sourceMessageId);
            this.lastMessageId = handoff.sourceMessageId;
          }
          this.emit('task_started', handoff.toAgentId, {
            message: `${handoff.toAgentId} started work`,
          });
        }
        return;
      }

      case 'send': {
        const message = this.runtime.sendMessage({
          ...step.draft,
          context: { ...(step.draft.context ?? {}), taskId: this.currentTaskId() },
        });
        this.lastMessageId = message.id;
        return;
      }

      case 'receive':
        if (this.lastMessageId) this.runtime.receiveMessage(this.lastMessageId);
        return;

      case 'complete': {
        if (!this.lastHandoffId) return;
        const handoff = this.runtime.completeHandoff(this.lastHandoffId);
        if (handoff) {
          this.emit('task_completed', handoff.toAgentId, {
            handoff,
            message: 'Quotation handed back to the manager',
          });
        }
        return;
      }

      case 'intent': {
        const intent = this.runtime.createIntent(
          step.agentId,
          step.action,
          step.resource,
          step.source,
          { taskId: this.currentTaskId() },
        );

        // The only experimental difference: whether TrustGate is consulted.
        const decision =
          this.mode === 'enforced'
            ? authorizeIntent(intent)
            : simulatedAllow(intent.agentId, intent.action, intent.resource);

        if (decision.decision === 'allow') {
          if (this.mode === 'baseline' && step.deniedFollowUp) {
            // Record that an unauthorized action would have proceeded.
            this.emit('policy_violation', intent.agentId, {
              message: 'Unauthorized action simulated as allowed (enforcement disabled)',
              policyDecision: decision,
              intent,
            });
          }
          this.emit(step.allowed.type, intent.agentId, {
            message: step.allowed.message,
            policyDecision: decision,
          });
          return;
        }

        this.emit('policy_denied', intent.agentId, {
          message: step.deniedMessage,
          policyDecision: decision,
          intent,
        });
        if (step.deniedFollowUp) {
          this.emit(step.deniedFollowUp.type, intent.agentId, {
            message: step.deniedFollowUp.message,
          });
        }
        return;
      }

      default:
        return;
    }
  }
}

/** Convenience re-export so callers can type event arrays from one place. */
export type SessionEvent = KayanEvent;
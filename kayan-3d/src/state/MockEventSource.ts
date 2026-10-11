import type { KayanEvent, KayanEventSource, KayanEventType } from '../types/events';
import { COLLAB_WORKFLOW, type CollabStep } from '../workflow/collabWorkflow';
import { WorkflowSession } from '../workflow/workflowSession';
import type { MockAgentRuntime } from '../agents/agentRuntime';

/**
 * Mock event source — the live, timed driver for the demo.
 *
 * It owns wall-clock scheduling and event identity only. All workflow behaviour
 * lives in `WorkflowSession`, which the experiment harness reuses unchanged, so
 * the demo and the experiment can never drift apart.
 */
export class MockEventSource implements KayanEventSource {
  private listeners = new Set<(event: KayanEvent) => void>();
  private statusListeners = new Set<(running: boolean) => void>();
  private timers: number[] = [];
  private seq = 0;
  private recorded: KayanEvent[] = [];
  private running = false;
  private session = new WorkflowSession(
    'enforced',
    (type: KayanEventType, actorId?: string, payload?: Record<string, unknown>) =>
      this.emit(type, actorId, payload),
  );
  private taskId = 'TASK-0001';

  /** Collaboration runtime, exposed for the dev bridge and tests. */
  get runtime(): MockAgentRuntime {
    return this.session.runtime;
  }

  constructor() {
    this.taskId = this.session.beginRun();
  }

  subscribe(listener: (event: KayanEvent) => void): () => void {
    this.listeners.add(listener);
    return () => {
      this.listeners.delete(listener);
    };
  }

  subscribeStatus(listener: (running: boolean) => void): () => void {
    this.statusListeners.add(listener);
    return () => {
      this.statusListeners.delete(listener);
    };
  }

  history(): KayanEvent[] {
    return [...this.recorded];
  }

  private setRunning(next: boolean): void {
    if (this.running === next) return;
    this.running = next;
    this.statusListeners.forEach((l) => l(next));
  }

  private emit(
    type: KayanEventType,
    actorId?: string,
    payload?: Record<string, unknown>,
  ): void {
    this.seq += 1;
    const event: KayanEvent = {
      id: `evt-${String(this.seq).padStart(4, '0')}`,
      type,
      timestamp: Date.now(),
      actorId,
      taskId: this.taskId,
      payload,
    };
    this.recorded.push(event);
    this.listeners.forEach((l) => l(event));
    // A handoff-level completion also uses `task_completed`; only an
    // order-level completion ends the run.
    if (type === 'task_completed' && !payload?.handoff) this.setRunning(false);
  }

  runOrder(): void {
    if (this.running) return;
    this.cancelTimers();
    this.recorded = [];
    this.taskId = this.session.beginRun();
    this.setRunning(true);

    let elapsed = 0;
    for (const step of COLLAB_WORKFLOW) {
      elapsed += step.after;
      const at = elapsed;
      const timer = window.setTimeout(() => this.runStep(step), at);
      this.timers.push(timer);
    }
  }

  private runStep(step: CollabStep): void {
    this.session.execute(step);
  }

  /**
   * Replays a recorded history at its original relative cadence. Used by the
   * dev-only Replay control so runs are reproducible.
   */
  replay(history: KayanEvent[]): void {
    if (history.length === 0 || this.running) return;
    this.cancelTimers();
    this.setRunning(true);

    const t0 = history[0].timestamp;
    for (const recordedEvent of history) {
      const delay = Math.max(0, recordedEvent.timestamp - t0);
      const timer = window.setTimeout(() => {
        this.seq += 1;
        const event: KayanEvent = {
          ...recordedEvent,
          id: `evt-${String(this.seq).padStart(4, '0')}`,
          timestamp: Date.now(),
        };
        this.recorded.push(event);
        this.listeners.forEach((l) => l(event));
        if (event.type === 'task_completed' && !event.payload?.handoff) this.setRunning(false);
      }, delay);
      this.timers.push(timer);
    }
  }

  private cancelTimers(): void {
    this.timers.forEach((t) => window.clearTimeout(t));
    this.timers = [];
  }
}
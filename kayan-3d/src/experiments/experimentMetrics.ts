import type { KayanEvent } from '../types/events';
import type { DomainState } from '../state/eventReducer';
import type { ExperimentRun, ExperimentSummary, ExperimentMode, TimingMetric } from './experimentTypes';

/**
 * Experiment metrics.
 *
 * Everything here is measured from what a run actually produced — the events it
 * emitted and the timestamps on them. No expected values are hard-coded, and no
 * aggregate is invented.
 */

function firstEvent(events: KayanEvent[], type: string): KayanEvent | undefined {
  return events.find((e) => e.type === type);
}

function lastEvent(events: KayanEvent[], type: string): KayanEvent | undefined {
  for (let i = events.length - 1; i >= 0; i -= 1) {
    if (events[i].type === type) return events[i];
  }
  return undefined;
}

function allEvents(events: KayanEvent[], type: string): KayanEvent[] {
  return events.filter((e) => e.type === type);
}

function gap(from: KayanEvent | undefined, to: KayanEvent | undefined): number | null {
  if (!from || !to) return null;
  return to.timestamp - from.timestamp;
}

function readIntent(event: KayanEvent): { action?: string; resource?: string } | null {
  const intent = event.payload?.intent as { action?: string; resource?: string } | undefined;
  return intent ?? null;
}

/** Intervals between real events, in the order the proposal cares about. */
export function measureTimings(events: KayanEvent[]): TimingMetric[] {
  const start = firstEvent(events, 'order_received');
  const complete = lastEvent(events, 'task_completed');
  // The gate decides at the moment the intent is evaluated, so "intent → decision"
  // is measured from the arrival of the untrusted instruction that caused it.
  const decision = events.find((e) => e.type === 'policy_denied' || e.type === 'policy_violation');
  const instruction = decision
    ? [...events].reverse().find((e) => e.type === 'agent_question' && e.timestamp <= decision.timestamp)
    : undefined;
  const denial = firstEvent(events, 'policy_denied');
  const blocked = firstEvent(events, 'blocked');
  const recovery = blocked
    ? events.find((e) => e.actorId === blocked.actorId && e.type === 'task_started' && e.timestamp > blocked.timestamp)
    : undefined;

  const candidates: Array<[string, number | null]> = [
    ['order_start_to_completion', gap(start, complete)],
    ['instruction_received_to_policy_decision', gap(instruction, decision)],
    ['policy_denial_to_blocked', gap(denial, blocked)],
    ['blocked_to_authorized_recovery', gap(blocked, recovery)],
    ['authorized_recovery_to_completion', gap(recovery, complete)],
  ];

  return candidates
    .filter((c): c is [string, number] => c[1] !== null)
    .map(([name, durationMs]) => ({ name, durationMs }));
}

/** Builds the metrics for one finished run. */
export function measureRun(
  runId: string,
  seed: string,
  mode: ExperimentMode,
  events: KayanEvent[],
  state: DomainState,
): ExperimentRun {
  const ordered = [...events].sort((a, b) => a.timestamp - b.timestamp);
  const start = ordered[0]?.timestamp ?? 0;
  const end = ordered[ordered.length - 1]?.timestamp ?? start;

  const denials = allEvents(ordered, 'policy_denied');
  const violations = allEvents(ordered, 'policy_violation');
  const blocked = allEvents(ordered, 'blocked');
  const decisions = ordered.filter((e) => e.payload?.policyDecision !== undefined);

  const intentEvent = ordered.find((e) => readIntent(e) !== null);
  const recovery = blocked.find((b) =>
    ordered.some((e) => e.actorId === b.actorId && e.type === 'task_started' && e.timestamp > b.timestamp),
  );

  const orderComplete = allEvents(ordered, 'task_completed').some((e) => e.payload?.handoff === undefined);
  const finalStates = state.actors.map((a) => a.state);
  const uniformFinal = finalStates.every((s) => s === finalStates[0]) ? finalStates[0] : finalStates.join(',');

  return {
    runId,
    seed,
    mode,
    startedAt: start,
    completedAt: end,
    durationMs: end - start,
    completed: orderComplete,
    eventCount: ordered.length,
    messageCount: state.collaboration.messages.length,
    handoffCount: state.collaboration.handoffs.length,
    policyDecisionCount: decisions.length,
    denialCount: denials.length,
    violationCount: violations.length,
    blockedCount: blocked.length,
    recoveryCount: recovery ? 1 : 0,
    unauthorizedActionAttempted: intentEvent !== undefined,
    unauthorizedActionAllowed: violations.length > 0 && denials.length === 0,
    finalState: uniformFinal,
    timings: measureTimings(ordered),
  };
}

function average(values: number[]): number {
  if (values.length === 0) return 0;
  return values.reduce((a, b) => a + b, 0) / values.length;
}

/** Descriptive aggregate for one condition. */
export function summarise(mode: ExperimentMode, runs: ExperimentRun[]): ExperimentSummary {
  const durations = runs.map((r) => r.durationMs);
  return {
    mode,
    runs: runs.length,
    completedRuns: runs.filter((r) => r.completed).length,
    averageDurationMs: Math.round(average(durations)),
    minDurationMs: durations.length ? Math.min(...durations) : 0,
    maxDurationMs: durations.length ? Math.max(...durations) : 0,
    averageEventCount: Math.round(average(runs.map((r) => r.eventCount))),
    averageMessageCount: Math.round(average(runs.map((r) => r.messageCount))),
    averageHandoffCount: Math.round(average(runs.map((r) => r.handoffCount))),
    totalPolicyDecisions: runs.reduce((a, r) => a + r.policyDecisionCount, 0),
    totalDenials: runs.reduce((a, r) => a + r.denialCount, 0),
    totalViolations: runs.reduce((a, r) => a + r.violationCount, 0),
    totalBlocked: runs.reduce((a, r) => a + r.blockedCount, 0),
    totalRecoveries: runs.reduce((a, r) => a + r.recoveryCount, 0),
    unauthorizedActionsAttempted: runs.filter((r) => r.unauthorizedActionAttempted).length,
    unauthorizedActionsAllowed: runs.filter((r) => r.unauthorizedActionAllowed).length,
  };
}
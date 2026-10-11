/**
 * Backend experiment client.
 *
 * The backend owns experiment execution and every metric. This module only
 * fetches persisted results and adapts them to the shapes the existing UI and
 * exporters already use, so `ExperimentView`, the comparison table and the
 * JSON/CSV exporters need no rewrite.
 *
 * Nothing here executes a workflow or computes a security outcome: it reads
 * backend-owned records and formats them.
 */

import type { KayanEvent } from '../types/events';
import type { ExperimentResult, ExperimentRun, ExperimentSummary } from '../experiments/experimentTypes';

/** Persisted comparison, as returned by the backend. */
export interface BackendExperimentPayload {
  experiment: {
    id: string;
    orderId: string;
    seed: string;
    runsPerCondition: number;
    status: 'running' | 'completed' | 'partially_failed' | 'failed';
    startedAt: string | null;
    completedAt: string | null;
    error: string | null;
  };
  comparison: {
    seed: string;
    runsPerCondition: number;
    baseline: ExperimentSummary & { failedRuns?: number };
    enforced: ExperimentSummary & { failedRuns?: number };
  };
  runs: BackendRunPayload[];
  progress: {
    totalTrials: number;
    recordedTrials: number;
    completedTrials: number;
    failedTrials: number;
  };
}

export interface BackendRunPayload {
  runId: string;
  experimentId: string | null;
  orderId: string;
  condition: 'baseline' | 'enforced' | null;
  seed: string | null;
  runIndex: number;
  startedAt: string | null;
  completedAt: string | null;
  durationMs: number;
  wallClockMs: number;
  completed: boolean;
  status: string;
  eventCount: number;
  messageCount: number;
  handoffCount: number;
  policyDecisionCount: number;
  denialCount: number;
  violationCount: number;
  blockedCount: number;
  recoveryCount: number;
  unauthorizedActionAttempted: boolean;
  unauthorizedActionAllowed: boolean;
  finalState: string | null;
  error: string | null;
  timings: Array<{ name: string; durationMs: number }>;
}

/** A backend run projected onto the existing frontend run record. */
export function toExperimentRun(run: BackendRunPayload): ExperimentRun {
  return {
    runId: run.runId,
    seed: run.seed ?? '',
    // A trial always has a condition; the field is renamed for the UI contract.
    mode: (run.condition ?? 'enforced') as ExperimentRun['mode'],
    startedAt: run.startedAt ? Date.parse(run.startedAt) : 0,
    completedAt: run.completedAt ? Date.parse(run.completedAt) : 0,
    durationMs: run.durationMs,
    completed: run.completed,
    eventCount: run.eventCount,
    messageCount: run.messageCount,
    handoffCount: run.handoffCount,
    policyDecisionCount: run.policyDecisionCount,
    denialCount: run.denialCount,
    violationCount: run.violationCount,
    blockedCount: run.blockedCount,
    recoveryCount: run.recoveryCount,
    unauthorizedActionAttempted: run.unauthorizedActionAttempted,
    unauthorizedActionAllowed: run.unauthorizedActionAllowed,
    finalState: run.finalState ?? 'unknown',
    timings: run.timings.map((t) => ({ name: t.name, durationMs: t.durationMs })),
  };
}

/**
 * Adapt a persisted comparison to the shape the existing view and exporters use.
 *
 * `runEvents` stays empty on purpose: in backend mode a trial's events are
 * fetched on demand from the run-scoped history endpoint, so evidence is never
 * duplicated into a browser-side copy.
 */
export function toExperimentResult(payload: BackendExperimentPayload): ExperimentResult {
  return {
    seed: payload.comparison.seed,
    runsPerCondition: payload.comparison.runsPerCondition,
    comparison: {
      seed: payload.comparison.seed,
      runsPerCondition: payload.comparison.runsPerCondition,
      baseline: payload.comparison.baseline,
      enforced: payload.comparison.enforced,
    },
    runs: payload.runs.map(toExperimentRun),
    runEvents: {},
  };
}

/** Fetch one comparison's persisted state and results. */
export async function fetchExperiment(apiUrl: string, experimentId: string): Promise<BackendExperimentPayload> {
  const res = await fetch(`${apiUrl.replace(/\/+$/, '')}/api/experiments/${experimentId}`);
  if (!res.ok) throw new Error(`GET /api/experiments/${experimentId} -> ${res.status}`);
  return (await res.json()) as BackendExperimentPayload;
}

/**
 * One trial's recorded events, in sequence order.
 *
 * This is what makes a selected trial's audit evidence isolable: the events are
 * the backend's, fetched by their owning run.
 */
export async function fetchRunEvents(apiUrl: string, runId: string): Promise<KayanEvent[]> {
  const res = await fetch(
    `${apiUrl.replace(/\/+$/, '')}/api/experiments/runs/${runId}/events`,
  );
  if (!res.ok) throw new Error(`GET /api/experiments/runs/${runId}/events -> ${res.status}`);
  // The history endpoint sends the client event contract plus runId.
  const body = (await res.json()) as {
    events: Array<KayanEvent & { runId?: string }>;
  };
  // The history endpoint sends the client contract plus runId; strip the extra
  // field so the reducer receives exactly the event it expects.
  return body.events.map(({ runId: _runId, ...event }) => event as KayanEvent);
}

/** Most recent comparisons, for restoring a view after a reload. */
export async function listExperiments(apiUrl: string): Promise<
  Array<{ id: string; status: string; seed: string; runsPerCondition: number }>
> {
  const res = await fetch(`${apiUrl.replace(/\/+$/, '')}/api/experiments`);
  if (!res.ok) return [];
  return (await res.json()) as Array<{
    id: string;
    status: string;
    seed: string;
    runsPerCondition: number;
  }>;
}
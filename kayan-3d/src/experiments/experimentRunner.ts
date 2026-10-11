import type { KayanEvent, KayanEventType } from '../types/events';
import { COLLAB_WORKFLOW } from '../workflow/collabWorkflow';
import { WorkflowSession, type PolicyMode } from '../workflow/workflowSession';
import { initialDomainState, reduce, type DomainState } from '../state/eventReducer';
import { measureRun, summarise } from './experimentMetrics';
import {
  DEFAULT_RUNS,
  EXPERIMENT_SEED,
  type ExperimentComparison,
  type ExperimentMode,
  type ExperimentResult,
  type ExperimentRun,
} from './experimentTypes';

/**
 * Experiment runner.
 *
 * Executes the *same* workflow the live demo uses, but synchronously on a virtual
 * clock so repeated runs are fast and reproducible.
 *
 * On timing: the harness does not sleep between steps. Each step advances the
 * clock by the same `after` delay the live workflow uses, so measured durations
 * are the workflow's real logical timings rather than an artefact of scheduling.
 * Nothing in the workflow is sped up or slowed to flatter the numbers.
 */

export interface RunOptions {
  seed?: string;
  /** Runs to execute for this condition. */
  runs?: number;
}

interface SingleRunResult {
  run: ExperimentRun;
  events: KayanEvent[];
}

/** Signature of the shared workflow steps, so callers can assert it is unchanged. */
export function stepSignature(): string[] {
  return COLLAB_WORKFLOW.map((s) => s.kind === 'event' ? s.emit : s.kind);
}

/** Runs one condition N times and returns each run's metrics plus its events. */
export function runExperiment(mode: ExperimentMode, options: RunOptions = {}): {
  runs: ExperimentRun[];
  runEvents: Record<string, KayanEvent[]>;
} {
  const seed = options.seed ?? EXPERIMENT_SEED;
  const count = Math.max(1, Math.min(50, options.runs ?? DEFAULT_RUNS));
  const runs: ExperimentRun[] = [];
  const runEvents: Record<string, KayanEvent[]> = {};

  for (let i = 0; i < count; i += 1) {
    const result = executeRun(mode, seed, i);
    runs.push(result.run);
    runEvents[result.run.runId] = result.events;
  }

  return { runs, runEvents };
}

function executeRun(mode: ExperimentMode, seed: string, index: number): SingleRunResult {
  const events: KayanEvent[] = [];
  let state: DomainState = initialDomainState();
  let seq = 0;
  const wallStart = Date.now();
  let clock = wallStart;

  const emit = (
    type: KayanEventType,
    actorId?: string,
    payload?: Record<string, unknown>,
  ): void => {
    seq += 1;
    const event: KayanEvent = {
      id: `evt-${String(seq).padStart(4, '0')}`,
      type,
      timestamp: clock,
      actorId,
      taskId: session.currentTaskId(),
      payload,
    };
    events.push(event);
    state = reduce(state, event);
  };

  const session = new WorkflowSession(mode as PolicyMode, emit);
  session.beginRun();

  // Virtual clock: advance by the workflow's own step delay, never by sleeping.
  COLLAB_WORKFLOW.forEach((step) => {
    clock += step.after;
    session.execute(step);
  });

  const runId = `${mode}-${String(index + 1).padStart(3, '0')}`;
  const run = measureRun(runId, seed, mode, events, state);
  return { run, events };
}

/** Runs baseline then enforced with the same seed and run count. */
export function runComparison(options: RunOptions = {}): ExperimentResult {
  const seed = options.seed ?? EXPERIMENT_SEED;
  const runsPerCondition = Math.max(1, Math.min(50, options.runs ?? DEFAULT_RUNS));

  const baseline = runExperiment('baseline', { seed, runs: runsPerCondition });
  const enforced = runExperiment('enforced', { seed, runs: runsPerCondition });

  const comparison: ExperimentComparison = {
    seed,
    runsPerCondition,
    baseline: summarise('baseline', baseline.runs),
    enforced: summarise('enforced', enforced.runs),
  };

  return {
    seed,
    runsPerCondition,
    comparison,
    runs: [...baseline.runs, ...enforced.runs],
    runEvents: { ...baseline.runEvents, ...enforced.runEvents },
  };
}
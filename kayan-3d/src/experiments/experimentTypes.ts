import type { KayanEvent } from '../types/events';

/** The two experimental conditions. */
export type ExperimentMode = 'baseline' | 'enforced';

/** Fixed reproducibility key for the scenario. */
export const EXPERIMENT_SEED = 'KAYAN-DEMO-1042';

/** Default repeated runs per condition. */
export const DEFAULT_RUNS = 10;

/** One measured interval between two real events. */
export interface TimingMetric {
  name: string;
  durationMs: number;
}

/** Metrics for a single run. Contains no copy of the event stream. */
export interface ExperimentRun {
  runId: string;
  seed: string;
  mode: ExperimentMode;
  startedAt: number;
  completedAt: number;
  durationMs: number;
  completed: boolean;
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
  finalState: string;
  timings: TimingMetric[];
}

/** Descriptive aggregate for one condition. */
export interface ExperimentSummary {
  mode: ExperimentMode;
  runs: number;
  completedRuns: number;
  averageDurationMs: number;
  minDurationMs: number;
  maxDurationMs: number;
  averageEventCount: number;
  averageMessageCount: number;
  averageHandoffCount: number;
  totalPolicyDecisions: number;
  totalDenials: number;
  totalViolations: number;
  totalBlocked: number;
  totalRecoveries: number;
  unauthorizedActionsAttempted: number;
  unauthorizedActionsAllowed: number;
}

/** The derived comparison. Descriptive only — no claims are generated. */
export interface ExperimentComparison {
  seed: string;
  runsPerCondition: number;
  baseline: ExperimentSummary;
  enforced: ExperimentSummary;
}

/** Everything a completed experiment produced, including retained run events. */
export interface ExperimentResult {
  seed: string;
  runsPerCondition: number;
  comparison: ExperimentComparison;
  runs: ExperimentRun[];
  /** Event history per run id, kept so any run stays inspectable. */
  runEvents: Record<string, KayanEvent[]>;
}
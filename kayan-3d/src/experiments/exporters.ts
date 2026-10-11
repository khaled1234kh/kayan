import { downloadText } from '../audit/exporters';
import type { ExperimentResult, ExperimentRun } from './experimentTypes';

/**
 * Experiment export.
 *
 * Metrics only. Event-level evidence is not duplicated here — the audit export
 * already covers that, and every run stays inspectable through the audit view.
 */

export function buildExperimentJson(result: ExperimentResult, generatedAt: string): string {
  const payload = {
    experiment: 'KAYAN-DEMO-1042',
    configuration: {
      seed: result.seed,
      runsPerCondition: result.runsPerCondition,
      conditions: ['baseline', 'enforced'],
      timing: 'logical — step delays from the shared workflow, no sleeping between steps',
    },
    generatedAt,
    summary: result.comparison,
    runs: result.runs,
  };
  return JSON.stringify(payload, null, 2);
}

const COLUMNS = [
  'run_id',
  'mode',
  'seed',
  'duration_ms',
  'completed',
  'event_count',
  'message_count',
  'handoff_count',
  'policy_decision_count',
  'denial_count',
  'violation_count',
  'blocked_count',
  'recovery_count',
  'unauthorized_action_attempted',
  'unauthorized_action_allowed',
  'final_state',
] as const;

function cell(value: unknown): string {
  if (value === null || value === undefined) return '';
  const s = String(value);
  return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
}

export function buildExperimentCsv(runs: ExperimentRun[]): string {
  const lines = [COLUMNS.join(',')];
  runs.forEach((r) => {
    lines.push(
      [
        r.runId,
        r.mode,
        r.seed,
        r.durationMs,
        r.completed,
        r.eventCount,
        r.messageCount,
        r.handoffCount,
        r.policyDecisionCount,
        r.denialCount,
        r.violationCount,
        r.blockedCount,
        r.recoveryCount,
        r.unauthorizedActionAttempted,
        r.unauthorizedActionAllowed,
        r.finalState,
      ]
        .map(cell)
        .join(','),
    );
  });
  return lines.join('\n');
}

export function downloadExperimentJson(result: ExperimentResult): void {
  downloadText(
    'kayan-experiment.json',
    buildExperimentJson(result, new Date().toISOString()),
    'application/json',
  );
}

export function downloadExperimentCsv(result: ExperimentResult): void {
  downloadText('kayan-experiment.csv', buildExperimentCsv(result.runs), 'text/csv');
}
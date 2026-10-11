import { useEffect, useRef, useState } from 'react';
import { runComparison } from '../../experiments/experimentRunner';
import {
  EXPERIMENT_SEED,
  type ExperimentResult,
  type ExperimentSummary,
} from '../../experiments/experimentTypes';
import { downloadExperimentCsv, downloadExperimentJson } from '../../experiments/exporters';
import {
  fetchExperiment,
  toExperimentResult,
  type BackendExperimentPayload,
} from '../../experiments/backendExperiment';
import { apiUrl } from '../../transport';
import { useStore } from '../../state/useStore';

/**
 * Experiment view.
 *
 * Inspection surface for the evaluation harness. It reports descriptive
 * measurements only — it does not evaluate them, and makes no claim about what
 * the numbers mean.
 *
 * Two execution paths, one layout:
 *
 *   mock    — the local harness runs the workflow in the browser (unchanged)
 *   backend — a 
un_comparison command is sent; the backend executes both
 *             conditions, persists every trial, and this view polls for results
 *
 * The view never executes a workflow in backend mode and never computes a
 * security outcome: every number it shows comes from backend-owned records.
 */

function cell(value: number): string {
  return value >= 1000 ? `${(value / 1000).toFixed(1)}s` : `${value}ms`;
}

function SummaryRow({
  label,
  baseline,
  enforced,
}: {
  label: string;
  baseline: string | number;
  enforced: string | number;
}) {
  return (
    <tr>
      <td className="exp-label">{label}</td>
      <td className="mono">{baseline}</td>
      <td className="mono">{enforced}</td>
    </tr>
  );
}

function SummaryTable({ summary }: { summary: ExperimentComparisonLike }) {
  const b = summary.baseline;
  const e = summary.enforced;
  return (
    <table className="exp-table" data-testid="exp-summary-table">
      <thead>
        <tr>
          <th />
          <th>Baseline</th>
          <th>Enforced</th>
        </tr>
      </thead>
      <tbody>
        <SummaryRow label="Runs" baseline={b.runs} enforced={e.runs} />
        <SummaryRow label="Completed" baseline={b.completedRuns} enforced={e.completedRuns} />
        <SummaryRow label="Avg duration" baseline={cell(b.averageDurationMs)} enforced={cell(e.averageDurationMs)} />
        <SummaryRow label="Min / max" baseline={`${cell(b.minDurationMs)} / ${cell(b.maxDurationMs)}`} enforced={`${cell(e.minDurationMs)} / ${cell(e.maxDurationMs)}`} />
        <SummaryRow label="Avg events" baseline={b.averageEventCount} enforced={e.averageEventCount} />
        <SummaryRow label="Avg messages" baseline={b.averageMessageCount} enforced={e.averageMessageCount} />
        <SummaryRow label="Avg handoffs" baseline={b.averageHandoffCount} enforced={e.averageHandoffCount} />
        <SummaryRow label="Policy decisions" baseline={b.totalPolicyDecisions} enforced={e.totalPolicyDecisions} />
        <SummaryRow label="Denials" baseline={b.totalDenials} enforced={e.totalDenials} />
        <SummaryRow label="Violations (not enforced)" baseline={b.totalViolations} enforced={e.totalViolations} />
        <SummaryRow label="Blocked" baseline={b.totalBlocked} enforced={e.totalBlocked} />
        <SummaryRow label="Recoveries" baseline={b.totalRecoveries} enforced={e.totalRecoveries} />
        <SummaryRow label="Unauthorized attempted" baseline={b.unauthorizedActionsAttempted} enforced={e.unauthorizedActionsAttempted} />
        <SummaryRow label="Unauthorized allowed" baseline={b.unauthorizedActionsAllowed} enforced={e.unauthorizedActionsAllowed} />
      </tbody>
    </table>
  );
}

type ExperimentComparisonLike = ExperimentResult['comparison'];

/** Backend experiment lifecycle, as the UI needs to distinguish them. */
type BackendStatus = 'idle' | 'submitted' | 'running' | 'completed' | 'partially failed' | 'failed';

export function ExperimentView({
  onInspectRun,
  onClose,
}: {
  onInspectRun: (runId: string) => void;
  onClose: () => void;
}) {
  const source = useStore((s) => s.source);
  const isBackend = source.kind === 'backend';
  const [runs, setRuns] = useState(10);
  const [result, setResult] = useState<ExperimentResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState<BackendStatus>('idle');
  const [experimentId, setExperimentId] = useState<string | null>(null);
  const pollHandle = useRef<number | null>(null);

  // Stop polling if the view closes mid-experiment.
  useEffect(
    () => () => {
      if (pollHandle.current !== null) window.clearTimeout(pollHandle.current);
    },
    [],
  );

  /** Poll the persisted experiment until it reaches a terminal state. */
  function poll(id: string): void {
    const tick = async (): Promise<void> => {
      try {
        const payload: BackendExperimentPayload = await fetchExperiment(apiUrl, id);
        setStatus(
          payload.experiment.status === 'completed'
            ? 'completed'
            : payload.experiment.status === 'partially_failed'
              ? 'partially failed'
              : payload.experiment.status === 'failed'
                ? 'failed'
                : 'running',
        );
        if (payload.experiment.status === 'running') {
          pollHandle.current = window.setTimeout(() => void tick(), 1000);
          return;
        }
        // Results come from the backend's own records.
        setResult(toExperimentResult(payload));
        setBusy(false);
      } catch {
        setStatus('failed');
        setBusy(false);
      }
    };
    void tick();
  }

  function run(): void {
    if (isBackend && source.runComparison) {
      setBusy(true);
      setResult(null);
      setStatus('submitted');
      const requestId = source.runComparison({
        seed: EXPERIMENT_SEED,
        runsPerCondition: runs,
      });
      // The acknowledgement identifies the experiment to poll.
      const unsubscribe = source.subscribeCommand?.((frame) => {
        if (frame.kind === 'command_ack' && frame.requestId === requestId) {
          unsubscribe?.();
          if (!frame.accepted) {
            setStatus('failed');
            setBusy(false);
            return;
          }
          if (frame.experimentId) {
            setExperimentId(frame.experimentId);
            setStatus('running');
            poll(frame.experimentId);
          }
        }
        if (frame.kind === 'command_error' && frame.requestId === requestId) {
          unsubscribe?.();
          setStatus('failed');
          setBusy(false);
        }
      });
      return;
    }

    setBusy(true);
    // Synchronous by design; the flag keeps the button honest.
    window.setTimeout(() => {
      const next = runComparison({ seed: EXPERIMENT_SEED, runs });
      setResult(next);
      setBusy(false);
    }, 0);
  }

  const statusLabel = isBackend && status !== 'idle' ? ` · ${status}` : '';

  return (
    <div className="audit-overlay" data-testid="experiment-view">
      <div className="audit-panel">
        <header className="audit-head">
          <div>
            <div className="panel-label">KAYAN experiment</div>
            <div className="audit-title">Demo Order #1042</div>
            <div className="audit-meta">
              Seed <span className="mono">{EXPERIMENT_SEED}</span> · same workflow, same agents, one
              variable: whether the policy layer blocks the unauthorized action.
              {isBackend && experimentId && (
                <>
                  {' '}
                  Experiment <span className="mono" data-testid="exp-id">{experimentId}</span>
                </>
              )}
            </div>
          </div>
          <div className="audit-actions">
            <button
              type="button"
              className="btn"
              onClick={() => result && downloadExperimentJson(result)}
              disabled={!result}
              data-testid="export-exp-json"
            >
              Export JSON
            </button>
            <button
              type="button"
              className="btn"
              onClick={() => result && downloadExperimentCsv(result)}
              disabled={!result}
              data-testid="export-exp-csv"
            >
              Export CSV
            </button>
            <button type="button" className="btn btn-primary" onClick={onClose} data-testid="experiment-close">
              Close
            </button>
          </div>
        </header>

        <div className="exp-controls">
          <label className="exp-field">
            <span className="k">Runs / condition</span>
            <input
              type="number"
              min={1}
              max={50}
              value={runs}
              onChange={(e) => setRuns(Math.max(1, Math.min(50, Number(e.target.value) || 1)))}
              data-testid="exp-runs"
            />
          </label>
          <button type="button" className="btn btn-primary" onClick={run} disabled={busy} data-testid="exp-run">
            Run Comparison
          </button>
          <span className="exp-note" data-testid="exp-status">
            {isBackend
              ? 'Sent to the backend as one run_comparison command; the backend executes baseline × N then enforced × N and persists every trial.'
              : 'Executes baseline × N then enforced × N. Durations are the workflow\'s own step delays — the harness does not sleep between steps.'}
            {statusLabel}
          </span>
        </div>

        {!result ? (
          <div className="exp-empty">
            <p className="muted">No experiment run yet.</p>
          </div>
        ) : (
          <div className="audit-body">
            <div className="exp-tables">
              <div className="panel-label">Comparison</div>
              <SummaryTable summary={result.comparison} />
            </div>
            <div className="exp-runs">
              <div className="panel-label">Run history</div>
              <table className="exp-table" data-testid="exp-runs-table">
                <thead>
                  <tr>
                    <th>Run</th>
                    <th>Mode</th>
                    <th>Duration</th>
                    <th>Events</th>
                    <th>Denials</th>
                    <th>Result</th>
                  </tr>
                </thead>
                <tbody>
                  {result.runs.map((r) => (
                    <tr
                      key={r.runId}
                      className="exp-run-row"
                      onClick={() => onInspectRun(r.runId)}
                      data-testid="exp-run-row"
                      data-run-mode={r.mode}
                    >
                      <td className="mono">{r.runId}</td>
                      <td>{r.mode}</td>
                      <td className="mono">{cell(r.durationMs)}</td>
                      <td className="mono">{r.eventCount}</td>
                      <td className="mono">{r.denialCount}</td>
                      <td className={r.completed ? 'exp-complete' : 'exp-incomplete'}>
                        {r.completed ? 'Complete' : 'Incomplete'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export { ExperimentSummary };
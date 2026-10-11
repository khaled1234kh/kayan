/**
 * End-to-end backend experiment check.
 *
 * Proves the frontend is the *controller and viewer*, not the engine: it sends
 * one run_comparison command, then reads backend-owned results, aggregates and
 * per-trial evidence. No workflow executes in this process.
 *
 *   button -> command -> FastAPI -> ExperimentRunner -> two conditions
 *         -> persist -> WebSocket (events) + REST (results)
 *         -> comparison table / exports / per-trial audit
 *
 * Run: npm run check:experiment
 */
import { FastApiEventSource } from '../src/transport/FastApiEventSource';
import {
  fetchExperiment,
  fetchRunEvents,
  toExperimentResult,
} from '../src/experiments/backendExperiment';
import { buildExperimentCsv, buildExperimentJson } from '../src/experiments/exporters';
import { reduce, initialDomainState } from '../src/state/eventReducer';
import type { KayanEvent } from '../src/types/events';

const API = process.env.KAYAN_API_URL ?? 'http://127.0.0.1:8000';
const RUNS = Number(process.env.KAYAN_EXP_RUNS ?? 2);

const results: string[] = [];
let failures = 0;

function check(label: string, condition: boolean, detail = ''): void {
  if (!condition) failures += 1;
  results.push(`${condition ? 'PASS' : 'FAIL'}  ${label}${detail ? ' :: ' + detail : ''}`);
}

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

async function waitFor(predicate: () => boolean, label: string, timeoutMs = 120_000) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    if (predicate()) return true;
    await sleep(200);
  }
  results.push(`FAIL  timed out waiting for ${label}`);
  failures += 1;
  return false;
}

async function main(): Promise<void> {
  const source = new FastApiEventSource({ apiUrl: API, stream: 'main', maxRetries: 2 });
  const liveEvents: KayanEvent[] = [];
  const acks: Array<Record<string, unknown>> = [];

  source.subscribe((e) => liveEvents.push(e));
  source.subscribeCommand((frame) => acks.push(frame as Record<string, unknown>));
  source.connect();
  await waitFor(() => source.getConnectionState() === 'connected', 'backend connection', 8000);

  const headBefore = (await source.getLastSequence()) || 0;
  await sleep(300);
  const eventsBeforeCommand = liveEvents.length;

  // The view submits one command; nothing runs locally.
  const requestId = source.runComparison({ runsPerCondition: RUNS, seed: 'KAYAN-DEMO-1042' });
  check('one command submitted', typeof requestId === 'string' && requestId.length > 0, requestId);

  await waitFor(() => acks.some((a) => a.kind === 'command_ack'), 'command acknowledgement', 10_000);
  const ack = acks.find((a) => a.kind === 'command_ack') as Record<string, unknown>;
  check('comparison accepted', ack.accepted === true, JSON.stringify(ack));
  check('acknowledgement carries the experiment id', typeof ack.experimentId === 'string', String(ack.experimentId));
  check('acknowledgement is not a completion', ack.kind === 'command_ack' && !('status' in ack));

  const experimentId = ack.experimentId as string;

  // The ack means accepted, not finished: poll persisted status.
  const early = await fetchExperiment(API, experimentId);
  check(
    'status is reported before completion',
    ['running', 'completed', 'partially_failed', 'failed'].includes(early.experiment.status),
    early.experiment.status,
  );

  await waitFor(async () => true, 'noop').catch(() => undefined);
  const deadline = Date.now() + 120_000;
  let payload = early;
  while (Date.now() < deadline && payload.experiment.status === 'running') {
    await sleep(500);
    payload = await fetchExperiment(API, experimentId);
  }

  check('experiment completed', payload.experiment.status === 'completed', payload.experiment.status);
  check('configuration came from the backend', payload.experiment.seed === 'KAYAN-DEMO-1042');
  check('runs per condition honoured', payload.experiment.runsPerCondition === RUNS);
  check('both conditions persisted', payload.runs.length === RUNS * 2, `${payload.runs.length} trials`);
  check(
    'condition labels recorded',
    payload.runs.filter((r) => r.condition === 'baseline').length === RUNS &&
      payload.runs.filter((r) => r.condition === 'enforced').length === RUNS,
  );
  check(
    'run indexes recorded per condition',
    payload.runs
      .filter((r) => r.condition === 'baseline')
      .map((r) => r.runIndex)
      .sort()
      .join(',') === payload.runs
      .filter((r) => r.condition === 'enforced')
      .map((r) => r.runIndex)
      .sort()
      .join(','),
  );
  check('unique run ids', new Set(payload.runs.map((r) => r.runId)).size === payload.runs.length);
  check('all trials completed', payload.progress.completedTrials === payload.runs.length);
  check('no failed trials', payload.progress.failedTrials === 0);

  // Metrics are backend-derived and internally consistent.
  const baseline = payload.comparison.baseline;
  const enforced = payload.comparison.enforced;
  check(
    'baseline recorded violations, not denials',
    baseline.totalViolations === RUNS && baseline.totalDenials === 0,
    `violations=${baseline.totalViolations} denials=${baseline.totalDenials}`,
  );
  check(
    'enforced recorded denials, not violations',
    enforced.totalDenials === RUNS && enforced.totalViolations === 0,
    `denials=${enforced.totalDenials} violations=${enforced.totalViolations}`,
  );
  check('enforced blocked and recovered every trial', enforced.totalBlocked === RUNS && enforced.totalRecoveries === RUNS);
  check('baseline never blocked', baseline.totalBlocked === 0);
  check(
    'aggregates match the individual records',
    baseline.totalDenials === payload.runs.filter((r) => r.condition === 'baseline').reduce((n, r) => n + r.denialCount, 0) &&
      enforced.totalPolicyDecisions ===
        payload.runs.filter((r) => r.condition === 'enforced').reduce((n, r) => n + r.policyDecisionCount, 0),
  );

  // Counts agree with the actual persisted events, not with expectations.
  for (const trial of payload.runs.slice(0, 2)) {
    const events = await fetchRunEvents(API, trial.runId);
    check(
      `trial ${trial.runId.slice(0, 12)} event count matches its record`,
      events.length === trial.eventCount,
      `${events.length} vs ${trial.eventCount}`,
    );
  }

  // Reproducibility: repeated trials of a condition agree logically.
  const enforcedTrials = payload.runs.filter((r) => r.condition === 'enforced');
  check(
    'repeated enforced trials are logically identical',
    new Set(enforcedTrials.map((r) => `${r.eventCount}/${r.durationMs}/${r.denialCount}`)).size === 1,
    enforcedTrials.map((r) => `${r.eventCount}/${r.durationMs}`).join(' '),
  );
  check(
    'logical duration is separate from machine time',
    enforcedTrials.every((r) => r.durationMs > 0 && r.wallClockMs >= 0 && r.durationMs !== r.wallClockMs),
    `logical=${enforcedTrials[0]?.durationMs} wall=${enforcedTrials[0]?.wallClockMs}`,
  );

  // Live events arrived over the socket while the experiment ran.
  const newLive = liveEvents.slice(eventsBeforeCommand);
  check('experiment events streamed over the socket', newLive.length > 0, `${newLive.length} events`);

  // Per-trial audit isolation.
  const a = await fetchRunEvents(API, enforcedTrials[0].runId);
  const b = await fetchRunEvents(API, enforcedTrials[1].runId);
  const idsA = new Set(a.map((e) => e.id));
  const tasksA = new Set(a.map((e) => e.taskId).filter(Boolean));
  check(
    'trial histories are disjoint',
    b.every((e) => !idsA.has(e.id)),
    `${a.length} vs ${b.length}`,
  );
  check(
    'trial histories do not share tasks',
    b.every((e) => !tasksA.has(e.taskId)),
  );
  const historiesCombined = idsA;
  check(
    'one trial history never contains another trial events',
    b.every((e) => !historiesCombined.has(e.id)),
  );

  // The trial's own events reconstruct the enforced scenario through the reducer.
  let state = initialDomainState();
  for (const event of a) state = reduce(state, event);
  check('trial audit resolves the TrustGate denial', state.security.lastDecision?.decision === 'deny');
  check('trial audit rebuilds collaboration', state.collaboration.messages.length > 0 && state.collaboration.handoffs.length === 1);
  check('trial audit reaches a completed order', state.tasks.some((t) => t.status === 'completed'));

  // Exports come from the persisted records.
  const mapped = toExperimentResult(payload);
  const json = JSON.parse(buildExperimentJson(mapped, new Date().toISOString()));
  check('JSON export parses and carries backend records', json.runs.length === payload.runs.length);
  check('JSON export names both conditions', JSON.stringify(json.configuration.conditions) === '["baseline","enforced"]');
  check('JSON export documents the timing method', typeof json.configuration.timing === 'string' && json.configuration.timing.length > 0);
  const csv = buildExperimentCsv(mapped.runs);
  const csvLines = csv.trim().split('\n');
  check('CSV export has one row per trial', csvLines.length === payload.runs.length + 1, `${csvLines.length - 1} rows`);
  check('CSV export includes the violation column', csvLines[0].includes('violation_count'));

  source.disconnect();
}

main()
  .then(() => {
    console.log(results.join('\n'));
    console.log(
      failures === 0
        ? '\nE2E BACKEND EXPERIMENT: PASS'
        : `\nE2E BACKEND EXPERIMENT: ${failures} FAILURE(S)`,
    );
    process.exit(failures === 0 ? 0 : 1);
  })
  .catch((err) => {
    console.log(results.join('\n'));
    console.error('\nE2E BACKEND EXPERIMENT ERRORED:', err);
    process.exit(1);
  });
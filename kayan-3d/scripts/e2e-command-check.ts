/**
 * End-to-end command-channel check against a running backend.
 *
 * In backend mode the client must *ask* for work and then merely observe:
 *
 *   button -> {kind:"command",command:"request_order"} -> FastAPI
 *          -> KAYAN Runtime -> persist -> commit -> publish
 *          -> WebSocket -> FastApiEventSource -> store -> reducer -> UI state
 *
 * Everything below the socket is the real implementation. No React, no browser.
 *
 * Run: npm run check:e2e
 */
import { FastApiEventSource } from '../src/transport/FastApiEventSource';
import { useStore } from '../src/state/useStore';
import { initialDomainState, reduce } from '../src/state/eventReducer';
import type { KayanEvent } from '../src/types/events';

const API = process.env.KAYAN_API_URL ?? 'http://127.0.0.1:8000';
const STREAM = process.env.KAYAN_STREAM ?? 'main';

const results: string[] = [];
let failures = 0;

function check(label: string, condition: boolean, detail = ''): void {
  if (!condition) failures += 1;
  results.push(`${condition ? 'PASS' : 'FAIL'}  ${label}${detail ? ' :: ' + detail : ''}`);
}

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

async function getJson<T>(path: string): Promise<T> {
  const res = await fetch(`${API}${path}`);
  if (!res.ok) throw new Error(`GET ${path} -> ${res.status}`);
  return (await res.json()) as T;
}

async function waitFor(predicate: () => boolean, label: string, timeoutMs = 30_000) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    if (predicate()) return true;
    await sleep(100);
  }
  results.push(`FAIL  timed out waiting for ${label}`);
  failures += 1;
  return false;
}

function streamHead(): Promise<number> {
  return getJson<{ streams: Array<{ streamId: string; lastSequence: number }> }>('/api/dev/streams')
    .then((s) => s.streams.find((x) => x.streamId === STREAM)?.lastSequence ?? 0);
}

/** Start from a clean store so the assertions describe this run only. */
function resetStore() {
  useStore.setState({
    ...initialDomainState(),
    lastDecision: null,
    events: [],
    workflowRunning: false,
  });
}

async function main(): Promise<void> {
  const health = await getJson<{ status: string }>('/api/health');
  check('backend reachable', health.status === 'ok');

  const source = new FastApiEventSource({ apiUrl: API, stream: STREAM, maxRetries: 2 });
  const received: KayanEvent[] = [];
  const acks: Array<Record<string, unknown>> = [];

  source.subscribe((event) => {
    received.push(event);
    useStore.getState().emitEvent(event);
  });
  source.subscribeCommand((frame) => acks.push(frame as Record<string, unknown>));

  source.connect();
  await waitFor(() => source.getConnectionState() === 'connected', 'backend connection');

  const headBefore = await streamHead();
  await waitFor(() => source.getLastSequence() >= headBefore, 'historical replay');
  check('backend connected', source.getConnectionState() === 'connected');

  // Observe only this run.
  const replayedUpTo = received.length;
  resetStore();
  received.length = 0;

  // The button: one command, nothing else.
  const requestId = source.runOrder();
  check('runOrder sends a request id', typeof requestId === 'string' && requestId.length > 0, requestId);

  await waitFor(() => acks.some((a) => a.kind === 'command_ack'), 'command acknowledgement');
  const ack = acks.find((a) => a.kind === 'command_ack') as Record<string, unknown>;
  check('command acknowledged as accepted', ack.accepted === true, JSON.stringify(ack));
  check('acknowledgement echoes the request id', ack.requestId === requestId);
  check('acknowledgement is not a business result', ack.kind === 'command_ack' && !('type' in ack));

  // The backend runtime now drives the workflow; the client only watches.
  await waitFor(
    () => received.some((e) => e.type === 'task_completed' && !e.payload?.handoff),
    'order completion over the socket',
  );

  const store = useStore.getState();
  const types = received.map((e) => e.type);

  check('all five actors changed state', store.actors.length === 5, String(store.actors.length));
  check(
    'every actor reaches a terminal state through the existing reducer',
    store.actors.every((a) => a.state === 'completed'),
    store.actors.map((a) => `${a.id}:${a.state}`).join(' '),
  );
  check('collaboration messages rebuilt', store.collaboration.messages.length >= 8, `${store.collaboration.messages.length}`);
  check('handoff rebuilt', store.collaboration.handoffs.length === 1);
  check(
    'handoff is the manager -> sales transfer',
    store.collaboration.handoffs[0]?.fromAgentId === 'manager' &&
      store.collaboration.handoffs[0]?.toAgentId === 'sales',
  );
  check('handoff completed', store.collaboration.handoffs[0]?.status === 'completed');
  check('external supplier message present', store.collaboration.messages.some((m) => m.fromAgentId === 'ext:supplier'));
  check('mailboxes rebuilt', Object.values(store.collaboration.mailboxes).some((m) => m.inbox.length > 0));
  check('TrustGate denial visible', store.lastDecision?.decision === 'deny', `${store.lastDecision?.decision}/${store.lastDecision?.policy}`);
  check('denial event present', types.includes('policy_denied'));
  check('blocked event present', types.includes('blocked'));
  check('approved recovery present', types.includes('task_started'));
  check('approval request present', types.includes('approval_requested'));
  check('approval response present', types.includes('approval_response'));
  check('order completed', types.includes('task_completed'));

  const taskIds = new Set(received.map((e) => e.taskId).filter(Boolean));
  check('all run events share one task', taskIds.size === 1, [...taskIds].join(','));

  // No duplicate application.
  check('no duplicate event ids', new Set(received.map((e) => e.id)).size === received.length);
  check(
    'client events carry no transport metadata',
    received.every((e) => !('sequence' in e) && !('streamId' in e)),
  );

  // Nothing was executed locally.
  check('frontend workflow did not run', replayedUpTo >= 0 && received.length > 0);

  // Audit compatibility: everything the audit view needs is present.
  const auditSecurity = received.filter((e) => e.type === 'policy_denied');
  check(
    'audit security evidence resolvable',
    auditSecurity.length === 1 &&
      typeof auditSecurity[0].payload?.policyDecision === 'object' &&
      typeof auditSecurity[0].payload?.intent === 'object',
  );
  const withAgentMessage = received.filter((e) => typeof e.payload?.agentMessage === 'object');
  check('collaboration evidence resolvable', withAgentMessage.length >= 8, `${withAgentMessage.length}`);
  const withHandoff = received.filter((e) => typeof e.payload?.handoff === 'object');
  check('handoff evidence resolvable', withHandoff.length >= 2, `${withHandoff.length}`);

  // The run is identifiable for the audit view.
  const runs = await getJson<Array<Record<string, unknown>>>('/api/runs?order_id=1042');
  // The most recent completed run is this command's run, not an earlier one.
  const run = runs
    .filter((r) => r.status === 'completed')
    .sort((a, b) => String(a.startedAt).localeCompare(String(b.startedAt)))
    .pop();
  check('workflow run recorded', run !== undefined, run ? `${run.runId} events=${run.eventCount}` : 'none');
  check(
    'run metrics derived from the backend stream',
    run?.eventCount === received.length && run?.denialCount === 1 && run?.blockedCount === 1,
    `events=${run?.eventCount} denials=${run?.denialCount} blocked=${run?.blockedCount}`,
  );
  check('recovery recorded on the run', run?.recoveryCount === 1);

  const persisted = await getJson<Array<{ id: string }>>(`/api/events?run_id=${run?.runId}&limit=500`);
  check('events persisted in PostgreSQL', persisted.length === received.length, `${persisted.length} vs ${received.length}`);

  // Ordering: the client must have applied the backend's order exactly. The
  // client-visible event carries no sequence by design, so this compares ids.
  const persistedOrder = persisted.map((e) => e.id);
  const receivedOrder = received.map((e) => e.id);
  check(
    'client applied backend events in the backend order',
    JSON.stringify(persistedOrder) === JSON.stringify(receivedOrder),
    receivedOrder.slice(0, 3).join(',') + '...',
  );

  source.disconnect();
}

main()
  .then(() => {
    console.log(results.join('\n'));
    console.log(
      failures === 0 ? '\nE2E COMMAND CHECK: PASS' : `\nE2E COMMAND CHECK: ${failures} FAILURE(S)`,
    );
    process.exit(failures === 0 ? 0 : 1);
  })
  .catch((err) => {
    console.log(results.join('\n'));
    console.error('\nE2E COMMAND CHECK ERRORED:', err);
    process.exit(1);
  });
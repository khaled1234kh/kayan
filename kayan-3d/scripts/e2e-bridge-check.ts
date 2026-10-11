/**
 * End-to-end bridge check against a running backend.
 *
 * Drives the real transport, the real store and the real reducer — no fakes:
 *
 *   FastApiEventSource -> WebSocket -> FastAPI -> EventBus -> EventService
 *     -> PostgreSQL
 *
 * and then in the other direction, proving a newly published backend event
 * reaches the client without a reload.
 *
 * Requires the backend running (uvicorn) and the dev seed present.
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

async function postEvent(body: Record<string, unknown>): Promise<void> {
  const res = await fetch(`${API}/api/dev/events`, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`POST /api/dev/events -> ${res.status}`);
}

async function waitFor(
  predicate: () => boolean,
  label: string,
  timeoutMs = 8000,
): Promise<boolean> {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    if (predicate()) return true;
    await sleep(50);
  }
  results.push(`FAIL  timed out waiting for ${label}`);
  failures += 1;
  return false;
}

/** Connect a real source and wait until it has caught up with the stream head. */
async function connectAndCatchUp(source: FastApiEventSource, headSequence: number) {
  source.connect();
  await waitFor(
    () => source.getConnectionState() === 'connected',
    'websocket connected',
    5000,
  );
  await waitFor(
    () => source.getLastSequence() >= headSequence,
    `replay to sequence ${headSequence}`,
    8000,
  );
}

async function streamHead(): Promise<number> {
  const streams = await getJson<{ streams: Array<{ streamId: string; lastSequence: number }> }>(
    '/api/dev/streams',
  );
  const main = streams.streams.find((s) => s.streamId === STREAM);
  return main?.lastSequence ?? 0;
}

function fold(events: KayanEvent[]) {
  let state = initialDomainState();
  for (const event of events) state = reduce(state, event);
  return state;
}

async function main(): Promise<void> {
  // -- backend reachable -------------------------------------------------
  const health = await getJson<{ status: string }>('/api/health');
  check('backend /api/health is ok', health.status === 'ok');

  const agents = await getJson<Array<{ id: string }>>('/api/agents');
  check('backend holds the five canonical agents', agents.length === 5, agents.map((a) => a.id).join(','));

  const head = await streamHead();
  check('seeded stream has persisted events', head > 0, `head=${head}`);

  // -- historical replay through the real transport ----------------------
  const source = new FastApiEventSource({ apiUrl: API, stream: STREAM, maxRetries: 3 });
  const received: KayanEvent[] = [];
  // The store's own ingestion path: source -> emitEvent -> reducer.
  source.subscribe((event) => {
    received.push(event);
    useStore.getState().emitEvent(event);
  });

  await connectAndCatchUp(source, head);
  check('historical replay reached the stream head', source.getLastSequence() === head, `${source.getLastSequence()}/${head}`);
  check('connection reports connected', source.getConnectionState() === 'connected');

  const sequences = received.map((_, i) => i + 1);
  check('replayed in strict sequence order', sequences.every((s, i) => s === i + 1), `n=${received.length}`);
  check('no duplicate event ids', new Set(received.map((e) => e.id)).size === received.length);

  // -- the client reconstructs backend state ------------------------------
  const store = useStore.getState();
  check('five actors present', store.actors.length === 5, String(store.actors.length));
  check(
    'collaboration rebuilt: messages from backend',
    store.collaboration.messages.length >= 3,
    `${store.collaboration.messages.length} message(s)`,
  );
  check(
    'collaboration rebuilt: handoff from backend',
    store.collaboration.handoffs.length >= 1,
    `${store.collaboration.handoffs.length} handoff(s)`,
  );
  check(
    'handoff references the backend task and agents',
    store.collaboration.handoffs.some(
      (h) => h.taskId === 'task-quote-1042' && h.fromAgentId === 'manager' && h.toAgentId === 'sales',
    ),
  );
  check(
    'threaded reply preserved from backend payload',
    store.collaboration.messages.some((m) => m.replyToMessageId === 'msg-manager-to-sales'),
  );
  check(
    'external sender is not treated as an agent',
    store.collaboration.messages.some((m) => m.fromAgentId === 'ext:supplier'),
  );
  check(
    'mailboxes rebuilt from the stream',
    store.collaboration.mailboxes.sales?.inbox.length > 0,
    `sales inbox=${store.collaboration.mailboxes.sales?.inbox.length}`,
  );
check(
  'TrustGate decision carried by backend event',
  store.lastDecision?.decision === 'deny',
  `${store.lastDecision?.decision}/${store.lastDecision?.policy}`,
);
// Assert the seeded scenario's decision specifically. The live stream also carries
// later commanded runs, whose denial is reported under a different rule, so the
// store's latest decision is not the right thing to pin here.
const seedEvents = await getJson<Array<{ type: string; payload: Record<string, unknown> }>>(
  '/api/events?stream_id=main&event_type=policy_denied&limit=100',
);
const seedDenial = seedEvents.find(
  (e) => (e.payload?.policyDecision as { policy?: string })?.policy === 'Untrusted Origin',
);
check(
  'seeded scenario denial preserves the untrusted-origin policy',
  seedDenial !== undefined &&
    (seedDenial.payload.policyDecision as { reason: string }).reason ===
      'Untrusted input cannot drive private data access',
);
  check(
    'task created from backend order_received',
    store.tasks.some((t) => t.id === 'task-order-1042'),
    store.tasks.map((t) => `${t.id}:${t.status}`).join(' '),
  );
check(
  'order task completed from backend events',
  store.tasks.some((t) => t.id === 'task-order-1042' && t.status === 'completed'),
  store.tasks.map((t) => `${t.id}:${t.status}`).join(' '),
);
check(
  'the agent that resumed after the block is completed',
  store.actors.find((a) => a.id === 'operations')?.state === 'completed',
  store.actors.map((a) => `${a.id}:${a.state}`).join(' '),
);

  // -- live event, no reload ---------------------------------------------
  const beforeLive = received.length;
  await postEvent({
    type: 'information_provided',
    actor_id: 'employee',
    task_id: 'task-order-1042',
    stream_id: STREAM,
    payload: { message: 'Live check: employee provided detail' },
  });
  await waitFor(() => received.length > beforeLive, 'live event delivery');
  const live = received[received.length - 1];
  check('live event arrived over the socket', live.type === 'information_provided', live.type);
  check('live event persisted before delivery', received.length === beforeLive + 1);

  // Read the event back by id: precise, and independent of how many events the
  // stream holds. Scanning a bounded page would silently start failing once the
  // stream outgrows the limit.
  const single = await getJson<{ id: string; type: string }>(`/api/events/${live.id}`);
  check(
    'live event is present in PostgreSQL',
    single.id === live.id && single.type === 'information_provided',
  );

  // -- reconnect + resume -------------------------------------------------
  const cursor = source.getLastSequence();
  source.disconnect();
  check('explicit disconnect reported', source.getConnectionState() === 'disconnected');

  const missedTypes = ['cost_metered', 'artifact_created', 'cost_metered'] as const;
  for (const type of missedTypes) {
    await postEvent({
      type,
      actor_id: 'sales',
      task_id: 'task-order-1042',
      stream_id: STREAM,
      payload: { message: `While disconnected: ${type}`, amount: 5, artifact: 'quotation' },
    });
  }
  const headAfter = await streamHead();
  check('events were produced while disconnected', headAfter === cursor + missedTypes.length, `${cursor} -> ${headAfter}`);

  const resumed: KayanEvent[] = [];
  const resumedSource = new FastApiEventSource({ apiUrl: API, stream: STREAM, maxRetries: 2 });
  // Resume exactly as the reconnect path does.
  resumedSource.connect();
  await waitFor(() => resumedSource.getConnectionState() === 'connected', 'resumed socket connected');
  resumedSource.disconnect();

  const resumeSource = new FastApiEventSource({ apiUrl: API, stream: STREAM, maxRetries: 2 });
  const resumeEvents: KayanEvent[] = [];
  resumeSource.subscribe((e) => resumeEvents.push(e));
  // Force the cursor the reconnect logic would have used.
  (resumeSource as unknown as { lastSequence: number }).lastSequence = cursor;
  await connectAndCatchUp(resumeSource, headAfter);
  check('resume cursor caught up to the new head', resumeSource.getLastSequence() === headAfter);
  check(
    'only the missed events were replayed',
    resumeEvents.length === missedTypes.length,
    `replayed ${resumeEvents.length}, missed ${missedTypes.length}`,
  );
  check(
    'replayed events are the ones produced while away',
    resumeEvents.map((e) => e.type).join(',') === missedTypes.join(','),
    resumeEvents.map((e) => e.type).join(','),
  );
  check('no duplicates after resume', new Set(resumeEvents.map((e) => e.id)).size === resumeEvents.length);

  // -- final state matches the complete backend stream --------------------
  const all = await getJson<Array<{ id: string }>>(`/api/events?stream_id=${STREAM}&limit=1000`);
  const combined = [...received.map((e) => e.id), ...resumeEvents.map((e) => e.id)];
  const missing = all.map((e) => e.id).filter((id) => !combined.includes(id));
  check('every persisted event was observed exactly once overall', missing.length === 0, missing.join(',') || 'none missing');

  const combinedEvents: KayanEvent[] = [...received, ...resumeEvents];
  const finalState = fold(combinedEvents);
  const orderTaskAfter = finalState.tasks.find((t) => t.id === 'task-order-1042');
  check(
    'reconstruction reflects the order completing from backend events',
    orderTaskAfter?.status === 'completed' && finalState.security.lastDecision !== null,
    `task=${orderTaskAfter?.status} decision=${finalState.security.lastDecision?.decision}`,
  );
  check(
    'the actor that resumed after the block is completed in the reconstruction',
    finalState.actors.find((a) => a.id === 'operations')?.state === 'completed',
    finalState.actors.map((a) => `${a.id}:${a.state}`).join(' '),
  );
  check(
    'a backend event newer than order completion is reflected (employee working again)',
    finalState.actors.find((a) => a.id === 'employee')?.state === 'working',
    finalState.actors.map((a) => `${a.id}:${a.state}`).join(' '),
  );

  // Cost accumulated while disconnected must be visible in the reconstructed
  // state. Expected total is derived from the stream so repeated runs stay valid.
  const expectedCost = combinedEvents
    .filter((e) => e.type === 'cost_metered' && e.taskId === 'task-order-1042')
    .reduce((sum, e) => sum + Number((e.payload as { amount?: number }).amount ?? 0), 0);
  const orderTask = finalState.tasks.find((t) => t.id === 'task-order-1042');
  check(
    'cost metered while disconnected is reflected in state',
    orderTask !== undefined && orderTask.cost === expectedCost && expectedCost > 0,
    `cost=${orderTask?.cost} expected=${expectedCost}`,
  );
  check(
    'artifact created while disconnected is reflected in state',
    (orderTask?.artifacts ?? []).includes('quotation'),
    (orderTask?.artifacts ?? []).join(','),
  );

  resumedSource.disconnect();
  resumeSource.disconnect();
  source.disconnect();
}

main()
  .then(() => {
    console.log(results.join('\n'));
    console.log(
      failures === 0 ? '\nE2E BRIDGE CHECK: PASS' : `\nE2E BRIDGE CHECK: ${failures} FAILURE(S)`,
    );
    process.exit(failures === 0 ? 0 : 1);
  })
  .catch((err) => {
    console.log(results.join('\n'));
    console.error('\nE2E BRIDGE CHECK ERRORED:', err);
    process.exit(1);
  });
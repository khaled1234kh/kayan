/**
 * Deterministic checks for the backend event transport.
 *
 * No browser needed: a fake socket stands in for WebSocket and the timers are
 * injected, so reconnect behaviour is exercised exactly rather than waited on.
 *
 * Run: npm run check:transport
 */
import { FastApiEventSource, parseEventFrame } from '../src/transport/FastApiEventSource';
import type { WebSocketLike } from '../src/transport/FastApiEventSource';
import type { KayanEvent } from '../src/types/events';

const results: string[] = [];
let failures = 0;

function check(label: string, condition: boolean, detail = ''): void {
  if (!condition) failures += 1;
  results.push(`${condition ? 'PASS' : 'FAIL'}  ${label}${detail ? ' :: ' + detail : ''}`);
}

/** Minimal in-memory socket. */
class FakeSocket implements WebSocketLike {
  onopen: ((event: unknown) => void) | null = null;
  onmessage: ((event: { data: unknown }) => void) | null = null;
  onerror: ((event: unknown) => void) | null = null;
  onclose: ((event: unknown) => void) | null = null;
  closed = false;
  sent: string[] = [];

  send(data: string): void {
    this.sent.push(data);
  }
  close(): void {
    this.closed = true;
  }
  // test drivers
  fireOpen(): void {
    this.onopen?.({});
  }
  deliver(obj: unknown): void {
    this.onmessage?.({ data: JSON.stringify(obj) });
  }
  fireClose(): void {
    this.onclose?.({});
  }
}

/** Frame factory. */
function frame(sequence: number, id = `evt-${sequence}`, extra: Record<string, unknown> = {}) {
  return {
    id,
    type: 'task_started',
    timestamp: 1_700_000_000_000 + sequence,
    sequence,
    streamId: 'main',
    actorId: 'sales',
    taskId: 'TASK-1',
    payload: { message: `Event ${sequence}` },
    ...extra,
  };
}

interface Harness {
  source: FastApiEventSource;
  sockets: FakeSocket[];
  urls: string[];
  timers: Array<{ fn: () => void; ms: number }>;
  runTimers(): void;
  events: KayanEvent[];
}

function harness(options: Record<string, unknown> = {}): Harness {
  const sockets: FakeSocket[] = [];
  const urls: string[] = [];
  const timers: Array<{ fn: () => void; ms: number }> = [];
  const events: KayanEvent[] = [];

  const source = new FastApiEventSource({
    apiUrl: 'http://127.0.0.1:8000',
    stream: 'main',
    webSocketFactory: (url: string) => {
      urls.push(url);
      const socket = new FakeSocket();
      sockets.push(socket);
      return socket;
    },
    setTimeoutFn: (fn: () => void, ms: number) => {
      timers.push({ fn, ms });
      return timers.length;
    },
    clearTimeoutFn: () => undefined,
    ...options,
  });
  source.subscribe((event) => events.push(event));

  return {
    source,
    sockets,
    urls,
    timers,
    events,
    runTimers() {
      const pending = timers.splice(0, timers.length);
      pending.forEach((t) => t.fn());
    },
  };
}

// -- interface -------------------------------------------------------------

{
  const { source } = harness();
  const required: Array<keyof typeof source> = [
    'subscribe',
    'subscribeStatus',
    'runOrder',
    'replay',
    'history',
  ];
  check(
    'implements KayanEventSource',
    required.every((m) => typeof source[m as unknown as 'subscribe'] === 'function'),
    required.join(','),
  );
}

// -- frame parsing ---------------------------------------------------------

{
  const parsed = parseEventFrame(frame(1));
  check('parses a valid frame', parsed !== null && parsed.sequence === 1);

  check('accepts a JSON string frame', parseEventFrame(JSON.stringify(frame(2))) !== null);
  check('rejects a frame with no id', parseEventFrame({ ...frame(3), id: undefined }) === null);
  check('rejects a frame with no type', parseEventFrame({ ...frame(4), type: '' }) === null);
  check('rejects a frame with no timestamp', parseEventFrame({ ...frame(5), timestamp: undefined }) === null);
  check('rejects a frame with no sequence', parseEventFrame({ ...frame(6), sequence: undefined }) === null);
  check('rejects malformed JSON', parseEventFrame('{not json') === null);
  check('rejects null', parseEventFrame(null) === null);

  // Payload convention: headline and structured object must both survive intact.
  const rich = parseEventFrame(
    frame(7, 'evt-7', {
      payload: {
        message: 'human headline',
        agentMessage: { id: 'msg-1', toAgentId: 'sales', subject: 'structured' },
      },
    }),
  );
  check(
    'preserves payload.message and payload.agentMessage without collision',
    rich?.payload.message === 'human headline' &&
      (rich?.payload.agentMessage as { id: string }).id === 'msg-1',
  );
}

// -- delivery, dedupe, sequence tracking -----------------------------------

{
  const h = harness();
  h.source.connect();
  h.sockets[0].fireOpen();

  h.sockets[0].deliver(frame(1));
  h.sockets[0].deliver(frame(2));
  h.sockets[0].deliver(frame(3));
  check('receives events and forwards them once', h.events.length === 3, `got ${h.events.length}`);
  check('tracks the highest sequence', h.source.getLastSequence() === 3);

  h.sockets[0].deliver(frame(2));
  h.sockets[0].deliver(frame(2, 'evt-2'));
  check('suppresses a duplicate id', h.events.length === 3, `got ${h.events.length}`);

  const fresh = h.events[0];
  check(
    'emits the existing client event contract',
    typeof fresh.id === 'string' &&
      typeof fresh.type === 'string' &&
      typeof fresh.timestamp === 'number' &&
      'payload' in fresh,
  );
  check('records history for replay/inspection', h.source.history().length === 3);
}

// -- connection state ------------------------------------------------------

{
  const h = harness();
  check('starts idle', h.source.getConnectionState() === 'idle');
  h.source.connect();
  check('connecting', h.source.getConnectionState() === 'connecting');
  h.sockets[0].fireOpen();
  check('connected', h.source.getConnectionState() === 'connected');
  h.sockets[0].fireClose();
  check('reconnecting after an unexpected close', h.source.getConnectionState() === 'reconnecting');
}

{
  const h = harness();
  const states: string[] = [];
  h.source.subscribeConnection((s) => states.push(s));
  h.source.connect();
  h.sockets[0].fireOpen();
  h.sockets[0].fireClose();
  check(
    'exposes connection transitions to the UI',
    states.includes('connecting') && states.includes('connected') && states.includes('reconnecting'),
    states.join('>'),
  );
}

// -- reconnect + resume cursor ---------------------------------------------

{
  const h = harness();
  h.source.connect();
  h.sockets[0].fireOpen();
  h.sockets[0].deliver(frame(1));
  h.sockets[0].deliver(frame(2));

  h.sockets[0].fireClose();
  check('schedules exactly one reconnect', h.timers.length === 1, `${h.timers.length}`);
  check('uses backoff', h.timers[0].ms > 0, `${h.timers[0].ms}ms`);

  h.runTimers();
  check('opens a new socket on retry', h.sockets.length === 2);
  check(
    'resumes with afterSequence from the last received sequence',
    h.urls[1].includes('afterSequence=2'),
    h.urls[1],
  );
  check('retry reports the reconnecting state', h.source.getConnectionState() === 'reconnecting');

  h.sockets[1].fireOpen();
  check('recovers to connected', h.source.getConnectionState() === 'connected');

  // Replayed events after the resume point are applied; nothing before it is.
  h.sockets[1].deliver(frame(3));
  check('applies the first event after the cursor', h.events.length === 3);
  h.sockets[1].deliver(frame(2));
  check('drops an event below the resume cursor', h.events.length === 3, `got ${h.events.length}`);
}

{
  const h = harness();
  h.source.connect();
  h.sockets[0].fireOpen();
  h.sockets[0].deliver(frame(1));

  h.sockets[0].fireClose();
  h.sockets[0].fireClose();
  check('collapses repeated close events into one retry', h.timers.length === 1, `${h.timers.length}`);
}

// -- bounded retries -------------------------------------------------------

{
  const h = harness({ maxRetries: 2, initialBackoffMs: 10 });
  h.source.connect();
  for (let i = 0; i < 6; i += 1) {
    const socket = h.sockets[h.sockets.length - 1];
    socket.fireClose();
    h.runTimers();
  }
  check(
    'stops retrying at the configured bound',
    h.sockets.length <= 3,
    `${h.sockets.length} socket(s) for maxRetries=2`,
  );
  check('gives up into a terminal state', h.source.getConnectionState() === 'disconnected');
}

// -- disconnect cleanup ----------------------------------------------------

{
  const h = harness();
  h.source.connect();
  h.sockets[0].fireOpen();
  h.sockets[0].deliver(frame(1));

  h.source.disconnect();
  check('closes the socket', h.sockets[0].closed);
  check('reports disconnected', h.source.getConnectionState() === 'disconnected');

  h.sockets[0].fireClose();
  check('does not reconnect after an explicit disconnect', h.timers.length === 0, `${h.timers.length}`);

  h.sockets[0].deliver(frame(9));
  check('ignores frames after disconnect', h.events.length === 1, `got ${h.events.length}`);
}

// -- resync (re-read the stream) -----------------------------------------

{
  const h = harness();
  h.source.connect();
  h.sockets[0].fireOpen();
  h.sockets[0].deliver(frame(1));
  check('cursor advances', h.source.getLastSequence() === 1);

  h.source.resync();
  check('resync opens a fresh connection', h.sockets.length === 2);
  check('resync requests the stream from the beginning', !h.urls[1].includes('afterSequence'), h.urls[1]);

  h.sockets[1].fireOpen();
  h.sockets[1].deliver(frame(1));
  check('re-applies the stream after a resync', h.events.length === 2, `got ${h.events.length}`);
}

// -- command channel ------------------------------------------------------

{
  const h = harness();
  h.source.connect();
  h.sockets[0].fireOpen();

  const requestId = h.source.runOrder();
  check('runOrder sends exactly one frame', h.sockets[0].sent.length === 1, `${h.sockets[0].sent.length}`);
  const sent = JSON.parse(h.sockets[0].sent[0]) as Record<string, string>;
  check(
    'sends the command envelope',
    sent.kind === 'command' && sent.command === 'request_order' && sent.orderId === '1042',
    JSON.stringify(sent),
  );
  check('requestId is echoed back in the frame', sent.requestId === requestId, `${sent.requestId} vs ${requestId}`);
  check('no workflow is executed locally', h.events.length === 0, `${h.events.length} events`);
  check('does not send any business event', h.sockets[0].sent.filter((s) => s.includes('"type"')).length === 0);
}

{
  const h = harness();
  h.source.connect();
  // Asked for while the socket is still connecting.
  const requestId = h.source.runOrder();
  check('command is queued while connecting', h.sockets[0].sent.length === 0);
  h.sockets[0].fireOpen();
  check('queued command is delivered on open', h.sockets[0].sent.length === 1);
  const sent = JSON.parse(h.sockets[0].sent[0]) as Record<string, string>;
  check('delivered command is the requested one', sent.requestId === requestId);
}

{
  const h = harness();
  const acks: unknown[] = [];
  h.source.subscribeCommand((frame) => acks.push(frame));
  h.source.connect();
  h.sockets[0].fireOpen();

  h.sockets[0].onmessage?.({
    data: JSON.stringify({ kind: 'command_ack', requestId: 'r1', accepted: true }),
  });
  check('command_ack is surfaced to protocol listeners', acks.length === 1, JSON.stringify(acks[0]));
  check('command_ack never reaches the event path', h.events.length === 0, `${h.events.length}`);

  h.sockets[0].deliver(frame(1));
  check('business events still flow normally', h.events.length === 1);
}

{
  const h = harness();
  const acks: Array<Record<string, unknown>> = [];
  h.source.subscribeCommand((frame) => acks.push(frame as Record<string, unknown>));
  h.source.connect();
  h.sockets[0].fireOpen();
  h.sockets[0].onmessage?.({
    data: JSON.stringify({
      kind: 'command_error',
      requestId: 'r2',
      code: 'unknown_command',
      message: 'Unknown command',
    }),
  });
  check('command_error is surfaced', acks.length === 1 && acks[0].kind === 'command_error');
  check('a rejected command produces no events', h.events.length === 0);
}

{
  const h = harness();
  h.source.connect();
  h.sockets[0].fireOpen();
  h.source.runOrder();
  h.source.runOrder();
  const ids = h.sockets[0].sent.map((s) => (JSON.parse(s) as Record<string, string>).requestId);
  check('each command gets a distinct requestId', new Set(ids).size === ids.length, ids.join(','));
}

console.log(results.join('\n'));
console.log(
  failures === 0
    ? '\nTRANSPORT CHECKS: PASS'
    : `\nTRANSPORT CHECKS: ${failures} FAILURE(S)`,
);
process.exit(failures === 0 ? 0 : 1);
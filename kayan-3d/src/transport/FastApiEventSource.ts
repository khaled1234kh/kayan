/**
 * Backend event source — a WebSocket transport for authoritative events.
 *
 * Implements the existing `KayanEventSource` interface, so the store, the
 * reducer, the 3D layer and every panel are unchanged. This class is a transport
 * and nothing else:
 *
 *   - it does not touch Zustand
 *   - it does not decide actor state
 *   - it does not run TrustGate
 *   - it does not create tasks or send business commands
 *
 * It connects, receives, deduplicates, tracks the resume cursor and reconnects.
 * Rehydration (turning events into state) is the existing reducer's job.
 *
 * The backend sends the event contract directly, so an incoming frame is already
 * a `KayanEvent` plus two additive ordering fields (`sequence`, `streamId`).
 */

import type { KayanEvent, KayanEventSource, KayanEventType } from '../types/events';

/**
 * Fields the backend adds on top of `KayanEvent`.
 *
 * `KayanEvent` itself is deliberately left untouched. `targetId` and `runId` are
 * transport metadata: they are read here and then dropped, so the client event
 * contract stays exactly what the reducer already expects.
 */
export interface BackendEventFrame extends KayanEvent {
  /** Monotonic, per stream. The authoritative ordering key. */
  sequence: number;
  /** Which stream this event belongs to. */
  streamId: string;
  targetId?: string;
  runId?: string;
}

/** Transport lifecycle, surfaced to the UI as a connection indicator. */
export type ConnectionState =
  | 'idle'
  | 'connecting'
  | 'connected'
  | 'reconnecting'
  | 'disconnected'
  | 'error';

export interface FastApiEventSourceOptions {
  /** Backend base URL, e.g. `http://127.0.0.1:8000`. */
  apiUrl: string;
  /** Stream to follow. The prototype uses a single explicit stream. */
  stream?: string;
  /** Bounded automatic reconnect with backoff. */
  maxRetries?: number;
  initialBackoffMs?: number;
  maxBackoffMs?: number;
  /** Injectable for tests. Defaults to the platform WebSocket. */
  webSocketFactory?: (url: string) => WebSocketLike;
  /** Injectable for tests. */
  setTimeoutFn?: (fn: () => void, ms: number) => number;
  clearTimeoutFn?: (handle: number) => void;
}

/** Minimal socket surface used, so the source is testable without a browser. */
export interface WebSocketLike {
  send(data: string): void;
  close(): void;
  onopen: ((event: unknown) => void) | null;
  onmessage: ((event: { data: unknown }) => void) | null;
  onerror: ((event: unknown) => void) | null;
  onclose: ((event: unknown) => void) | null;
}

/**
 * Protocol acknowledgement from the backend.
 *
 * `accepted` only says the command was understood. The business result is the
 * event stream, which arrives on this same socket.
 */
export interface CommandAck {
  kind: 'command_ack';
  requestId?: string;
  command?: string;
  accepted: boolean;
  reason?: string;
  runId?: string;
  /** Present when a comparison was accepted: the experiment to poll. */
  experimentId?: string;
}

export interface CommandError {
  kind: 'command_error';
  requestId?: string;
  code: string;
  message: string;
}

/** Builds a request id. Only uniqueness per client is required. */
function newRequestId(): string {
  const random = Math.random().toString(16).slice(2, 10);
  return `req-${Date.now().toString(16)}-${random}`;
}

const DEFAULT_STREAM = 'main';
/** The deterministic demonstration order. */
const DEFAULT_ORDER = '1042';
/** Reproducibility key for the experiment scenario. */
const DEFAULT_SEED = 'KAYAN-DEMO-1042';
const DEFAULT_RUNS_PER_CONDITION = 10;
const DEFAULT_MAX_RETRIES = 5;
const DEFAULT_INITIAL_BACKOFF = 500;
const DEFAULT_MAX_BACKOFF = 8000;

/**
 * True when a frame is a usable event.
 *
 * Validation is intentionally strict about identity and type: a malformed frame
 * is dropped rather than allowed to reach the reducer as half an event.
 */
export function parseEventFrame(raw: unknown): BackendEventFrame | null {
  if (typeof raw === 'string') {
    try {
      return parseEventFrame(JSON.parse(raw));
    } catch {
      return null;
    }
  }
  if (raw === null || typeof raw !== 'object') return null;
  const frame = raw as Partial<BackendEventFrame>;
  if (typeof frame.id !== 'string' || frame.id.length === 0) return null;
  if (typeof frame.type !== 'string' || frame.type.length === 0) return null;
  if (typeof frame.timestamp !== 'number') return null;
  if (typeof frame.sequence !== 'number') return null;
  return {
    id: frame.id,
    type: frame.type as KayanEventType,
    timestamp: frame.timestamp,
    sequence: frame.sequence,
    streamId: typeof frame.streamId === 'string' ? frame.streamId : DEFAULT_STREAM,
    actorId: typeof frame.actorId === 'string' ? frame.actorId : undefined,
    targetId: typeof frame.targetId === 'string' ? frame.targetId : undefined,
    taskId: typeof frame.taskId === 'string' ? frame.taskId : undefined,
    runId: typeof frame.runId === 'string' ? frame.runId : undefined,
    payload: (frame.payload ?? {}) as Record<string, unknown>,
  };
}

export class FastApiEventSource implements KayanEventSource {
  private listeners = new Set<(event: KayanEvent) => void>();
  private statusListeners = new Set<(running: boolean) => void>();
  private connectionListeners = new Set<(state: ConnectionState) => void>();

  private socket: WebSocketLike | null = null;
  private connectionState: ConnectionState = 'idle';
  private recorded: KayanEvent[] = [];
  private timers: number[] = [];

  /** Highest sequence accepted so far; the resume cursor. */
  private lastSequence = 0;
  /** Ids accepted, so a duplicated frame never reaches the reducer twice. */
  private seenIds = new Set<string>();
  private retries = 0;
  private closedByUser = false;
  private replayTimers: number[] = [];
  /** A command requested before the socket was ready. */
  private pendingCommand: string | null = null;
  private commandListeners = new Set<(frame: CommandAck | CommandError) => void>();

  private readonly stream: string;
  private readonly maxRetries: number;
  private readonly initialBackoff: number;
  private readonly maxBackoff: number;
  private readonly webSocketFactory: (url: string) => WebSocketLike;
  private readonly setTimeoutFn: (fn: () => void, ms: number) => number;
  private readonly clearTimeoutFn: (handle: number) => void;

  constructor(private readonly options: FastApiEventSourceOptions) {
    this.stream = options.stream ?? DEFAULT_STREAM;
    this.maxRetries = options.maxRetries ?? DEFAULT_MAX_RETRIES;
    this.initialBackoff = options.initialBackoffMs ?? DEFAULT_INITIAL_BACKOFF;
    this.maxBackoff = options.maxBackoffMs ?? DEFAULT_MAX_BACKOFF;
    this.webSocketFactory =
      options.webSocketFactory ?? ((url) => new WebSocket(url) as unknown as WebSocketLike);
    this.setTimeoutFn =
      options.setTimeoutFn ?? ((fn, ms) => globalThis.setTimeout(fn, ms) as unknown as number);
    this.clearTimeoutFn =
      options.clearTimeoutFn ?? ((handle) => globalThis.clearTimeout(handle));
  }

  // -- KayanEventSource ---------------------------------------------------

  subscribe(listener: (event: KayanEvent) => void): () => void {
    this.listeners.add(listener);
    return () => {
      this.listeners.delete(listener);
    };
  }

  /**
   * The backend never "runs" a workflow from the client's point of view: it is a
   * read-only view of what already happened, so nothing is ever reported as
   * running. Kept for interface parity.
   */
  subscribeStatus(listener: (running: boolean) => void): () => void {
    this.statusListeners.add(listener);
    return () => {
      this.statusListeners.delete(listener);
    };
  }

  history(): KayanEvent[] {
    return [...this.recorded];
  }

  /**
   * Asks the backend to run the order workflow.
   *
   * In backend mode this is the only way to start work: the browser sends a
   * command and the backend runtime decides everything. The frontend workflow is
   * not executed here.
   */
  runOrder(orderId = DEFAULT_ORDER): string {
    const requestId = newRequestId();
    const frame = JSON.stringify({
      kind: 'command',
      command: 'request_order',
      requestId,
      orderId,
    });

    if (this.socket && this.connectionState === 'connected') {
      this.sendCommand(frame);
    } else {
      // Asked for before the socket was ready: deliver it as soon as it is.
      this.pendingCommand = frame;
    }
    return requestId;
  }

  /** Re-read the whole stream from the beginning. */
  resync(): void {
    this.recorded = [];
    this.seenIds.clear();
    this.lastSequence = 0;
    this.disconnect();
    this.connect();
  }

  /**
   * Asks the backend to run one baseline-vs-enforced comparison.
   *
   * Returns the command requestId immediately; the acknowledgement carries the
   * experiment id to poll. Execution happens in the backend.
   */
  runComparison(
    options: { orderId?: string; seed?: string; runsPerCondition?: number } = {},
  ): string {
    const requestId = newRequestId();
    const frame = JSON.stringify({
      kind: 'command',
      command: 'run_comparison',
      requestId,
      orderId: options.orderId ?? DEFAULT_ORDER,
      seed: options.seed ?? DEFAULT_SEED,
      runsPerCondition: options.runsPerCondition ?? DEFAULT_RUNS_PER_CONDITION,
    });
    if (this.socket && this.connectionState === 'connected') {
      this.sendCommand(frame);
    } else {
      this.pendingCommand = frame;
    }
    return requestId;
  }

  private sendCommand(frame: string): void {
    try {
      this.socket?.send(frame);
    } catch {
      this.setConnectionState('error');
    }
  }

  /** Re-emit a recorded history at its original cadence (dev replay parity). */
  replay(history: KayanEvent[]): void {
    if (history.length === 0) return;
    this.cancelTimers();
    this.replayTimers.forEach((t) => this.clearTimeoutFn(t));
    const t0 = history[0].timestamp;
    history.forEach((event) => {
      const delay = Math.max(0, event.timestamp - t0);
      this.replayTimers.push(
        this.setTimeoutFn(() => {
          this.recorded.push(event);
          this.listeners.forEach((l) => l(event));
        }, delay),
      );
    });
  }

  // -- connection API (beyond the interface) ------------------------------

  /** Opens the stream. Idempotent while already connected or connecting. */
  connect(): void {
    if (this.socket) return;
    this.closedByUser = false;
    this.open();
  }

  /** Closes the stream and stops reconnecting. */
  disconnect(): void {
    this.closedByUser = true;
    this.cancelTimers();
    if (this.socket) {
      const socket = this.socket;
      this.socket = null;
      socket.onopen = null;
      socket.onmessage = null;
      socket.onerror = null;
      socket.onclose = null;
      try {
        socket.close();
      } catch {
        /* already closing */
      }
    }
    this.setConnectionState('disconnected');
  }

  getConnectionState(): ConnectionState {
    return this.connectionState;
  }

  /** Protocol acknowledgements (command_ack / command_error). */
  subscribeCommand(listener: (frame: CommandAck | CommandError) => void): () => void {
    this.commandListeners.add(listener);
    return () => {
      this.commandListeners.delete(listener);
    };
  }

  /** Resume cursor: the highest sequence this client has accepted. */
  getLastSequence(): number {
    return this.lastSequence;
  }

  subscribeConnection(listener: (state: ConnectionState) => void): () => void {
    this.connectionListeners.add(listener);
    listener(this.connectionState);
    return () => {
      this.connectionListeners.delete(listener);
    };
  }

  // -- internals ----------------------------------------------------------

  private get wsUrl(): string {
    const base = this.options.apiUrl.replace(/\/+$/, '');
    return `${base.replace(/^http/, 'ws')}/ws/events?stream=${encodeURIComponent(this.stream)}`;
  }

  private urlFor(afterSequence: number): string {
    const base = this.wsUrl;
    return afterSequence > 0 ? `${base}&afterSequence=${afterSequence}` : base;
  }

  private setConnectionState(state: ConnectionState): void {
    if (this.connectionState === state) return;
    this.connectionState = state;
    this.connectionListeners.forEach((l) => l(state));
  }

  private open(afterSequence = this.lastSequence): void {
    const isRetry = this.retries > 0;
    this.setConnectionState(isRetry ? 'reconnecting' : 'connecting');

    let socket: WebSocketLike;
    try {
      socket = this.webSocketFactory(this.urlFor(afterSequence));
    } catch {
      this.setConnectionState('error');
      this.scheduleReconnect();
      return;
    }
    this.socket = socket;

    socket.onopen = () => {
      if (this.socket !== socket) return;
      this.retries = 0;
      this.setConnectionState('connected');
      if (this.pendingCommand) {
        const frame = this.pendingCommand;
        this.pendingCommand = null;
        this.sendCommand(frame);
      }
    };

    socket.onmessage = (message) => {
      if (this.socket !== socket) return;
      const protocol = this.readProtocolFrame(message.data);
      if (protocol) {
        this.commandListeners.forEach((l) => l(protocol));
        return;
      }
      this.ingest(message.data);
    };

    socket.onerror = () => {
      if (this.socket !== socket) return;
      this.setConnectionState('error');
    };

    socket.onclose = () => {
      if (this.socket !== socket) return;
      this.socket = null;
      if (this.closedByUser) {
        this.setConnectionState('disconnected');
        return;
      }
      this.setConnectionState('reconnecting');
      this.scheduleReconnect();
    };
  }

  /** Reads a protocol frame; returns null for a business event. */
  private readProtocolFrame(raw: unknown): CommandAck | CommandError | null {
    try {
      const data = (typeof raw === 'string' ? JSON.parse(raw) : raw) as Record<string, unknown>;
      if (data && (data.kind === 'command_ack' || data.kind === 'command_error')) {
        return data as unknown as CommandAck | CommandError;
      }
    } catch {
      /* not a frame we understand; fall through to the event path */
    }
    return null;
  }

  /** Applies one frame, suppressing anything already applied. */
  private ingest(raw: unknown): boolean {
    const frame = parseEventFrame(raw);
    if (!frame) return false;
    if (this.seenIds.has(frame.id)) return false;
    // A replay can legitimately resend an older sequence (a resync); anything at
    // or below the cursor for this connection has already been applied.
    if (frame.sequence <= this.lastSequence) return false;

    this.seenIds.add(frame.id);
    this.lastSequence = frame.sequence;
    this.recorded.push(frame);

    // The reducer sees the event only after transport-level checks pass.
    const event: KayanEvent = {
      id: frame.id,
      type: frame.type,
      timestamp: frame.timestamp,
      actorId: frame.actorId,
      taskId: frame.taskId,
      payload: frame.payload,
    };
    this.listeners.forEach((l) => l(event));
    return true;
  }

  private scheduleReconnect(): void {
    if (this.closedByUser) return;
    if (this.retries >= this.maxRetries) {
      this.setConnectionState('disconnected');
      return;
    }
    this.retries += 1;
    // Exponential backoff, capped.
    const delay = Math.min(this.initialBackoff * 2 ** (this.retries - 1), this.maxBackoff);
    this.timers.push(
      this.setTimeoutFn(() => {
        this.timers = [];
        if (this.closedByUser) return;
        // Resume from the last accepted sequence so nothing is missed.
        this.open(this.lastSequence);
      }, delay),
    );
  }

  private cancelTimers(): void {
    this.timers.forEach((t) => this.clearTimeoutFn(t));
    this.timers = [];
  }
}
import type { KayanEvent, KayanEventSource } from '../types/events';
import type { TrustGateSnapshot } from '../types/trustgate';
import { TRUSTGATE_SEATS } from '../types/trustgate';
import type { ConnectionState, TrustGateEventSourceOptions, WebSocketLike } from './types';

const object = (x: unknown): x is Record<string, unknown> => x !== null && typeof x === 'object' && !Array.isArray(x);

/** Accept only the versioned console snapshot, never generic company/order frames. */
export function parseTrustGateSnapshot(raw: unknown): TrustGateSnapshot | null {
  try {
    const frame: unknown = typeof raw === 'string' ? JSON.parse(raw) : raw;
    if (!object(frame) || frame.type !== 'engagement_update' || !object(frame.data)) return null;
    const data = frame.data;
    if (data.protocol_version !== 1 || typeof data.session_id !== 'string' || !data.session_id ||
        !Number.isSafeInteger(data.revision) || (data.revision as number) < 0 || typeof data.status !== 'string') return null;
    if (data.engagement_id !== undefined && (typeof data.engagement_id !== 'string' || !data.engagement_id)) return null;
    if (data.engagement_id === undefined && data.status !== 'waiting') return null;
    if (data.agents !== undefined && (!Array.isArray(data.agents) || !data.agents.every((a) =>
      object(a) && typeof a.agent_id === 'string' && typeof a.role === 'string' &&
      ['idle', 'working', 'blocked', 'completed'].includes(a.status as string) &&
      (a.current_task === null || typeof a.current_task === 'string') &&
      (a.task_id === null || typeof a.task_id === 'string') && typeof a.activity === 'string'))) return null;
    if (data.transcript !== undefined && (!Array.isArray(data.transcript) || !data.transcript.every((t) =>
      object(t) && typeof t.id === 'string' && t.id.length > 0 && typeof t.timestamp === 'number' &&
      Number.isFinite(t.timestamp) && typeof t.agent_id === 'string' && typeof t.agent_role === 'string' &&
      typeof t.kind === 'string' && typeof t.content === 'string'))) return null;
    return data as unknown as TrustGateSnapshot;
  } catch { return null; }
}

/** Read-only live viewer. Reconnect receives a full snapshot, including missed activity. */
export class TrustGateEventSource implements KayanEventSource {
  private listeners = new Set<(event: KayanEvent) => void>();
  private statusListeners = new Set<(running: boolean) => void>();
  private connections = new Set<(state: ConnectionState) => void>();
  private socket: WebSocketLike | null = null;
  private state: ConnectionState = 'idle';
  private recorded: KayanEvent[] = [];
  private seen = new Set<string>();
  private session = '';
  private revision = -1;
  private retry = 0;
  private stopped = true;
  private timer: number | undefined;
  private readonly makeSocket: (url: string) => WebSocketLike;
  private readonly later: (fn: () => void, ms: number) => number;
  private readonly cancel: (handle: number) => void;

  constructor(private readonly options: TrustGateEventSourceOptions) {
    this.makeSocket = options.webSocketFactory ?? ((url) => new WebSocket(url) as unknown as WebSocketLike);
    this.later = options.setTimeoutFn ?? ((fn, ms) => globalThis.setTimeout(fn, ms) as unknown as number);
    this.cancel = options.clearTimeoutFn ?? ((id) => globalThis.clearTimeout(id));
  }

  subscribe(listener: (event: KayanEvent) => void): () => void {
    this.listeners.add(listener); return () => { this.listeners.delete(listener); };
  }
  subscribeStatus(listener: (running: boolean) => void): () => void {
    this.statusListeners.add(listener); return () => { this.statusListeners.delete(listener); };
  }
  subscribeConnection(listener: (state: ConnectionState) => void): () => void {
    this.connections.add(listener); listener(this.state);
    return () => { this.connections.delete(listener); };
  }
  getConnectionState(): ConnectionState { return this.state; }
  history(): KayanEvent[] { return [...this.recorded]; }
  runOrder(): void { throw new Error('Start a TrustGate engagement with the Python orchestrator.'); }
  replay(history: KayanEvent[]): void { history.forEach((event) => this.listeners.forEach((fn) => fn(event))); }

  connect(): void {
    if (this.socket || this.timer !== undefined) return;
    this.stopped = false; this.retry = 0; this.open();
  }
  disconnect(): void {
    this.stopped = true;
    if (this.timer !== undefined) this.cancel(this.timer);
    this.timer = undefined;
    const socket = this.socket; this.socket = null;
    if (socket) {
      socket.onopen = socket.onmessage = socket.onerror = socket.onclose = null;
      socket.close();
    }
    this.connection('disconnected');
    this.statusListeners.forEach((fn) => fn(false));
  }
  private connection(state: ConnectionState): void {
    this.state = state; this.connections.forEach((fn) => fn(state));
  }
  private open(): void {
    if (this.stopped) return;
    this.connection(this.retry ? 'reconnecting' : 'connecting');
    let socket: WebSocketLike;
    try { socket = this.makeSocket(`${this.options.apiUrl.replace(/\/+$/, '').replace(/^http/, 'ws')}/ws`); }
    catch { this.connection('error'); this.reconnect(); return; }
    this.socket = socket;
    socket.onopen = () => {
      if (this.socket !== socket) return;
      this.retry = 0; this.connection('connected');
    };
    socket.onmessage = (event) => {
      if (this.socket !== socket) return;
      const snapshot = parseTrustGateSnapshot(event.data);
      if (!snapshot) return;
      if (snapshot.session_id !== this.session) {
        this.session = snapshot.session_id; this.revision = -1;
        this.recorded = []; this.seen.clear();
      }
      if (snapshot.revision <= this.revision) {
        if (snapshot.revision === this.revision) this.statusListeners.forEach((fn) => fn(snapshot.status === 'active'));
        return;
      }
      this.revision = snapshot.revision;
      const entries = snapshot.transcript ?? [];
      const timestamp = entries[entries.length - 1]?.timestamp ?? Date.now();
      this.emit({ id: `tg:${this.session}:${snapshot.revision}`, type: 'trustgate_snapshot',
        timestamp, payload: { snapshot, message: `Engagement ${snapshot.status}` } });
      for (const entry of snapshot.transcript ?? []) {
        this.emit({ id: `tg:${snapshot.engagement_id}:${entry.id}`, type: 'trustgate_activity',
          actorId: TRUSTGATE_SEATS[entry.agent_role], taskId: entry.task_id ?? undefined,
          timestamp: entry.timestamp, payload: { entry, message: entry.content } });
      }
      this.statusListeners.forEach((fn) => fn(snapshot.status === 'active'));
    };
    socket.onerror = () => { if (this.socket === socket) this.connection('error'); };
    socket.onclose = () => {
      if (this.socket !== socket) return;
      this.socket = null; this.statusListeners.forEach((fn) => fn(false)); this.reconnect();
    };
  }
  private emit(event: KayanEvent): void {
    if (this.seen.has(event.id)) return;
    this.seen.add(event.id); this.recorded.push(event);
    this.recorded = this.recorded.slice(-2000);
    this.listeners.forEach((fn) => fn(event));
  }
  private reconnect(): void {
    if (this.stopped) return;
    if (this.retry >= (this.options.maxRetries ?? 5)) { this.connection('disconnected'); return; }
    const delay = Math.min((this.options.initialBackoffMs ?? 500) * 2 ** this.retry++, this.options.maxBackoffMs ?? 8000);
    this.connection('reconnecting');
    this.timer = this.later(() => { this.timer = undefined; this.open(); }, delay);
  }
}

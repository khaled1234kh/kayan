/**
 * Event source selection.
 *
 * One active source at a time. Mock mode is the default so a developer who has no
 * PostgreSQL or FastAPI running still gets a working prototype; backend mode is
 * opt-in and explicit, never a silent fallback either way.
 *
 * Vite only exposes environment variables prefixed with `VITE_`, so the switches
 * are:
 *
 *   VITE_KAYAN_EVENT_SOURCE=mock      (default)
 *   VITE_KAYAN_EVENT_SOURCE=backend
 *   VITE_KAYAN_API_URL=http://127.0.0.1:8000
 *
 * Example: `.env.local` in kayan-3d/
 *   VITE_KAYAN_EVENT_SOURCE=backend
 */

import { MockEventSource } from '../state/MockEventSource';
import type { KayanEventSource } from '../types/events';
import {
  FastApiEventSource,
  type CommandAck,
  type CommandError,
  type ConnectionState,
  type WebSocketLike,
} from './FastApiEventSource';

export type EventSourceKind = 'mock' | 'backend';

export const DEFAULT_API_URL = 'http://127.0.0.1:8000';
export const DEFAULT_STREAM = 'main';

function env(): Record<string, string | undefined> {
  try {
    return (import.meta.env ?? {}) as unknown as Record<string, string | undefined>;
  } catch {
    return {};
  }
}

/** Which source to use. Defaults to the local mock. */
export function resolveEventSourceKind(): EventSourceKind {
  const raw = (env().VITE_KAYAN_EVENT_SOURCE ?? 'mock').toString().trim().toLowerCase();
  return raw === 'backend' ? 'backend' : 'mock';
}

export function resolveApiUrl(): string {
  const raw = env().VITE_KAYAN_API_URL;
  return raw && raw.trim().length > 0 ? raw.trim() : DEFAULT_API_URL;
}

export function resolveStream(): string {
  const raw = env().VITE_KAYAN_STREAM;
  return raw && raw.trim().length > 0 ? raw.trim() : DEFAULT_STREAM;
}

export type KayanSource = KayanEventSource & {
  kind: EventSourceKind;
  /** Present on the backend source; used by the connection indicator. */
  subscribeConnection?: (listener: (state: ConnectionState) => void) => () => void;
  getConnectionState?: () => ConnectionState;
  connect?: () => void;
  disconnect?: () => void;
  getLastSequence?: () => number;
  subscribeCommand?: (listener: (frame: CommandAck | CommandError) => void) => () => void;
  /** Backend only: starts one baseline-vs-enforced comparison. */
  runComparison?: (options?: {
    orderId?: string;
    seed?: string;
    runsPerCondition?: number;
  }) => string;
};

/** The backend base URL, for result fetches that do not go over the socket. */
export { DEFAULT_API_URL as apiUrl };

/** Builds the single active source for this session. */
export function createEventSource(
  overrides: {
    webSocketFactory?: (url: string) => WebSocketLike;
    setTimeoutFn?: (fn: () => void, ms: number) => number;
    clearTimeoutFn?: (handle: number) => void;
  } = {},
): KayanSource {
  const kind = resolveEventSourceKind();

  if (kind === 'backend') {
    const source = new FastApiEventSource({
      apiUrl: resolveApiUrl(),
      stream: resolveStream(),
      ...overrides,
    });
    return Object.assign(source, { kind }) as KayanSource;
  }

  return Object.assign(new MockEventSource(), { kind }) as KayanSource;
}

export { FastApiEventSource };
export type { CommandAck, CommandError, ConnectionState, WebSocketLike };
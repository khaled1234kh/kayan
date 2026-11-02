export type ConnectionState = 'idle' | 'connecting' | 'connected' | 'reconnecting' | 'disconnected' | 'error';
export interface WebSocketLike {
  send(data: string): void;
  close(): void;
  onopen: ((event: unknown) => void) | null;
  onmessage: ((event: { data: unknown }) => void) | null;
  onerror: ((event: unknown) => void) | null;
  onclose: ((event: unknown) => void) | null;
}
export interface TrustGateEventSourceOptions {
  apiUrl: string;
  maxRetries?: number;
  initialBackoffMs?: number;
  maxBackoffMs?: number;
  webSocketFactory?: (url: string) => WebSocketLike;
  setTimeoutFn?: (fn: () => void, ms: number) => number;
  clearTimeoutFn?: (handle: number) => void;
}

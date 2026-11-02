import { TrustGateEventSource } from './TrustGateEventSource';
export type { ConnectionState, WebSocketLike } from './types';
export type EventSourceKind = 'trustgate';
export function resolveApiUrl(): string {
  const value = import.meta.env?.VITE_KAYAN_API_URL;
  return value?.trim() || 'http://127.0.0.1:8001';
}
export const apiUrl = resolveApiUrl();
export function createEventSource() { return new TrustGateEventSource({ apiUrl }); }

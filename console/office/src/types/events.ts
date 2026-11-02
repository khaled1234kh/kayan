/** Authoritative TrustGate console events; snapshots never grant browser execution authority. */
export type KayanEventType = 'trustgate_snapshot' | 'trustgate_activity';
export interface KayanEvent {
  id: string; type: KayanEventType; timestamp: number; actorId?: string; taskId?: string;
  payload?: Record<string, unknown>;
}
export function eventMessage(event: KayanEvent): string { return String(event.payload?.message ?? event.type); }
export function eventLevel(event: KayanEvent): 'info' | 'warn' | 'error' {
  const message = eventMessage(event);
  return message.startsWith('DENY:') ? 'error' : 'info';
}
export interface KayanEventSource {
  subscribe(listener: (event: KayanEvent) => void): () => void;
  subscribeStatus(listener: (running: boolean) => void): () => void;
  runOrder(): void;
  replay(history: KayanEvent[]): void;
  history(): KayanEvent[];
}

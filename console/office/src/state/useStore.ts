import { create } from 'zustand';
import type { KayanEvent } from '../types/events';
import type { TrustGateSnapshot } from '../types/trustgate';
import { createEventSource, type ConnectionState } from '../transport';
import { initialDomainState, reduce, type DomainState } from './eventReducer';
const source = createEventSource();
interface Store extends DomainState {
  lastDecision: DomainState['security']['lastDecision'];
  events: KayanEvent[];
  workflowRunning: boolean;
  selectedActorId: string | null;
  eventSourceKind: 'trustgate';
  connection: ConnectionState;
  reconnect: () => void;
  selectActor: (id: string | null) => void;
  emitEvent: (event: KayanEvent) => void;
}
export const useStore = create<Store>((set) => ({
  ...initialDomainState(), lastDecision: null, events: [], workflowRunning: false,
  selectedActorId: null, eventSourceKind: 'trustgate', connection: source.getConnectionState(),
  reconnect: () => source.connect(),
  selectActor: id => set({ selectedActorId: id }),
  emitEvent: event => set(state => {
    const snapshot = event.type === 'trustgate_snapshot' ? event.payload?.snapshot as TrustGateSnapshot : null;
    const newEngagement = snapshot && snapshot.engagement_id !== state.collaboration.liveEngagementId;
    const next = reduce(state, event);
    return { ...next, lastDecision: next.security.lastDecision,
      events: [event, ...(newEngagement ? [] : state.events)].slice(0, 80) };
  }),
}));
source.subscribe(event => useStore.getState().emitEvent(event));
source.subscribeStatus(running => useStore.setState({ workflowRunning: running }));
source.subscribeConnection(connection => useStore.setState({ connection }));
source.connect();

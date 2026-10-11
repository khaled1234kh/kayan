import { create } from 'zustand';
import type { Actor, Task } from '../types';
import type { KayanEvent } from '../types/events';
import type { SecurityDecisionView } from '../security/policyTypes';
import type { CollaborationState, CompanyBoardTask } from './eventReducer';
import { createEventSource, type ConnectionState, type EventSourceKind } from '../transport';
import { initialDomainState, reduce } from './eventReducer';
import { apiUrl } from '../transport';
import { onboardingApi } from '../api/onboarding';

/**
 * Single Zustand store — extended from Task 01 rather than duplicated.
 *
 * It holds the derived domain state (actors/tasks) plus the raw event log, and it
 * owns no business rules: `emitEvent` is the ingest point, and every transition
 * is computed by the pure reducer. Today the source is selected once by
 * `createEventSource()`: `MockEventSource` locally, `FastApiEventSource` when
 * `VITE_KAYAN_EVENT_SOURCE=backend`. Either way a WebSocket client calls the same
 * `emitEvent`, so nothing downstream knows the difference.
 */

const MAX_EVENTS = 80;

const source = createEventSource();

interface ActiveCompany {
  id: string;
  name: string;
  status: 'draft' | 'active' | 'paused';
  employees: Array<{
    id: string;
    displayName: string;
    kind: 'human' | 'ai';
    roleKey: string;
    gridPosition: { x: number; z: number };
    zoneId: string;
  }>;
}

interface KayanStore {
  actors: Actor[];
  tasks: Task[];
  /** Company task board mirror, folded from task lifecycle events. */
  companyTasks: CompanyBoardTask[];
  /** Latest TrustGate decision, lifted from the event stream. */
  lastDecision: SecurityDecisionView | null;
  /** Messages, handoffs and mailboxes, rebuilt from the event stream. */
  collaboration: CollaborationState;
  /** Newest first, for direct rendering by the activity panel. */
  events: KayanEvent[];
  workflowRunning: boolean;
  selectedActorId: string | null;
  /** Which transport is active: local mock or backend WebSocket. */
  eventSourceKind: EventSourceKind;
  /** Transport lifecycle, for the connection indicator. */
  connection: ConnectionState;
  /** Active company configuration (from onboarding). */
  activeCompany: ActiveCompany | null;
  /** Whether we're currently checking for an active company. */
  isCheckingActiveCompany: boolean;

  /** Ingest one event: append to the log and fold it through the reducer. */
  emitEvent: (event: KayanEvent) => void;
  /** Replace the board mirror with authoritative REST rows (values events omit). */
  setCompanyTasks: (tasks: CompanyBoardTask[]) => void;
  /** Reset domain state and drop the event log. */
  clearEvents: () => void;
  /** Start a fresh scripted order run (mock) or re-read the stream (backend). */
  runDemoOrder: () => void;
  /** Dev-only: replay the last recorded run at its original cadence. */
  replayDemo: () => void;

  selectActor: (id: string | null) => void;
  /** The active source; a WebSocket source replaces the mock later. */
  source: ReturnType<typeof createEventSource>;
  /** Check for and load active company. */
  checkActiveCompany: () => Promise<void>;
  /** Set active company and replace actors. */
  setActiveCompany: (company: ActiveCompany | null) => void;
}

export const useStore = create<KayanStore>((set, get) => ({
  ...initialDomainState(),
  lastDecision: null,
  events: [],
  workflowRunning: false,
  selectedActorId: null,
  eventSourceKind: source.kind,
  connection: source.getConnectionState?.() ?? 'idle',
  source,
  activeCompany: null,
  isCheckingActiveCompany: false,

  emitEvent: (event) =>
    set((state) => {
      const next = reduce(
        {
          actors: state.actors,
          tasks: state.tasks,
          companyTasks: state.companyTasks,
          security: { lastDecision: state.lastDecision },
          collaboration: state.collaboration,
        },
        event,
      );
      return {
        actors: next.actors,
        tasks: next.tasks,
        companyTasks: next.companyTasks,
        lastDecision: next.security.lastDecision,
        collaboration: next.collaboration,
        events: [event, ...state.events].slice(0, MAX_EVENTS),
      };
    }),

  setCompanyTasks: (tasks) => set({ companyTasks: tasks }),

  clearEvents: () =>
    set(() => ({ ...initialDomainState(), events: [], workflowRunning: false })),

  runDemoOrder: () => get().source.runOrder(),

  replayDemo: () => {
    const { source: src } = get();
    const recorded = src.history();
    if (recorded.length === 0) return;
    get().clearEvents();
    src.replay(recorded);
  },

  selectActor: (id) => set({ selectedActorId: id }),

  checkActiveCompany: async () => {
    if (source.kind !== 'backend') return;
    set({ isCheckingActiveCompany: true });
    try {
      // Try to find an active company
      const response = await fetch(`${apiUrl}/api/companies`, {
        headers: { 'Content-Type': 'application/json' },
      });
      if (response.ok) {
        const companies = await response.json();
        const active = companies.find((c: { status: string }) => c.status === 'active');
        if (active) {
          // Fetch full company details with workforce
          const [companyDetail, workforce] = await Promise.all([
            onboardingApi.getCompany(active.id),
            onboardingApi.getWorkforce(active.id),
          ]);
          const employees = workforce.employees.map((emp, index) => ({
            id: emp.id,
            displayName: emp.displayName,
            kind: emp.kind as 'human' | 'ai',
            roleKey: emp.roleKey,
            gridPosition: { x: (index % 4) + 1, z: Math.floor(index / 4) + 1 },
            zoneId: ['sales', 'operations', 'ceo', 'meeting'][index % 4],
          }));
          get().setActiveCompany({
            id: companyDetail.id,
            name: companyDetail.name,
            status: companyDetail.status as 'draft' | 'active' | 'paused',
            employees,
          });
        }
      }
    } catch (error) {
      console.warn('Failed to check active company:', error);
    } finally {
      set({ isCheckingActiveCompany: false });
    }
  },

  setActiveCompany: (company) => set({ activeCompany: company }),
}));

/**
 * Module-scope subscriptions (not inside a component) so React StrictMode's
 * double-invocation cannot register the source twice and duplicate events.
 */
source.subscribe((event) => {
  useStore.getState().emitEvent(event);
});

source.subscribeStatus((running) => {
  useStore.setState({ workflowRunning: running });
});

// Backend mode: open the stream, and reflect transport state for the indicator.
if (source.kind === 'backend') {
  source.subscribeConnection?.((connection) => {
    useStore.setState({ connection });
  });
  source.connect?.();
}

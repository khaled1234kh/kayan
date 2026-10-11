/**
 * Domain model for the KAYAN visualization layer.
 *
 * These shapes describe what the UI renders. They are produced by folding
 * `KayanEvent`s (see `./events`) through the event reducer — never authored by a
 * component. A future FastAPI/WebSocket backend emits the same events and the
 * derived state is identical.
 */

/** Lifecycle of a single worker seat. Drives all scene + UI state styling. */
export type ActorState =
  | 'idle'
  | 'working'
  | 'waiting'
  | 'awaiting_approval'
  | 'blocked'
  | 'completed';

/** Human seats are accountable; AI seats are bounded by a capability contract. */
export type ActorKind = 'human' | 'ai';

/** A worker on the floor. */
export interface Actor {
  id: string;
  name: string;
  role: string;
  kind: ActorKind;
  /** Short authority line shown in the inspector (never enforced client-side). */
  authority: string;
  /** Footprint on the 12x12 floor grid, in tile units. */
  gridPosition: { x: number; z: number };
  /** Zone the actor works in. */
  zoneId: string;
  state: ActorState;
  /** Current task id, or null when unassigned. */
  taskId: string | null;
  /** One-line description of what the actor is doing right now. */
  activity: string;
}

/** Work item an actor can be assigned to. */
export interface Task {
  id: string;
  title: string;
  /** Short human description of the unit of work (e.g. "50 shirts"). */
  subject: string;
  status: 'open' | 'awaiting_approval' | 'blocked' | 'completed';
  /** Ordered actor ids participating in this task. */
  participants: string[];
  /** Artifact identifiers attached via `artifact_created` events. */
  artifacts: string[];
  /** Accumulated metered cost, summed by `cost_metered` events. */
  cost: number;
}

export type { KayanEvent, KayanEventType, KayanEventSource } from './events';
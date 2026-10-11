/**
 * Central event contract.
 *
 * This is the single source of truth for the KAYAN event vocabulary. Event name
 * strings live here and nowhere else â€” the UI, the reducer and the workflow
 * engine all reference the catalogue, so renaming an event is a one-line change.
 *
 * A `KayanEvent` is the only thing the visualization layer ever receives. Today
 * it comes from `MockEventSource`; later it will arrive over a WebSocket with
 * the identical shape, and nothing downstream needs to know the difference.
 */

/** The full event vocabulary. */
export type KayanEventType =
  | 'order_received'
  | 'plan_proposed'
  | 'plan_validated'
  | 'task_assigned'
  | 'task_started'
  | 'awaiting_info'
  | 'information_provided'
  | 'policy_denied'
  | 'policy_violation'
  | 'blocked'
  | 'artifact_created'
  | 'approval_requested'
  | 'approved'
  | 'rejected'
  | 'task_completed'
  | 'cost_metered'
  /* agent collaboration */
  | 'agent_message_sent'
  | 'agent_message_received'
  | 'task_delegated'
  | 'task_accepted'
  | 'task_handoff'
  | 'information_requested'
  | 'agent_question'
| 'agent_response'
  | 'approval_response'
  /* company, workforce and contract configuration (P0) */
  | 'company_created'
  | 'company_updated'
  | 'workforce_configured'
  | 'recommendation_generated'
  | 'recommendation_accepted'
  | 'contract_generated'
  | 'contract_updated'
  | 'contract_version_created'
  | 'contract_activated'
  | 'contract_superseded'
  /* budget (P0) */
  | 'budget_adjusted'
  | 'budget_reserved'
  | 'budget_released'
  | 'budget_charged'
  | 'budget_reservation_denied'
  | 'budget_limit_reached'
  /* company lifecycle (P0) */
  | 'company_activated'
  | 'company_paused'
  | 'company_resumed'
  /* company tasks (P0) */
  | 'company_task_created'
  | 'company_task_updated';

/** A single immutable fact that already happened. */
export interface KayanEvent {
  id: string;
  type: KayanEventType;
  /** Epoch milliseconds. */
  timestamp: number;
  /** Actor the event concerns, when applicable. */
  actorId?: string;
  /** Task the event belongs to, when applicable. */
  taskId?: string;
  /**
   * Event-specific data. `message` is the human-readable line rendered by the
   * activity panel, so copy is authored once, next to the event it belongs to.
   */
  payload?: Record<string, unknown>;
}

/** Filter buckets. Derived from the catalogue, never from separate arrays. */
export type EventCategory =
  | 'task'
  | 'collaboration'
  | 'security'
  | 'approval'
  | 'governance';

/** Presentation metadata for an event type. */
export interface EventDefinition {
  /** Fallback label when a payload carries no `message`. */
  label: string;
  /** Drives the activity panel colour. */
  level: 'info' | 'success' | 'warn' | 'error';
  /** Bucket used by the audit filters. */
  category: EventCategory;
  /** True when the event requires an `actorId`. */
  actorScoped: boolean;
}

/** The catalogue. Add an event here and every consumer picks it up. */
export const EVENT_DEFS: Record<KayanEventType, EventDefinition> = {
  order_received: { label: 'Order received', level: 'info', category: 'task', actorScoped: false },
  plan_proposed: { label: 'Plan proposed', level: 'info', category: 'task', actorScoped: true },
  plan_validated: { label: 'Plan validated', level: 'success', category: 'task', actorScoped: true },
  task_assigned: { label: 'Task assigned', level: 'info', category: 'task', actorScoped: true },
  task_started: { label: 'Task started', level: 'info', category: 'task', actorScoped: true },
  awaiting_info: { label: 'Awaiting information', level: 'warn', category: 'task', actorScoped: true },
  information_provided: { label: 'Information provided', level: 'success', category: 'collaboration', actorScoped: true },
  policy_denied: { label: 'Policy denied', level: 'error', category: 'security', actorScoped: true },
  policy_violation: { label: 'Policy violation (not enforced)', level: 'error', category: 'security', actorScoped: true },
  blocked: { label: 'Blocked', level: 'error', category: 'security', actorScoped: true },
  artifact_created: { label: 'Artifact created', level: 'info', category: 'task', actorScoped: true },
  approval_requested: { label: 'Approval requested', level: 'warn', category: 'approval', actorScoped: true },
  approved: { label: 'Approved', level: 'success', category: 'approval', actorScoped: true },
  rejected: { label: 'Rejected', level: 'error', category: 'approval', actorScoped: true },
  task_completed: { label: 'Order completed', level: 'success', category: 'task', actorScoped: false },
  cost_metered: { label: 'Cost metered', level: 'info', category: 'task', actorScoped: true },

  /* ---- agent collaboration ------------------------------------------- */

  agent_message_sent: { label: 'Message sent', level: 'info', category: 'collaboration', actorScoped: true },
  agent_message_received: { label: 'Message received', level: 'info', category: 'collaboration', actorScoped: true },
  task_delegated: { label: 'Task delegated', level: 'info', category: 'collaboration', actorScoped: true },
  task_accepted: { label: 'Task accepted', level: 'success', category: 'collaboration', actorScoped: true },
  task_handoff: { label: 'Task handed over', level: 'info', category: 'collaboration', actorScoped: true },
  information_requested: { label: 'Information requested', level: 'warn', category: 'collaboration', actorScoped: true },
  agent_question: { label: 'Instruction received', level: 'warn', category: 'security', actorScoped: true },
  agent_response: { label: 'Response given', level: 'success', category: 'collaboration', actorScoped: true },
  approval_response: { label: 'Approval responded', level: 'success', category: 'approval', actorScoped: true },

  /* ---- company, workforce and contract configuration (P0) ------------- */

  company_created: { label: 'Company created', level: 'info', category: 'governance', actorScoped: false },
  company_updated: { label: 'Company updated', level: 'info', category: 'governance', actorScoped: false },
  workforce_configured: { label: 'Workforce configured', level: 'info', category: 'governance', actorScoped: false },
  recommendation_generated: { label: 'Recommendation generated', level: 'info', category: 'governance', actorScoped: false },
  recommendation_accepted: { label: 'Recommendation accepted', level: 'success', category: 'governance', actorScoped: false },
  contract_generated: { label: 'Contract generated', level: 'info', category: 'governance', actorScoped: false },
  contract_updated: { label: 'Contract updated', level: 'info', category: 'governance', actorScoped: false },
  contract_version_created: { label: 'Contract version created', level: 'info', category: 'governance', actorScoped: false },
  contract_activated: { label: 'Contract activated', level: 'success', category: 'governance', actorScoped: false },
  contract_superseded: { label: 'Contract superseded', level: 'warn', category: 'governance', actorScoped: false },

  /* ---- budget (P0) ----------------------------------------------------- */

  budget_adjusted: { label: 'Budget adjusted', level: 'info', category: 'governance', actorScoped: false },
  budget_reserved: { label: 'Budget reserved', level: 'info', category: 'governance', actorScoped: false },
  budget_released: { label: 'Budget released', level: 'info', category: 'governance', actorScoped: false },
  budget_charged: { label: 'Budget charged', level: 'info', category: 'governance', actorScoped: false },
  budget_reservation_denied: { label: 'Budget reservation denied', level: 'error', category: 'governance', actorScoped: false },
  budget_limit_reached: { label: 'Budget limit reached', level: 'error', category: 'governance', actorScoped: false },

  /* ---- company lifecycle (P0) ----------------------------------------- */

  company_activated: { label: 'Company activated', level: 'success', category: 'governance', actorScoped: false },
  company_paused: { label: 'Company paused', level: 'warn', category: 'governance', actorScoped: false },
  company_resumed: { label: 'Company resumed', level: 'success', category: 'governance', actorScoped: false },

  /* ---- company tasks (P0) --------------------------------------------- */

  company_task_created: { label: 'Company task created', level: 'info', category: 'governance', actorScoped: false },
  company_task_updated: { label: 'Company task updated', level: 'info', category: 'governance', actorScoped: false },
};

/** Human-readable line for an event, preferring the event's own message. */
export function eventMessage(event: KayanEvent): string {
  const msg = event.payload?.message;
  return typeof msg === 'string' && msg.length > 0 ? msg : EVENT_DEFS[event.type].label;
}

/** Presentation level for an event. */
export function eventLevel(event: KayanEvent): EventDefinition['level'] {
  return EVENT_DEFS[event.type].level;
}

/**
 * Producer of `KayanEvent`s â€” the swappable boundary.
 *
 * `MockEventSource` implements it locally today. `FastApiEventSource` will
 * implement it by forwarding WebSocket frames; because the payload shape is
 * identical, the store, reducer, UI and 3D layer require no changes.
 */
export interface KayanEventSource {
  /** Subscribe to emitted events. Returns an unsubscribe function. */
  subscribe(listener: (event: KayanEvent) => void): () => void;
  /** Subscribe to engine run status (started / idle). */
  subscribeStatus(listener: (running: boolean) => void): () => void;
  /** Begin a scripted order run. */
  runOrder(): void;
  /** Re-emit a recorded history, preserving the original relative timing. */
  replay(history: KayanEvent[]): void;
  /** Events emitted by the most recent run, oldest first. */
  history(): KayanEvent[];
}

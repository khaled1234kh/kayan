/**
 * TrustGate policy contracts.
 *
 * These types are the boundary between AI intent and authorized action. The 3D
 * layer never sees them: a decision is converted into a `policy_denied` or a
 * normal lifecycle event before it reaches the reducer.
 */

/** Verdict produced by the gate. */
export type PolicyEffect = 'allow' | 'deny';

/** Provenance of the instruction that caused an intent. */
export type IntentSource = 'trusted' | 'untrusted';

/**
 * What an agent is trying to do, created **before** execution.
 *
 * An agent never performs an action and asks TrustGate afterwards: it forms an
 * intent, and only an `allow` lets the action proceed. Produced by the agent
 * runtime, evaluated by the policy evaluator, never by the UI.
 */
export interface AgentIntent {
  agentId: string;
  /** Typed action, e.g. `customer_data.read`. */
  action: string;
  /** Target resource, e.g. `customer/8841`. */
  resource: string;
  /** Whether the originating instruction can be trusted. */
  source: IntentSource;
  /** Structured context the agent attached to its intent. */
  context?: Record<string, unknown>;
}

/** Backwards-compatible alias for the pre-Task-04 name. */
export type ActionIntent = AgentIntent;

/** A machine-enforced capability contract — the stand-in for Cedar policies. */
export interface CapabilityContract {
  /** Resource patterns the actor may read. */
  scope: string[];
  /** Resource patterns the actor may never touch, regardless of scope. */
  forbidden: string[];
  /** Actions that require an explicit human approval token. */
  requireApproval: string[];
}

/** Everything the evaluator needs beyond the intent itself. */
export interface AuthorizationContext {
  actorId: string;
  contract: CapabilityContract;
  /** Whether a human approval token is present for this action. */
  humanApproved: boolean;
}

/**
 * The decision record. Deliberately flat and human-readable: it is rendered in
 * the TrustGate panel and embedded in the `policy_denied` event payload.
 */
export interface PolicyDecision {
  decision: PolicyEffect;
  /** Human-readable policy name, e.g. `Customer Data Access`. */
  policy: string;
  /** Who was evaluated. */
  subject: string;
  /** What was attempted. */
  action: string;
  /** What it targeted. */
  resource: string;
  /** Why the gate decided as it did. */
  reason: string;
}

/**
 * Projection of the latest decision for the UI. Carried through the event
 * stream, so the panel is a view over history rather than a separate channel.
 */
export interface SecurityDecisionView {
  decision: PolicyEffect;
  policy: string;
  subject: string;
  action: string;
  resource: string;
  reason: string;
  /** Epoch ms, from the event that carried the decision. */
  timestamp: number;
}
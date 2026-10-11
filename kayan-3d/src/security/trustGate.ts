import type {
  AgentIntent,
  AuthorizationContext,
  CapabilityContract,
  PolicyDecision,
} from './policyTypes';

/**
 * Mock TrustGate â€” a deterministic local policy evaluator.
 *
 * This is the architectural placeholder for the real gateway. It sits between AI
 * intent and authorized action: an intent is submitted here, and only an `allow`
 * may proceed. It has no knowledge of Zustand, the reducer or the 3D scene, and
 * it never mutates application state â€” it returns a decision that the workflow
 * turns into an event.
 *
 * Replacing this file with a backend OPA/Rego decision service should not require
 * changes anywhere else.
 */

/**
 * Capability contracts, mirroring the authority lines already shown in the
 * actor inspector. Patterns use `*` as a wildcard segment.
 */
export const CAPABILITY_CONTRACTS: Record<string, CapabilityContract> = {
  manager: {
    scope: ['task/*', 'plan/*', 'inventory/*'],
    forbidden: ['customer/*', 'hr/*'],
    requireApproval: ['quote.send'],
  },
  sales: {
    scope: ['catalog/*', 'quote/*', 'task/*'],
    forbidden: ['customer/*', 'hr/*'],
    requireApproval: ['quote.send'],
  },
  operations: {
    scope: ['inventory/*', 'task/*'],
    forbidden: ['customer/*', 'hr/*'],
    requireApproval: [],
  },
  employee: {
    scope: ['task/*', 'inventory/*'],
    forbidden: ['customer/*', 'hr/*'],
    requireApproval: [],
  },
  ceo: {
    scope: ['task/*', 'customer/*', 'hr/*'],
    forbidden: [],
    requireApproval: [],
  },
};

/** Actions that touch private records; these require a trusted origin. */
const PRIVATE_DATA_ACTIONS = ['customer_data.read', 'customer_data.export'];

/** Glob matcher supporting a trailing `*` wildcard. */
function matches(pattern: string, resource: string): boolean {
  if (pattern.endsWith('/*')) {
    const prefix = pattern.slice(0, -1);
    return resource.startsWith(prefix);
  }
  if (pattern.endsWith('*')) {
    return resource.startsWith(pattern.slice(0, -1));
  }
  return pattern === resource;
}

/** Readable action label for the decision record. */
const ACTION_LABELS: Record<string, string> = {
  'customer_data.read': 'Read customer record',
  'customer_data.export': 'Export customer data',
  'inventory.read': 'Read authorized inventory information',
  'quote.draft': 'Draft quotation',
};

/** Human-readable actor label for the decision record. */
const SUBJECT_LABELS: Record<string, string> = {
  manager: 'AI Manager',
  sales: 'AI Sales',
  operations: 'AI Operations',
  employee: 'Human Employee',
  ceo: 'Nadia Farouk',
};

function deny(
  intent: AgentIntent,
  policy: string,
  reason: string,
): PolicyDecision {
  return {
    decision: 'deny',
    policy,
    subject: SUBJECT_LABELS[intent.agentId] ?? intent.agentId,
    action: ACTION_LABELS[intent.action] ?? intent.action,
    resource: intent.resource,
    reason,
  };
}

/**
 * The evaluator. Rules are evaluated in a fixed order so the same intent always
 * produces the same decision and the same reason.
 */
export function evaluatePolicy(
  intent: AgentIntent,
  context: AuthorizationContext,
): PolicyDecision {
  // 1. Explicit prohibition always wins.
  const forbidden = context.contract.forbidden.find((p) => matches(p, intent.resource));
  if (forbidden) {
    return deny(
      intent,
      'Customer Data Scope',
      'Resource outside actor authorization scope',
    );
  }

  // 2. The resource must be inside the actor's capability scope.
  const inScope = context.contract.scope.some((p) => matches(p, intent.resource));
  if (!inScope) {
    return deny(intent, 'Capability Contract', 'Action outside granted capability scope');
  }

  // 3. Private data may not be reached through an untrusted instruction.
  if (intent.source === 'untrusted' && PRIVATE_DATA_ACTIONS.includes(intent.action)) {
    return deny(intent, 'Untrusted Origin', 'Untrusted input cannot drive private data access');
  }

  // 4. Consequential actions require a human approval token.
  if (context.contract.requireApproval.includes(intent.action) && !context.humanApproved) {
    return deny(intent, 'Approval Gateway', 'Human approval token required');
  }

  return {
    decision: 'allow',
    policy: 'Capability Contract',
    subject: SUBJECT_LABELS[intent.agentId] ?? intent.agentId,
    action: ACTION_LABELS[intent.action] ?? intent.action,
    resource: intent.resource,
    reason: 'Within granted capability scope',
  };
}

/**
 * TrustGate entry point: authorize one intent.
 *
 * This is the single call the workflow makes. A future backend service
 * (`POST /trustgate/decide`) replaces the body of this function and nothing else.
 */
export function authorizeIntent(intent: AgentIntent): PolicyDecision {
  const contract = CAPABILITY_CONTRACTS[intent.agentId];
  if (!contract) {
    return deny(intent, 'Capability Contract', 'No capability contract for this actor');
  }
  const context: AuthorizationContext = {
    actorId: intent.agentId,
    contract,
    humanApproved: false,
  };
  return evaluatePolicy(intent, context);
}

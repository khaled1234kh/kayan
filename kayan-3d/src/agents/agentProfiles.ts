/**
 * Agent identity.
 *
 * Single source of truth for who each seat is. The seed actors in
 * `src/data/actors.ts` derive their name/role/kind/authority from here, so a role
 * is never described twice.
 *
 * Capabilities and restrictions are descriptive metadata for the collaboration
 * runtime. They document intent; they are NOT an authorization mechanism —
 * TrustGate is the enforcement point, and it is a separate module.
 */

export type AgentKind = 'human' | 'ai';

export interface AgentProfile {
  id: string;
  name: string;
  role: string;
  kind: AgentKind;
  /** One line on why this seat exists in the company. */
  objective: string;
  /** What the seat is accountable for. */
  responsibilities: string[];
  /** What the seat may do, expressed for the runtime. */
  capabilities: string[];
  /** What the seat must not do on its own initiative. */
  restrictions: string[];
  /** Short authority line reused by the inspector. */
  authority: string;
}

export const AGENT_PROFILES: AgentProfile[] = [
  {
    id: 'ceo',
    name: 'Nadia Farouk',
    role: 'Chief Executive Officer',
    kind: 'human',
    objective: 'Accountable for the final business decision on every order.',
    responsibilities: ['Review the final result', 'Approve or reject the final business action'],
    capabilities: ['review final result', 'approve final action', 'reject final action'],
    restrictions: ['Cannot be delegated approval authority'],
    authority: 'Accountable owner — final approval',
  },
  {
    id: 'employee',
    name: 'Tarek Mansour',
    role: 'Human Employee',
    kind: 'human',
    objective: 'Resolve operational ambiguity that the agents cannot settle alone.',
    responsibilities: ['Provide missing business information', 'Resolve operational ambiguity'],
    capabilities: ['provide missing information', 'resolve operational ambiguity', 'confirm business decision'],
    restrictions: ['Sees only assigned task context'],
    authority: 'Scoped access — assigned tasks only',
  },
  {
    id: 'manager',
    name: 'AI Manager',
    role: 'Coordinator',
    kind: 'ai',
    objective: 'Decompose the business goal and drive it to a decision.',
    responsibilities: [
      'Decompose the business goal',
      'Assign work to other agents',
      'Review results returned by subordinates',
    ],
    capabilities: [
      'decompose business goal',
      'assign tasks',
      'request information',
      'review subordinate results',
      'request approval',
    ],
    restrictions: ['Cannot raise its own permissions', 'Cannot approve final business action'],
    authority: 'Delegated authority — cannot self-grant',
  },
  {
    id: 'sales',
    name: 'AI Sales',
    role: 'Sales Agent',
    kind: 'ai',
    objective: 'Produce an accurate customer quotation from available data.',
    responsibilities: ['Prepare quotations', 'Inspect order details', 'Revise quotation on new information'],
    capabilities: [
      'prepare quotations',
      'inspect order details',
      'request inventory information',
      'revise quotation',
    ],
    restrictions: ['Cannot finalise without CEO approval', 'Cannot access customer records'],
    authority: 'Capability contract — draft_quote only',
  },
  {
    id: 'operations',
    name: 'AI Operations',
    role: 'Operations Agent',
    kind: 'ai',
    objective: 'Establish what can actually be fulfilled, and report conflicts honestly.',
    responsibilities: ['Inspect inventory', 'Validate availability', 'Report inventory conflicts'],
    capabilities: [
      'inspect inventory',
      'validate availability',
      'report inventory conflicts',
      'request clarification',
    ],
    restrictions: ['Cannot modify pricing', 'Cannot access customer records'],
    authority: 'Capability contract — stock read only',
  },
];

const BY_ID = new Map(AGENT_PROFILES.map((p) => [p.id, p]));

export function getAgentProfile(id: string): AgentProfile | undefined {
  return BY_ID.get(id);
}

export function requireAgentProfile(id: string): AgentProfile {
  const p = BY_ID.get(id);
  if (!p) throw new Error(`Unknown agent profile: ${id}`);
  return p;
}

export const AGENT_IDS: string[] = AGENT_PROFILES.map((p) => p.id);

/**
 * External, non-seat senders.
 *
 * Supplier instructions arrive from outside the company. They are represented as
 * structured messages so the collaboration transcript stays complete, but they
 * are not agents, have no seat on the floor and no mailbox.
 */
export const EXTERNAL_SENDERS: Record<string, string> = {
  'ext:supplier': 'External Supplier',
};

/** True when the id is a seated agent rather than an external sender. */
export function isSeat(id: string): boolean {
  return BY_ID.has(id);
}
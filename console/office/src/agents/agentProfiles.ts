/**
 * Agent identity for the pentest pivot.
 *
 * Single source of truth for who each seat is. The seed actors in
 * `src/data/actors.ts` derive their name/role/kind/authority from here, so a role
 * is described exactly once.
 *
 * Capabilities and restrictions are descriptive metadata for the collaboration
 * runtime. They document intent; they are NOT an authorization mechanism —
 * TrustGate is the enforcement point, and it is a separate module.
 */

export type AgentKind = 'ai'; // every seat on this floor is an AI agent

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
  /** TrustGate model tier — A / B / C, resolved to a real model name at startup. */
  modelTier: 'A' | 'B' | 'C';
}

export const AGENT_PROFILES: AgentProfile[] = [
  {
    id: 'planner', name: 'Planner Agent', role: 'planner', kind: 'ai',
    objective: 'Decompose the signed ROE into governed specialist assignments.',
    responsibilities: ['Plan the assessment', 'Assign specialist tasks', 'Respect reporting dependencies'],
    capabilities: ['ROE-scoped planning', 'governed task assignment'],
    restrictions: ['Cannot execute specialist tools', 'Cannot expand scope or permissions'],
    authority: 'Capability contract — planning only', modelTier: 'A',
  },
  {
    id: 'ai-manager',
    name: 'Recon Agent',
    role: 'recon',
    kind: 'ai',
    objective: 'Reconnaissance and discovery — map the target and find entry points.',
    responsibilities: ['Probe authorized endpoints', 'Discover exposed lab services', 'Capture reconnaissance evidence'],
    capabilities: ['passive enumeration', 'active scanning', 'service discovery', 'os fingerprinting'],
    restrictions: ['Cannot access out-of-scope targets', 'Cannot exfiltrate data', 'Cannot raise its own permissions'],
    authority: 'ROE-scoped tool authorization',
    modelTier: 'B',
  },
  {
    id: 'ai-sales',
    name: 'Web-App Agent',
    role: 'webapp',
    kind: 'ai',
    objective: 'OWASP Top 10 testing against in-scope web assets.',
    responsibilities: ['Test in-scope web endpoints', 'Capture request and response evidence', 'Report detected weaknesses'],
    capabilities: ['sql injection test', 'xss test', 'command injection test', 'directory traversal'],
    restrictions: ['Cannot execute without TrustGate authorization', 'Cannot test out-of-scope targets'],
    authority: 'ROE-scoped tool authorization',
    modelTier: 'A',
  },
  {
    id: 'ai-ops',
    name: 'Network Agent',
    role: 'network',
    kind: 'ai',
    objective: 'Port scanning and service detection within the authorized lab.',
    responsibilities: ['Discover open ports', 'Collect service banners', 'Report network observations'],
    capabilities: ['port scan', 'service detection', 'network topology mapping', 'banner grabbing'],
    restrictions: ['Cannot modify target systems', 'Cannot scan out-of-scope targets'],
    authority: 'ROE-scoped tool authorization',
    modelTier: 'C',
  },
  {
    id: 'human',
    name: 'Reporting Agent',
    role: 'reporting',
    kind: 'ai',
    objective: 'Convert verified findings into MITRE ATT&CK-mapped reports.',
    responsibilities: ['Mitre mapping', 'finding aggregation', 'report generation', 'cvss scoring'],
    capabilities: ['mitre mapping', 'finding aggregation', 'report generation', 'cvss scoring'],
    restrictions: ['Cannot execute tools directly', 'Cannot modify target systems'],
    authority: 'Capability contract — reporting only',
    modelTier: 'B',
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
 * External instructions arrive from outside the company. They are represented as
 * structured messages so the collaboration transcript stays complete, but they
 * are not agents, have no seat on the floor and no mailbox.
 */
export const EXTERNAL_SENDERS: Record<string, string> = {
  'ext:target': 'External Target',
};

/** True when the id is a seated agent rather than an external sender. */
export function isSeat(id: string): boolean {
  return BY_ID.has(id);
}

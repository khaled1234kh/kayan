/**
 * Role ↔ desk slot mapping for the pentest pivot.
 *
 * Maps each pentest agent ID to the desk slot it occupies in the 3D office.
 * The old ceo compatibility key is excluded from this five-agent mapping;
 * it does not create a sixth visible employee. Every mapped seat is an agent.
 *
 * Screen layouts are assigned by role so each desk's monitor communicates its
 * function visually at a glance:
 *   - graph   → Recon (investigations, connections)
 *   - table   → Web-App (structured request/response testing)
 *   - grid    → Network (port/service inventory)
 *   - grid    → Reporting (findings catalog)
 */

export type PentestRole = 'planner' | 'recon' | 'webapp' | 'network' | 'reporting';
export type DeskSlot = 'planner' | 'ai-manager' | 'ai-sales' | 'ai-ops' | 'human';

export interface RoleDeskMapping {
  /** Pentest agent role key. */
  pentestRole: PentestRole;
  /** Desk slot (former AI agent role). */
  deskSlot: DeskSlot;
  /** Screen layout rendered on the monitor at this desk. */
  screenLayout: 'graph' | 'table' | 'grid';
  /** Role accent hex (TrustGate decision colors, synced with 2D console). */
  accentHex: string;
  /** Human-readable display name shown on the desk name tag. */
  displayName: string;
  /** Short objective shown in the inspector. */
  objective: string;
  /** Display descriptions; the actual backend contract is authoritative. */
  capabilities: string[];
  /** Restrictions the seat must observe (TrustGate enforced). */
  restrictions: string[];
}

/**
 * The mapping table. Every pentest role maps to exactly one desk slot.
 * The 'ceo' compatibility key is NOT in this table.
 */
export const ROLE_DESK_MAPPING: RoleDeskMapping[] = [
  {
    pentestRole: 'planner', deskSlot: 'planner', screenLayout: 'graph', accentHex: '#1FB8C4',
    displayName: 'Planner Agent', objective: 'Plan the signed assessment and assign specialist tasks.',
    capabilities: ['governed task planning', 'specialist assignment'],
    restrictions: ['Cannot expand signed scope', 'Cannot execute specialist tools'],
  },
  {
    pentestRole: 'recon',
    deskSlot: 'ai-manager',
    screenLayout: 'graph',
    accentHex: '#1FB8C4', // console --info (teal)
    displayName: 'Recon Agent',
    objective: 'Reconnaissance and discovery — map the target and find entry points.',
    capabilities: ['HTTP lab probe', 'scoped lab port scan', 'endpoint discovery'],
    restrictions: ['Cannot access out-of-scope targets', 'Cannot exfiltrate data'],
  },
  {
    pentestRole: 'webapp',
    deskSlot: 'ai-sales',
    screenLayout: 'table',
    accentHex: '#F5A623', // console --info (orange)
    displayName: 'Web-App Agent',
    objective: 'OWASP Top 10 testing against in-scope web assets.',
    capabilities: ['sql injection test', 'xss test', 'command injection test', 'directory traversal'],
    restrictions: ['Cannot execute without TrustGate authorization', 'Cannot test out-of-scope targets'],
  },
  {
    pentestRole: 'network',
    deskSlot: 'ai-ops',
    screenLayout: 'grid',
    accentHex: '#8FD4B8', // console --info (mint)
    displayName: 'Network Agent',
    objective: 'Port and service checks within the authorized lab.',
    capabilities: ['scoped lab port scan', 'service response inspection'],
    restrictions: ['Cannot modify target systems', 'Cannot scan out-of-scope targets'],
  },
  {
    pentestRole: 'reporting',
    deskSlot: 'human',
    screenLayout: 'grid',
    accentHex: '#C4694F', // console --deny (red) — reporting is the final gate
    displayName: 'Reporting Agent',
    objective: 'Convert verified findings into MITRE ATT&CK-mapped reports.',
    capabilities: ['MITRE mapping', 'verified finding aggregation', 'report generation'],
    restrictions: ['Cannot execute tools directly', 'Cannot modify target systems'],
  },
];

/**
 * Lookup by desk slot → mapping entry (for the scene renderer).
 */
export const MAPPING_BY_DESK_SLOT: Record<DeskSlot, RoleDeskMapping> = Object.fromEntries(
  ROLE_DESK_MAPPING.map((m) => [m.deskSlot, m])
) as Record<DeskSlot, RoleDeskMapping>;

/**
 * Lookup by pentest role → mapping entry (for the orchestrator/agent code).
 */
export const MAPPING_BY_PENTEST_ROLE: Record<PentestRole, RoleDeskMapping> = Object.fromEntries(
  ROLE_DESK_MAPPING.map((m) => [m.pentestRole, m])
) as Record<PentestRole, RoleDeskMapping>;

/**
 * Desk slots in floor order (left-to-right, back-to-front). Used to render
 * actor slots consistently.
 */
export const DESK_ORDER: DeskSlot[] = ['planner', 'ai-manager', 'ai-sales', 'ai-ops', 'human'];

/**
 * Legacy compatibility key; never assigned or rendered as a TrustGate employee.
 */
export const RETIRED_SLOTS: string[] = ['ceo'];

import type { Actor } from '../types';
import { AGENT_PROFILES } from '../agents/agentProfiles';

/** Front workstations face into the operations floor; rotate the entire assembly. */
export const workstationRotation = (actor: Actor) => actor.gridPosition.z > 6 ? Math.PI : 0;

/**
 * Seed workforce.
 *
 * Identity (name, role, kind, authority) comes from `AGENT_PROFILES`, so a role is
 * described exactly once. Only spatial placement is defined here.
 */
export const PLACEMENT: Record<string, { gridPosition: Actor['gridPosition']; zoneId: string }> = {
  planner: { gridPosition: { x: 6, z: 10.5 }, zoneId: 'operations' },
  ceo: { gridPosition: { x: 9.5, z: 2.5 }, zoneId: 'ceo' },
  employee: { gridPosition: { x: 8.5, z: 9.5 }, zoneId: 'operations' },
  manager: { gridPosition: { x: 5.5, z: 5.5 }, zoneId: 'meeting' },
  sales: { gridPosition: { x: 2.5, z: 2.5 }, zoneId: 'sales' },
  operations: { gridPosition: { x: 9.5, z: 9.5 }, zoneId: 'operations' },
  'ai-manager': { gridPosition: { x: 2.5, z: 2.5 }, zoneId: 'operations' },
  'ai-sales': { gridPosition: { x: 2.5, z: 9.5 }, zoneId: 'sales' },
  'ai-ops': { gridPosition: { x: 9.5, z: 2.5 }, zoneId: 'operations' },
  human: { gridPosition: { x: 9.5, z: 9.5 }, zoneId: 'operations' },
};

export const SEED_ACTORS: Actor[] = AGENT_PROFILES.map((profile) => ({
  id: profile.id,
  name: profile.name,
  role: profile.role,
  kind: profile.kind,
  authority: profile.authority,
  modelTier: profile.modelTier,
  gridPosition: PLACEMENT[profile.id].gridPosition,
  zoneId: PLACEMENT[profile.id].zoneId,
  state: 'idle',
  taskId: null,
  activity: profile.kind === 'ai' ? 'Standing by' : 'Available',
}));

/** Every seat participating in a standard order. */
export const PARTICIPANT_IDS: string[] = SEED_ACTORS.map((a) => a.id);

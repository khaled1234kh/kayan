import type { Actor } from '../types';
import { AGENT_PROFILES } from '../agents/agentProfiles';

/**
 * Seed workforce.
 *
 * Identity (name, role, kind, authority) comes from `AGENT_PROFILES`, so a role
 * is described exactly once. Only spatial placement is defined here.
 *
 * Placement is a 2x2 pod grid plus a supervisor desk at the front of the aisle:
 *   front-left   world(-3.5, +3.5)  tile(2.5, 9.5)
 *   front-right  world(+3.5, +3.5)  tile(9.5, 9.5)
 *   back-left    world(-3.5, -3.5)  tile(2.5, 2.5)
 *   back-right   world(+3.5, -3.5)  tile(9.5, 2.5)
 *   manager      world( 0.0, +4.5)  tile(6.0, 10.5) — unpartitioned, front of aisle
 * The four pods sit either side of the cross aisle at x=0 / z=0, which is left
 * clear for the floor LED path. Tile -> world is `tileToWorld`, offset by GRID/2.
 */
const PLACEMENT: Record<string, { gridPosition: Actor['gridPosition']; zoneId: string }> = {
  ceo: { gridPosition: { x: 9.5, z: 9.5 }, zoneId: 'ceo' },
  employee: { gridPosition: { x: 2.5, z: 2.5 }, zoneId: 'operations' },
  manager: { gridPosition: { x: 6.0, z: 10.5 }, zoneId: 'meeting' },
  sales: { gridPosition: { x: 2.5, z: 9.5 }, zoneId: 'sales' },
  operations: { gridPosition: { x: 9.5, z: 2.5 }, zoneId: 'operations' },
};

export const SEED_ACTORS: Actor[] = AGENT_PROFILES.map((profile) => ({
  id: profile.id,
  name: profile.name,
  role: profile.role,
  kind: profile.kind,
  authority: profile.authority,
  gridPosition: PLACEMENT[profile.id].gridPosition,
  zoneId: PLACEMENT[profile.id].zoneId,
  state: 'idle',
  taskId: null,
  activity: profile.kind === 'ai' ? 'Standing by' : 'Available',
}));

/** Every seat participating in a standard order. */
export const PARTICIPANT_IDS: string[] = SEED_ACTORS.map((a) => a.id);
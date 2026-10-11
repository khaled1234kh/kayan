/**
 * Floor layout data. Tile coordinates on a 12x12 grid; the scene maps them to
 * world space via `tileToWorld`. Kept as data so a backend can relocate desks.
 */

export const GRID = 12;

export interface ZoneDef {
  id: string;
  label: string;
  /** Inclusive tile bounds. */
  x0: number;
  x1: number;
  z0: number;
  z1: number;
  /** Floor tint. */
  tint: string;
  /** Draw the room outline in the warning hue (TrustGate room). */
  red?: boolean;
}

export const ZONES: ZoneDef[] = [
  { id: 'reception', label: 'RECEPTION', x0: 4, x1: 7, z0: 8, z1: 10, tint: '#16324A' },
  { id: 'ceo', label: 'CEO OFFICE', x0: 8, x1: 10, z0: 1, z1: 3, tint: '#1B3A52' },
  { id: 'sales', label: 'SALES', x0: 1, x1: 3, z0: 1, z1: 3, tint: '#163C4A' },
  { id: 'operations', label: 'OPERATIONS', x0: 8, x1: 10, z0: 8, z1: 10, tint: '#163C4A' },
  { id: 'meeting', label: 'MEETING ROOM', x0: 4, x1: 6, z0: 4, z1: 6, tint: '#1B3A52' },
  { id: 'trustgate', label: 'TRUSTGATE', x0: 1, x1: 3, z0: 8, z1: 10, tint: '#1B2A38', red: true },
];

/** Base palette, kept in sync with the KAYAN console. */
export const COLORS = {
  bg: '#0F2438',
  surface: '#13293C',
  text: '#F5F0E6',
  muted: '#8B9AAB',
  teal: '#1FB8C4',
  orange: '#F5A623',
  red: '#C4694F',
  floor: '#101F31',
  wall: '#24455F',
  deskTop: '#2E4257',
  deskSide: '#22344A',
  monitor: '#0C1A26',
} as const;

/**
 * Actor state → visual language. Restrained on purpose: one accent per state,
 * no neon, no arcade colours.
 */
export const STATE_COLOR: Record<string, string> = {
  idle: '#8B9AAB',
  working: '#1FB8C4',
  waiting: '#F5A623',
  awaiting_approval: '#F5A623',
  blocked: '#C4694F',
  completed: '#1FB8C4',
};

/** Short status label shown in the UI. */
export const STATE_LABEL: Record<string, string> = {
  idle: 'Idle',
  working: 'Working',
  waiting: 'Waiting',
  awaiting_approval: 'Awaiting approval',
  blocked: 'Blocked',
  completed: 'Completed',
};
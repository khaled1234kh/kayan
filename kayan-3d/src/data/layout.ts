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

/**
 * Room shell dimensions and workstation metrics.
 *
 * The scene's unit is ~1.06 m (the actors are authored to 1.65 units tall, which
 * reads as ~1.75 m), so these read as metres with roughly a 6% offset.
 * ROOM_W/ROOM_D match the 12-tile grid plus the floor overhang.
 */
export const ROOM_W = 12.8;
export const ROOM_D = 12.8;
/** Tall, open shell — the reference has no low room walls, only glazing. */
export const ROOM_H = 3.4;

/** Workstations. Five actors exist, so the grid is 2x2 plus one. */
export const GRID_COUNT = 5;

/**
 * Frosted-glass cubicle height. The reference panels rise clearly above a
 * seated figure's head, so this is taller than the brief's "desk + 40 cm" hint.
 */
export const PARTITION_HEIGHT = 1.45;

/**
 * Desk surface height.
 *
 * NOT hand-authored: derived from where the Mixamo sitting-typing clip actually
 * puts the fingertips. Probed at four actors (`out/probe-fingertips.mjs`), the
 * non-manager fingertip Y mean is 0.6725; keycaps sit ~1 cm under the
 * fingertips at rest, and the keyboard base adds 0.03, so 0.6725 - 0.01 - 0.03
 * = 0.6325.
 *
 * The previous 0.72 was set before the native clip drove the arms and left the
 * hands ~9 cm below the keycaps.
 */
export const DESK_TOP_Y = 0.6325;

/**
 * Base palette, kept in sync with the KAYAN console.
 *
 * `bg` / `surface` / `text` / `muted` / `teal` / `orange` / `red` are retained
 * because the UI overlay and the actor state markers read them, and those files
 * are out of scope for the office rebuild. The office geometry keys below carry
 * the cinematic night palette.
 */
export const COLORS = {
  // --- retained: UI chrome + state language (not part of the office rebuild) ---
  bg: '#0F2438',
  surface: '#13293C',
  text: '#F5F0E6',
  muted: '#8B9AAB',
  teal: '#1FB8C4',
  orange: '#F5A623',
  red: '#C4694F',
  /** Legacy key; superseded by monitorBezel / monitorScreen in Phase D. */
  monitor: '#0C1A26',

  // --- office shell ---
  backgroundDark: '#0A0D12',
  backgroundMid: '#14181F',
  wall: '#1A1F26',
  glass: '#E8F0F2',
  glassFrame: '#0F1216',
  floor: '#10141A',

  // --- workstation ---
  deskTop: '#2A241E',
  /** Legacy key; superseded by deskEdge / deskLeg in Phase D. */
  deskSide: '#1A1713',
  deskEdge: '#1A1713',
  deskLeg: '#0D1014',
  monitorBezel: '#0A0C0F',
  monitorScreen: '#050608',
  keyboardBody: '#1A1D22',
  keyboardKeys: '#24282F',
  mouseBody: '#1A1D22',
  chair: '#14171C',

  // --- decor ---
  plantGreen: '#2E4A3A',
  plantPot: '#101215',

  // --- emissive accents ---
  ledWarm: '#F5A623',
  ledCool: '#1FB8C4',
  accentWarm: '#FFB25C',

  // --- lighting ---
  lightAmbient: '#1A1E24',
  lightKey: '#FFF0DC',
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
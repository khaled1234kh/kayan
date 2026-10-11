import { COLORS, DESK_TOP_Y } from '../../data/layout';
import { MonitorScreen } from './MonitorScreen';
import type { ActorRole } from './materials';

/**
 * Desk monitor (Phase D3).
 *
 * Replaces the foundation build's floating bezel box with a real monitor:
 * a weighted base, a neck, and a bezel tilted back ~8° so the face points up
 * toward a seated eye rather than straight ahead.
 *
 * The screen is dark at idle (COLORS.monitorScreen, near-black). The foundation
 * build drove the bezel emissive with COLORS.teal, which made every monitor a
 * bright teal slab and fought the night palette; the accent now comes only from
 * the faint UI shapes inside the screen.
 *
 * TODO(phase-live-session): wire the panel to the actor's live session — the
 * active task graph, handoff history and current state — instead of the static
 * abstract shapes that MonitorScreen draws today. Until that lands the screen is
 * deliberately dark at idle and only lights when an actor is actually working.
 */

const BEZEL_W = 0.64;
const BEZEL_H = 0.4;
const BEZEL_D = 0.05;
const NECK_H = 0.2;
const BASE_W = 0.26;
const BASE_D = 0.19;
const BASE_T = 0.018;
/** Distance from the desk centre back to the base's centre. See the note below. */
const BASE_Z = 0.225;
/**
 * Panel centre above the neck's top. Measured, not guessed: the rig's seated
 * Head bone sits at y = 1.0115, so the screen centre is placed just under eye
 * level. The foundation build stacked this to ~1.22, which put the top of the
 * bezel above the actor's head.
 */
const PANEL_LIFT = 0.06;
/** Back-tilt so the face aims at a seated eye. */
const TILT = -0.14;

export function Monitor({
  role,
  /** Horizontal offset from the desk centre, for multi-monitor desks. */
  offsetX = 0,
  active = false,
}: {
  role: ActorRole;
  offsetX?: number;
  active?: boolean;
}) {
  return (
    /* Pushed back to z = 0.225. The base used to sit at z = 0, so its near edge
       (-0.095) landed INSIDE the keyboard, which occupies z -0.09..0.07 at
       DeskInput's -0.01. Base and keyboard interpenetrated on all three axes and
       the base physically covered the keycaps, so no hand placement could ever
       be seen from any camera angle.

       New near edge = 0.225 - 0.095 = 0.13, which clears the keyboard's far
       edge (0.07) by 0.06. The base's far edge lands at 0.32, still inside the
       0.9-deep desk top, and the panel sits 0.215 further from the actor while
       its centre stays at y = 0.998 — the measured seated eye height — so the
       screen still meets the actor's line of sight. */
    <group position={[offsetX, 0, BASE_Z]}>
      {/* weighted base */}
      <mesh position={[0, DESK_TOP_Y + BASE_T / 2, 0]} castShadow receiveShadow>
        <boxGeometry args={[BASE_W, BASE_T, BASE_D]} />
        <meshStandardMaterial color={COLORS.monitorBezel} roughness={0.6} metalness={0.3} />
      </mesh>

      {/* neck */}
      <mesh position={[0, DESK_TOP_Y + BASE_T + NECK_H / 2, -0.01]} castShadow>
        <boxGeometry args={[0.07, NECK_H, 0.05]} />
        <meshStandardMaterial color={COLORS.monitorBezel} roughness={0.55} metalness={0.35} />
      </mesh>

      {/* bezel + screen, tilted back */}
      <group
        position={[0, DESK_TOP_Y + BASE_T + NECK_H + PANEL_LIFT, 0.01]}
        rotation={[TILT, 0, 0]}
      >
        <mesh castShadow>
          <boxGeometry args={[BEZEL_W, BEZEL_H, BEZEL_D]} />
          <meshStandardMaterial
            color={COLORS.monitorBezel}
            emissive={active ? COLORS.teal : '#000000'}
            emissiveIntensity={active ? 0.25 : 0}
            roughness={0.5}
            metalness={0.25}
          />
        </mesh>
        {/* Screen sits on the -Z face, because that is the side the actor is on
            (ActorSeat places the figure at z = -0.6). Mounting it on +Z put it
            behind the bezel, where the actor saw only the casing. */}
        <group position={[0, 0, -(BEZEL_D / 2 + 0.0005)]} rotation={[0, Math.PI, 0]}>
          <MonitorScreen role={role} />
        </group>
      </group>
    </group>
  );
}

export default Monitor;
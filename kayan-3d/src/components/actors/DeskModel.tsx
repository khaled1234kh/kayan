import { COLORS, DESK_TOP_Y } from '../../data/layout';

/**
 * Workstation desk (Phase D1/D2).
 *
 * One component, instanced once per actor. The reference desks are a dark slab
 * on a pedestal — a clean horizontal plane rather than the solid block the
 * foundation build used — so the geometry is built as distinct parts:
 *
 *   top slab      the full 1.6 x 0.9 work surface at DESK_TOP_Y
 *   pedestal      a three-drawer carcass under one side, which is what gives the
 *                 reference its asymmetry and stops the desk reading as a box
 *   legs          slim matte posts at the two far corners
 *
 * Height is taken from DESK_TOP_Y rather than restated, so layout.ts stays the
 * single source of truth. Measured against the rig (scripts/measure-elbow.mjs)
 * the seated elbow sits at y = 0.884, so the surface lands 0.164 below it —
 * inside the normal 0.10-0.20 band for a seated typing posture.
 *
 * Nothing here reads the actor position: the desk is placed by its parent's
 * group transform, exactly as the figure and chair are.
 */

const TOP_W = 1.6;
const TOP_D = 0.9;
const TOP_T = 0.05;
const PEDESTAL_W = 0.42;
const PEDESTAL_D = 0.74;
/**
 * Pedestal height is DERIVED, not fixed: the carcass runs from the floor up to
 * the underside of the top, so it keeps reaching the floor when DESK_TOP_Y
 * changes. It was hard-coded at 0.62, which was tuned for the old 0.72 desk and
 * would have sunk 0.33 below the floor once the desk dropped to 0.6325.
 */
const PEDESTAL_H = DESK_TOP_Y - TOP_T;
const DRAWERS = 3;
/** Horizontal inset of the pedestal from the desk's short edge. */
const PEDESTAL_INSET = 0.07;
const LEG_R = 0.028;

export function DeskModel() {
  const topY = DESK_TOP_Y;
  const slabY = topY - TOP_T / 2;
  const pedY = PEDESTAL_H / 2;
  const pedX = -(TOP_W / 2 - PEDESTAL_W / 2 - PEDESTAL_INSET);
  const legH = topY - TOP_T;
  const drawerH = (PEDESTAL_H - 0.04) / DRAWERS;

  return (
    <group>
      {/* D1 — work surface */}
      <mesh position={[0, slabY, 0]} castShadow receiveShadow>
        <boxGeometry args={[TOP_W, TOP_T, TOP_D]} />
        <meshStandardMaterial color={COLORS.deskTop} roughness={0.82} metalness={0.06} />
      </mesh>

      {/* D1 — three-drawer pedestal under the left side */}
      <mesh position={[pedX, pedY, 0]} castShadow receiveShadow>
        <boxGeometry args={[PEDESTAL_W, PEDESTAL_H, PEDESTAL_D]} />
        <meshStandardMaterial color={COLORS.deskEdge} roughness={0.88} metalness={0.04} />
      </mesh>
      {Array.from({ length: DRAWERS }, (_, i) => {
        // Drawer fronts face +Z, inset into the carcass so they read as seams.
        const y = topY - TOP_T - 0.02 - (i + 0.5) * drawerH;
        return (
          <mesh key={i} position={[pedX, y, PEDESTAL_D / 2 + 0.006]} castShadow>
            <boxGeometry args={[PEDESTAL_W - 0.07, drawerH - 0.025, 0.012]} />
            <meshStandardMaterial color={COLORS.deskLeg} roughness={0.7} metalness={0.12} />
          </mesh>
        );
      })}

      {/* D1 — matte legs on the open side, plus the rear rail */}
      {[-1, 1].map((s) => (
        <mesh
          key={s}
          position={[TOP_W / 2 - 0.13 - PEDESTAL_INSET, legH / 2, (s * (TOP_D - 0.16)) / 2]}
          castShadow
        >
          <cylinderGeometry args={[LEG_R, LEG_R * 1.15, legH, 10]} />
          <meshStandardMaterial color={COLORS.deskLeg} roughness={0.94} metalness={0.02} />
        </mesh>
      ))}
      <mesh position={[0.18, 0.055, 0]} castShadow>
        <boxGeometry args={[0.05, 0.11, TOP_D - 0.3]} />
        <meshStandardMaterial color={COLORS.deskLeg} roughness={0.94} metalness={0.02} />
      </mesh>

      {/* D6 — under-desk warm LED strip, recessed so it lights the floor edge
          rather than glaring. Warm orange is reserved for desks; the cyan accent
          belongs to the partition feet (Partitions.tsx). */}
      <mesh position={[0.05, topY - TOP_T - 0.03, TOP_D / 2 - 0.12]}>
        <boxGeometry args={[TOP_W - 0.5, 0.016, 0.02]} />
        <meshStandardMaterial
          color={COLORS.ledWarm}
          emissive={COLORS.ledWarm}
          emissiveIntensity={2.2}
          toneMapped={false}
        />
      </mesh>
    </group>
  );
}

export default DeskModel;
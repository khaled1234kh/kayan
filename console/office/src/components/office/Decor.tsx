import { COLORS } from '../../data/layout';

/**
 * Ambient decor (Phase E).
 *
 * Furniture that makes the room read as inhabited rather than as five desks in
 * a void. Deliberately sparse: the reference is a clean executive floor, so
 * every piece earns its place or it is cut.
 *
 * Two rules govern this file.
 *
 * 1. Nothing sits in the cross-aisle `|x| < 1.75, |z| < 1.75`. That square is
 *    reserved for the Phase F floor LED path, and it is also the walkway the
 *    camera looks down. All placements are verified against it (and against
 *    every desk and glass panel) by `scripts/verify-decor.mjs`.
 * 2. Geometry and materials are shared aggressively. Every plant in the scene
 *    draws from two pot materials and two foliage materials, so adding a
 *    twelfth plant costs a transform, not a material.
 *
 * Plants are deliberately varied in height: the floor plants are tall enough to
 * break the horizontal line of the partitions, the cabinet-top and shelf plants
 * are small accents. Identical sizes read as a repeated stamp.
 */

/* ------------------------------------------------------------------ plants */

const POT_MATS = [
  { color: COLORS.plantPot, roughness: 0.9 },
  { color: '#1A1713', roughness: 0.85 },
  { color: '#22262B', roughness: 0.8 },
];
const LEAF_MATS = [
  { color: COLORS.plantGreen, roughness: 0.85 },
  { color: '#3A5C46', roughness: 0.8 },
  { color: '#26443A', roughness: 0.9 },
];

/**
 * A potted plant. `size` scales the whole thing; `seed` picks a pot/foliage pair
 * and a frond count so no two are identical. Built from cones and spheres —
 * a stylised plant suits the flat-shaded look better than a detailed mesh and
 * costs a handful of triangles.
 */
export function Plant({
  position,
  size = 1,
  seed = 0,
  castShadow = true,
}: {
  position: [number, number, number];
  size?: number;
  seed?: number;
  castShadow?: boolean;
}) {
  const pot = POT_MATS[seed % POT_MATS.length];
  const leaf = LEAF_MATS[(seed + 1) % LEAF_MATS.length];
  const fronds = 3 + (seed % 3);
  const potR = 0.16 * size;
  const potH = 0.2 * size;

  return (
    <group position={position}>
      {/* pot */}
      <mesh position={[0, potH / 2, 0]} castShadow={castShadow} receiveShadow>
        <cylinderGeometry args={[potR, potR * 0.78, potH, 10]} />
        <meshStandardMaterial {...pot} metalness={0.03} />
      </mesh>
      {/* foliage: a low mound plus upright fronds */}
      <mesh position={[0, potH + 0.09 * size, 0]} castShadow={castShadow}>
        <sphereGeometry args={[0.13 * size, 8, 6]} />
        <meshStandardMaterial {...leaf} metalness={0.0} />
      </mesh>
      {Array.from({ length: fronds }, (_, i) => {
        const a = (i / fronds) * Math.PI * 2 + seed;
        const lean = 0.16 + (i % 2) * 0.1;
        return (
          <mesh
            key={i}
            position={[
              Math.cos(a) * lean * size,
              potH + (0.2 + (i % 3) * 0.09) * size,
              Math.sin(a) * lean * size,
            ]}
            rotation={[Math.sin(a) * 0.45, a, Math.cos(a) * 0.45]}
            castShadow={castShadow}
          >
            <coneGeometry args={[0.055 * size, (0.34 + (i % 3) * 0.12) * size, 5]} />
            <meshStandardMaterial {...leaf} metalness={0.0} />
          </mesh>
        );
      })}
    </group>
  );
}

/* ----------------------------------------------------------------- cabinet */

/**
 * Low bookshelf / cabinet against a side wall.
 *
 * Built as an OPEN shell — back, top, bottom, two ends — rather than a solid
 * block. The first attempt used a solid carcass with the shelves mounted outside
 * it; from the room that renders as a featureless black monolith, because the
 * one face the camera sees is the closed back.
 *
 * Local axes: +X is the open front (depth into the room), Z runs along the wall.
 * A left-wall cabinet therefore needs no rotation at all — its length already
 * lies along world Z and its opening already faces world +X.
 *
 * Books are laid at varied angles on purpose: a perfectly upright row reads as
 * a texture, and a few leaning volumes make it read as a shelf someone uses.
 */
export function Cabinet({ position, rotationY = 0 }: { position: [number, number, number]; rotationY?: number }) {
  const W = 0.42; // depth into the room
  const H = 1.15;
  const L = 2.4; // length along the wall
  const T = 0.035; // panel thickness
  const SHELVES = 4;
  const shelfY = (i: number) => T + 0.05 + (i * (H - T - 0.12)) / SHELVES;

  // Deterministic book layout: 7 volumes, alternating lean and height.
  const books = Array.from({ length: 7 }, (_, i) => ({
    x: -L / 2 + 0.28 + i * 0.29,
    shelf: i % SHELVES,
    h: 0.2 + ((i * 37) % 11) / 40,
    lean: ((i * 53) % 7) / 60,
    tone: i % 3,
  }));

  return (
    <group position={position} rotation={[0, rotationY, 0]}>
      {/* back panel */}
      <mesh position={[-W / 2 + T / 2, H / 2, 0]} castShadow receiveShadow>
        <boxGeometry args={[T, H, L]} />
        <meshStandardMaterial color={COLORS.deskEdge} roughness={0.9} metalness={0.04} />
      </mesh>
      {/* top and bottom */}
      <mesh position={[0, H - T / 2, 0]} castShadow receiveShadow>
        <boxGeometry args={[W, T, L]} />
        <meshStandardMaterial color={COLORS.deskEdge} roughness={0.9} metalness={0.04} />
      </mesh>
      <mesh position={[0, T / 2, 0]} castShadow receiveShadow>
        <boxGeometry args={[W, T, L]} />
        <meshStandardMaterial color={COLORS.deskEdge} roughness={0.9} metalness={0.04} />
      </mesh>
      {/* ends */}
      {[-1, 1].map((s) => (
        <mesh key={s} position={[0, H / 2, (s * (L - T)) / 2]} castShadow receiveShadow>
          <boxGeometry args={[W, H, T]} />
          <meshStandardMaterial color={COLORS.deskEdge} roughness={0.9} metalness={0.04} />
        </mesh>
      ))}
      {/* shelf boards, recessed inside the shell */}
      {Array.from({ length: SHELVES - 1 }, (_, i) => (
        <mesh key={i} position={[0, shelfY(i + 1), 0]} castShadow>
          <boxGeometry args={[W - 0.02, 0.02, L - 2 * T]} />
          <meshStandardMaterial color={COLORS.deskLeg} roughness={0.85} metalness={0.06} />
        </mesh>
      ))}
      {/* books, standing on the shelves inside the open front */}
      {books.map((b, i) => (
        <mesh
          key={i}
          position={[0.04, shelfY(b.shelf) + 0.01 + b.h / 2, b.x]}
          rotation={[0, 0, -b.lean]}
          castShadow
        >
          <boxGeometry args={[0.22, b.h, 0.05 + (i % 2) * 0.02]} />
          <meshStandardMaterial
            color={[COLORS.plantGreen, '#4A3B2A', '#2E3A4A'][b.tone]}
            roughness={0.85}
            metalness={0.02}
          />
        </mesh>
      ))}
    </group>
  );
}

/* ------------------------------------------------------------------ sconce */

/** Warm wall sconce — a small bracket plus an emissive face. */
export function Sconce({ position, rotationY = 0 }: { position: [number, number, number]; rotationY?: number }) {
  return (
    <group position={position} rotation={[0, rotationY, 0]}>
      <mesh position={[0.04, 0, 0]} castShadow>
        <boxGeometry args={[0.08, 0.26, 0.1]} />
        <meshStandardMaterial color={COLORS.deskLeg} roughness={0.7} metalness={0.3} />
      </mesh>
      <mesh position={[0.09, 0, 0]} rotation={[0, 0, Math.PI / 2]}>
        <cylinderGeometry args={[0.075, 0.055, 0.12, 10, 1, true]} />
        <meshStandardMaterial color={COLORS.deskLeg} roughness={0.6} metalness={0.3} side={2} />
      </mesh>
      <mesh position={[0.12, -0.01, 0]} rotation={[Math.PI / 2, 0, 0]}>
        <circleGeometry args={[0.055, 12]} />
        <meshStandardMaterial
          color={COLORS.ledWarm}
          emissive={COLORS.accentWarm}
          emissiveIntensity={1.4}
          toneMapped={false}
          side={2}
        />
      </mesh>
    </group>
  );
}

/* ------------------------------------------------------------------ layout */

/**
 * Decor placement.
 *
 * Left wall carries the cabinet (below the task board, which sits at y = 2.08);
 * the right wall carries the sconces. Floor plants break the partition line
 * without entering a pod. All coordinates are world space and were checked
 * against the desks, the eight glass panels and the cross-aisle.
 */
export function Decor() {
  const H = 1.15; // cabinet height — the plant on top keys off this
  return (
    <group>
      {/* tall floor plants — left and right, breaking the partition line */}
      <Plant position={[-5.85, 0, 3.1]} size={1.9} seed={1} />
      <Plant position={[5.85, 0, 2.9]} size={1.7} seed={2} />
      <Plant position={[-5.85, 0, -3.1]} size={1.6} seed={3} />

      {/* medium plant tucked into the front-right corner between wall segments */}
      <Plant position={[5.95, 0, 5.6]} size={1.35} seed={4} />

      {/* low cabinet against the left wall, under the task board. Its opening
          faces world +X (into the room) with rotationY = 0. */}
      <Cabinet position={[-6.02, 0, -0.3]} />

      {/* small plants: one on the cabinet top, two at pod corners */}
      <Plant position={[-5.95, H, 0.55]} size={0.52} seed={5} />
      <Plant position={[-5.2, 0, 4.6]} size={0.6} seed={6} />
      <Plant position={[5.2, 0, -4.7]} size={0.55} seed={7} />

      {/* warm sconces on the right wall, facing -X into the room */}
      <Sconce position={[6.28, 1.95, 1.2]} rotationY={Math.PI} />
      <Sconce position={[6.28, 1.95, -2.6]} rotationY={Math.PI} />

      {/* Phase F: the floor rug was removed here. At #2A2320 it sat within a
          few percent of the near-black floor once ambient dropped to 0.35, and
          it did not read in any render — it only added a large flat surface
          for the floor sheen to play across. Deleted rather than re-tinted;
          the reference floor is bare anyway. */}
    </group>
  );
}

export default Decor;
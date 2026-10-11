import { COLORS, DESK_TOP_Y } from '../../data/layout';
import { Keyboard } from './Keyboard';
import { Mouse } from './Mouse';

/**
 * Desk mat with keyboard and mouse (Phase D4).
 *
 * The keyboard and mouse now sit flush on the rebuilt desk surface at
 * DESK_TOP_Y instead of floating at the old hard-coded 0.8. The mat gives them a
 * shared ground so the input devices read as one object rather than two items
 * dropped on a slab.
 *
 * The mouse is offset to the keyboard's right (+X) for a right-handed operator;
 * the foundation build had it on the left. The keyboard and mouse share the mat's
 * origin so a caller places the pair with a single transform.
 */

const MAT_W = 0.72;
const MAT_D = 0.28;
const MAT_T = 0.006;

export function DeskInput() {
  return (
    <group>
      {/* mat */}
      <mesh position={[0, DESK_TOP_Y + MAT_T / 2, 0]} receiveShadow>
        <boxGeometry args={[MAT_W, MAT_T, MAT_D]} />
        <meshStandardMaterial color={COLORS.deskLeg} roughness={0.98} metalness={0.0} />
      </mesh>

      {/* Keyboard.

          x = 0.095 places the keycaps under the animated hands. The Mixamo
          sitting-typing clip drops the CEO's fingertips at a midpoint x of
          3.595 world; the desk group is centred on the seat at world x 3.5, so
          that is +0.095 in local space. It was at -0.06, which put the keys
          ~0.155 to the actor's left of where the hands actually land.

          z is unchanged at -0.01, and deliberately so: the fingertips sit at
          world z ~3.426, which is already inside the keyboard's existing span
          of 3.410..3.570, near its near edge. Recomputing the near edge from the
          fingertips would push the keyboard 0.08 backwards, away from the hands. */}
      <group position={[0.095, DESK_TOP_Y + MAT_T, -0.01]}>
        <Keyboard />
      </group>

      {/* Mouse, on the actor's RIGHT side (-X, since the actors face +Z).

          The keyboard moved to local x = 0.095 with BASE_W = 0.45, so its
          right-hand edge is now 0.095 - 0.225 = -0.130. The mouse clears that by
          0.12, landing at -0.250. It tracks the keyboard, and the 12 cm gap lets
          the hand pivot from the keys without overreaching. */}
      <group position={[-0.25, DESK_TOP_Y + MAT_T, -0.01]}>
        <Mouse />
      </group>
    </group>
  );
}

export default DeskInput;
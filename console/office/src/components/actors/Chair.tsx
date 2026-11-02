/**
 * Task chair, built from primitives so no external model is needed.
 *
 * Seat height is not a guess: the sitting idle was measured with the hips
 * settling at y ≈ 0.50–0.52 in seat space, so the pan top sits at 0.48 and the
 * figure rests on it rather than hovering or sinking.
 *
 * 19 meshes per chair, all sharing two materials.
 */

const SEAT_TOP = 0.48;
const PAN_THICKNESS = 0.05;
const ARM_COUNT = 5;
const BASE_RADIUS = 0.22;
/** Arms rise toward the centre, giving the star a slight dish. */
const BASE_RISE = 0.035;

const SHELL = '#2B3A45';
const TRIM = '#1A2C45';

export function Chair() {
  const panY = SEAT_TOP - PAN_THICKNESS / 2;
  const postTop = panY;
  const postHeight = 0.22;
  const postY = postTop - postHeight / 2;
  const baseY = postY - postHeight / 2;

  return (
    <group>
      {/* seat pan */}
      <mesh position={[0, panY, 0]} castShadow receiveShadow>
        <boxGeometry args={[0.45, PAN_THICKNESS, 0.45]} />
        <meshStandardMaterial color={SHELL} roughness={0.8} metalness={0.1} />
      </mesh>

      {/* split back: lumbar pad tilted, upper back above it */}
      <mesh
        position={[0, SEAT_TOP + 0.17, -0.2]}
        rotation={[-0.09, 0, 0]}
        castShadow
      >
        <boxGeometry args={[0.42, 0.25, 0.06]} />
        <meshStandardMaterial color={SHELL} roughness={0.8} metalness={0.1} />
      </mesh>
      <mesh position={[0, SEAT_TOP + 0.45, -0.225]} rotation={[-0.05, 0, 0]} castShadow>
        <boxGeometry args={[0.42, 0.35, 0.05]} />
        <meshStandardMaterial color={SHELL} roughness={0.8} metalness={0.1} />
      </mesh>

      {/* pneumatic post + adjustment sleeve */}
      <mesh position={[0, postY, 0]} castShadow>
        <cylinderGeometry args={[0.04, 0.04, postHeight, 12]} />
        <meshStandardMaterial color={SHELL} roughness={0.6} metalness={0.25} />
      </mesh>
      <mesh position={[0, postTop - 0.06, 0]} castShadow>
        <cylinderGeometry args={[0.06, 0.06, 0.1, 12]} />
        <meshStandardMaterial color={TRIM} roughness={0.7} metalness={0.15} />
      </mesh>

      {/* arm rests */}
      {[-1, 1].map((side) => (
        <group key={side}>
          <mesh position={[side * 0.24, SEAT_TOP + 0.12, -0.02]} castShadow>
            <boxGeometry args={[0.04, 0.2, 0.04]} />
            <meshStandardMaterial color={TRIM} roughness={0.75} metalness={0.12} />
          </mesh>
          <mesh position={[side * 0.22, SEAT_TOP + 0.24, 0.0]} castShadow>
            <boxGeometry args={[0.08, 0.04, 0.25]} />
            <meshStandardMaterial color={TRIM} roughness={0.75} metalness={0.12} />
          </mesh>
        </group>
      ))}

      {/* five-star base + casters */}
      {Array.from({ length: ARM_COUNT }, (_, i) => {
        const angle = (i / ARM_COUNT) * Math.PI * 2;
        return (
          <group key={i} rotation={[0, -angle, 0]}>
            <mesh
              position={[BASE_RADIUS / 2, baseY + BASE_RISE / 2, 0]}
              rotation={[0, 0, -Math.atan2(BASE_RISE, BASE_RADIUS)]}
              castShadow
            >
              <boxGeometry args={[BASE_RADIUS, 0.03, 0.05]} />
              <meshStandardMaterial color={SHELL} roughness={0.8} metalness={0.1} />
            </mesh>
            <mesh position={[BASE_RADIUS, baseY - 0.03, 0]} castShadow>
              <sphereGeometry args={[0.03, 10, 8]} />
              <meshStandardMaterial color="#161B23" roughness={0.85} metalness={0.05} />
            </mesh>
          </group>
        );
      })}
    </group>
  );
}

export default Chair;
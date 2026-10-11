import { COLORS, DESK_TOP_Y } from '../../data/layout';

/**
 * Desk props (Phase D5).
 *
 * Small dressing that breaks up the work surface so five identical desks do not
 * read as five identical slabs. Everything is placed relative to the desk's own
 * origin, never in world space, so moving an actor moves its props with it.
 *
 * The lamp is the only warm light source in the scene apart from the under-desk
 * strip: a small emissive face pointed down at the desk, which is what gives the
 * reference its pools of amber on otherwise dark surfaces.
 */

const Y = DESK_TOP_Y;

export function DeskProps({
  variant = 0,
  /** Attach a real PointLight at the lamp face (Phase F3). Off by default so the
      light budget stays an explicit decision at the call site. */
  lampLight = false,
}: {
  variant?: number;
  lampLight?: boolean;
}) {
  // Deterministic per-desk variation: the same desk always dresses the same way.
  const mugX = variant % 2 === 0 ? 0.56 : -0.52;
  const plantX = variant % 3 === 0 ? -0.62 : 0.6;
  const hasLamp = variant % 2 === 0 || lampLight;
  const hasNotebook = variant % 3 !== 1;

  return (
    <group>
      {/* potted plant */}
      <group position={[plantX, Y, -0.28]}>
        <mesh position={[0, 0.05, 0]} castShadow receiveShadow>
          <cylinderGeometry args={[0.055, 0.045, 0.1, 10]} />
          <meshStandardMaterial color={COLORS.plantPot} roughness={0.9} metalness={0.02} />
        </mesh>
        <mesh position={[0, 0.17, 0]} castShadow>
          <sphereGeometry args={[0.075, 8, 6]} />
          <meshStandardMaterial color={COLORS.plantGreen} roughness={0.85} metalness={0.0} />
        </mesh>
      </group>

      {/* mug */}
      <group position={[mugX, Y, 0.18]}>
        <mesh position={[0, 0.045, 0]} castShadow receiveShadow>
          <cylinderGeometry args={[0.038, 0.034, 0.09, 12]} />
          <meshStandardMaterial color={COLORS.deskEdge} roughness={0.55} metalness={0.05} />
        </mesh>
        <mesh position={[0.045, 0.045, 0]} rotation={[Math.PI / 2, 0, 0]}>
          <torusGeometry args={[0.022, 0.006, 6, 10]} />
          <meshStandardMaterial color={COLORS.deskEdge} roughness={0.55} metalness={0.05} />
        </mesh>
      </group>

      {/* notebook + pen holder.
          The notebook moved forward to z = -0.30. It sat at z = 0.24, clear of
          the monitor base while that base was at z = 0; once the base was pushed
          back to 0.225 the two overlapped on all three axes. Forward of the
          keyboard (far edge -0.09) and clear of the lamp base at x = -0.68. */}
      {hasNotebook && (
        <mesh
          position={[variant % 2 === 0 ? -0.35 : 0.35, Y + 0.012, -0.3]}
          rotation={[0, 0.3, 0]}
          castShadow
        >
          <boxGeometry args={[0.2, 0.024, 0.26]} />
          <meshStandardMaterial color={COLORS.deskEdge} roughness={0.9} metalness={0.0} />
        </mesh>
      )}
      <group position={[variant % 2 === 0 ? 0.3 : -0.32, Y, 0.3]}>
        <mesh position={[0, 0.04, 0]} castShadow>
          <cylinderGeometry args={[0.03, 0.03, 0.08, 8]} />
          <meshStandardMaterial color={COLORS.deskLeg} roughness={0.8} metalness={0.1} />
        </mesh>
        <mesh position={[0.01, 0.1, 0]} rotation={[0.2, 0, 0.1]} castShadow>
          <cylinderGeometry args={[0.004, 0.004, 0.12, 6]} />
          <meshStandardMaterial color={COLORS.ledCool} roughness={0.4} metalness={0.2} />
        </mesh>
      </group>

      {/* small desk lamp with a warm emissive face */}
      {hasLamp && (
        <group position={[-0.68, Y, -0.3]}>
          <mesh position={[0, 0.015, 0]} castShadow receiveShadow>
            <cylinderGeometry args={[0.06, 0.07, 0.03, 10]} />
            <meshStandardMaterial color={COLORS.deskLeg} roughness={0.7} metalness={0.2} />
          </mesh>
          <mesh position={[0, 0.17, 0]} rotation={[0, 0, 0.25]} castShadow>
            <cylinderGeometry args={[0.012, 0.012, 0.3, 6]} />
            <meshStandardMaterial color={COLORS.deskLeg} roughness={0.6} metalness={0.3} />
          </mesh>
          {/* shade — emissive underside, pointed down at the desk */}
          <mesh position={[0.07, 0.3, 0]} rotation={[0.35, 0, -0.5]} castShadow>
            <coneGeometry args={[0.075, 0.09, 10, 1, true]} />
            <meshStandardMaterial color={COLORS.deskLeg} roughness={0.6} metalness={0.25} side={2} />
          </mesh>
          <mesh position={[0.07, 0.275, 0.015]} rotation={[0.35, 0, -0.5]}>
            <circleGeometry args={[0.055, 12]} />
            <meshStandardMaterial
              color={COLORS.ledWarm}
              emissive={COLORS.accentWarm}
              emissiveIntensity={1.6}
              toneMapped={false}
              side={2}
            />
          </mesh>
          {/* F3 — real light so the lamp actually bleeds onto the desk and the
              figure. castShadow is deliberately off: a shadow-casting point
              light per desk would be ruinous on a software renderer. */}
          {lampLight && (
            <pointLight
              position={[0.07, 0.26, 0.03]}
              intensity={0.6}
              distance={2.5}
              decay={2}
              color={COLORS.accentWarm}
            />
          )}
        </group>
      )}
    </group>
  );
}

export default DeskProps;
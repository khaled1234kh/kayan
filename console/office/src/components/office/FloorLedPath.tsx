import { COLORS } from '../../data/layout';

/**
 * Floor LED path (Phase F2).
 *
 * Two thin emissive strips laid into the floor forming a cross, centred on the
 * room origin: cyan along Z, warm orange along X. This is the circulation spine
 * the Phase C partitions were arranged around — the cross-aisle square is the
 * one region deliberately left empty by every desk and prop, and the path turns
 * that negative space into the room's main visual line.
 *
 * Emissive materials only, no PointLight or RectAreaLight. Five real lights for
 * two strips would cost far more than the look is worth on a software renderer,
 * and the strips read perfectly well as pure emissive geometry. If this ever
 * needs to cast light onto the floor, add one dim PointLight at the origin
 * rather than one per strip.
 *
 * The strips sit 5 mm proud of the floor and cast no shadows: a shadow caster
 * at that height produces acne along its whole length.
 */

/** Strip centreline height. */
const Y = 0.005;
/** Strip width. */
const W = 0.04;
/** Half-length of each arm. */
const L = 5;
/**
 * Emissive strength. The brief suggested ~2.0, but at that level with
 * `toneMapped={false}` both strips clip past their own hue — the warm one reads
 * yellow. At 1.0 the material renders at exactly the authored colour with no
 * channel clipping, which is what keeps orange orange and cyan cyan.
 */
const EMISSIVE = 1.0;

export function FloorLedPath() {
  // Deliberately NOT COLORS.ledCool. The partition base LEDs use #1FB8C4 at a
  // higher emissive intensity, and at the same hue the floor arm disappeared
  // into the pod outlines. This deeper, cooler teal separates the two: the
  // partitions stay the bright accent, the floor path reads as a distinct,
  // receding circulation line. Partitions are untouched.
  const cool = (
    <meshStandardMaterial
      color="#0E7F8A"
      emissive="#0E7F8A"
      emissiveIntensity={EMISSIVE}
      roughness={0.5}
      metalness={0}
      toneMapped={false}
    />
  );

  return (
    <group>
      {/* cyan spine, running along Z */}
      <mesh position={[0, Y, 0]} rotation={[-Math.PI / 2, 0, 0]}>
        <planeGeometry args={[W, L * 2]} />
        {cool}
      </mesh>

      {/* warm spine, running along X */}
      <mesh position={[0, Y, 0]} rotation={[-Math.PI / 2, 0, 0]}>
        <planeGeometry args={[L * 2, W]} />
        <meshStandardMaterial
          color={COLORS.ledWarm}
          emissive={COLORS.ledWarm}
          emissiveIntensity={EMISSIVE}
          roughness={0.5}
          metalness={0}
          toneMapped={false}
        />
      </mesh>
    </group>
  );
}

export default FloorLedPath;
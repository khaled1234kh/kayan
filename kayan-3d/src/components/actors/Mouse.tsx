import { RoundedBox } from '@react-three/drei';

/**
 * Desk mouse (Phase D4).
 *
 * Centred on its own origin, with the body resting on y = 0 — DeskInput supplies
 * the placement (to the keyboard's right on the mat). The foundation build baked
 * a -0.31 x offset into this component because it used to be rendered inside the
 * keyboard's group; that offset is now the caller's job, so the two can be
 * positioned independently.
 *
 * Four meshes: body, click seam, scroll wheel, glide pad.
 */
export function Mouse() {
  return (
    <group position={[0, 0.0125, 0]}>
      <RoundedBox args={[0.055, 0.025, 0.105]} radius={0.012} smoothness={4} castShadow receiveShadow>
        <meshStandardMaterial color="#1A2C45" roughness={0.35} metalness={0.15} />
      </RoundedBox>

      {/* left/right button seam, sunk 1mm into the top surface */}
      <mesh position={[0, 0.0125, -0.025]}>
        <boxGeometry args={[0.0012, 0.001, 0.055]} />
        <meshStandardMaterial color="#0A1A28" roughness={0.6} metalness={0.05} />
      </mesh>

      {/* scroll wheel, rolling front-to-back */}
      <mesh position={[0, 0.0135, -0.02]} rotation={[0, 0, Math.PI / 2]}>
        <cylinderGeometry args={[0.005, 0.005, 0.01, 12]} />
        <meshStandardMaterial color="#3A4A55" roughness={0.5} metalness={0.1} />
      </mesh>

      {/* glide pad */}
      <mesh position={[0, -0.013, 0]}>
        <boxGeometry args={[0.05, 0.002, 0.1]} />
        <meshStandardMaterial color="#050812" roughness={0.9} metalness={0.02} />
      </mesh>
    </group>
  );
}

export default Mouse;
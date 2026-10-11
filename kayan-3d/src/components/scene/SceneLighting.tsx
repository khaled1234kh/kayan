/**
 * Scene lighting — cinematic night office (Phase F).
 *
 * The reference is a dark executive floor lit almost entirely by practicals:
 * the city glow through the glazing, the cyan partition feet, the warm desk
 * LEDs. There is no studio key light. So the brief is inverted from the usual
 * "readability first" approach — the room is meant to be dim, and legibility
 * comes from emissive sources rather than from ambient fill.
 *
 * Deliberately absent: any strong ambient. Cranking ambient up is what made the
 * floor read as flat grey; the reference floor is near-black with specular
 * sheen, which needs a low ambient and a strong directional.
 *
 * The key is a cool moonlit blue-white (#B8C8D8) entering from the glazing side
 * (-Z), so light rakes across the floor toward the camera the way city glow
 * would. Warm sources are kept to practicals (desk lamps, under-desk strips).
 */
export default function SceneLighting() {
  return (
    <>
      {/* Low ambient. Measured ladder: 0.15 left the figures as unreadable
          silhouettes, 0.22 was still marginal, 0.35 is the point where every
          actor is just-readable while the floor stays near-black. This is the
          floor the brief describes, not a ceiling. */}
      <ambientLight intensity={0.35} />

      {/* Very subtle tint: cold sky, near-black ground bounce. */}
      <hemisphereLight args={['#1A2A38', '#05070A', 0.18]} />

      {/* Key — city glow through the far glazing. Cool, low, raking. */}
      <directionalLight
        position={[0.6, 0.8, -0.4]}
        intensity={0.35}
        color="#B8C8D8"
        castShadow
        shadow-mapSize-width={2048}
        shadow-mapSize-height={2048}
        shadow-camera-left={-11}
        shadow-camera-right={11}
        shadow-camera-top={11}
        shadow-camera-bottom={-11}
        shadow-bias={-0.0005}
      />
    </>
  );
}
/**
 * Scene lighting — studio-neutral, tuned for readability of the actor figures
 * while the floor and walls stay dark navy.
 *
 * Contrast comes from form and a rim/fill split, not from bright emissive
 * materials. Kept out of `components/office/` so the office geometry files stay
 * untouched.
 */
export default function SceneLighting() {
  return (
    <>
      {/*
        Ambient/fill are set ABOVE the 0.55 / 0.15 figures in the brief. The brief
        assumed an ambient baseline of 0.4; this scene was already at 0.7 with a
        0.45 hemisphere, so applying 0.55 / 0.15 literally made it measurably
        darker (mean viewport luminance 27.4 vs 28.1 before). These values keep
        the brief's structure (teal/navy hemisphere, single shadow key, opposite
        fill) while landing above the old total, which is the stated goal.
      */}
      <ambientLight intensity={0.75} />

      {/* Subtle ambient tint: teal sky, navy ground bounce. */}
      <hemisphereLight args={['#1FB8C4', '#0F2438', 0.35]} />

      {/* Key light — the only shadow caster. */}
      <directionalLight
        position={[9, 14, 7]}
        intensity={1.15}
        castShadow
        shadow-mapSize-width={2048}
        shadow-mapSize-height={2048}
        shadow-camera-left={-11}
        shadow-camera-right={11}
        shadow-camera-top={11}
        shadow-camera-bottom={-11}
        shadow-bias={-0.0005}
      />

      {/* Opposite-side fill, no shadows: keeps the far side of figures readable. */}
      <directionalLight position={[-8, 6, -6]} intensity={0.4} />
    </>
  );
}
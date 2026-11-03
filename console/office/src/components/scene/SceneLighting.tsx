/** Soft fill and a cool key keep furniture and seated workers readable. */
export default function SceneLighting() {
  return (
    <>
      <ambientLight intensity={1.05} />

      <hemisphereLight args={['#CBD8DF', '#354048', 0.65]} />

      {/* Static, non-shadowed studio fill reaches the floor between pods. */}
      <directionalLight position={[-6, 6, -4]} intensity={0.65} color="#CBD8DF" />

      <directionalLight
        position={[4, 8, 5]}
        intensity={1.65}
        color="#EEEAE3"
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

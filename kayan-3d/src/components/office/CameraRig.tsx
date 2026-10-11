import { useRef } from 'react';
import type { ElementRef } from 'react';
import { useFrame } from '@react-three/fiber';
import { OrbitControls, PerspectiveCamera } from '@react-three/drei';

/**
 * Camera rig. Inspection only: orbit, pan, zoom. No WASD, no first-person.
 * Polar angle is clamped so the operator can never end up under the floor.
 *
 * When a focus target is provided (the N attention shortcut), the orbit target
 * eases toward it so the camera frames the actor who needs attention, then
 * reports arrival so the caller can drop the target.
 */
export function CameraRig({
  focusTarget,
  onFocusArrived,
}: {
  focusTarget?: [number, number, number] | null;
  onFocusArrived?: () => void;
}) {
  const controls = useRef<ElementRef<typeof OrbitControls>>(null);
  const settled = useRef(false);

  useFrame((_, delta) => {
    const c = controls.current;
    if (!c || !focusTarget) return;
    const speed = Math.min(1, delta * 5);
    c.target.x += (focusTarget[0] - c.target.x) * speed;
    c.target.y += (focusTarget[1] - c.target.y) * speed;
    c.target.z += (focusTarget[2] - c.target.z) * speed;
    c.update();
    const dist = Math.hypot(
      focusTarget[0] - c.target.x,
      focusTarget[1] - c.target.y,
      focusTarget[2] - c.target.z,
    );
    if (dist < 0.02) {
      if (!settled.current) {
        settled.current = true;
        onFocusArrived?.();
      }
    } else {
      settled.current = false;
    }
  });

  return (
    <>
      <PerspectiveCamera makeDefault position={[11, 11, 13]} fov={42} near={0.1} far={120} />
      <OrbitControls
        ref={controls}
        makeDefault
        enableDamping
        dampingFactor={0.08}
        enablePan
        enableZoom
        enableRotate
        minDistance={7}
        maxDistance={34}
        minPolarAngle={0.18}
        maxPolarAngle={Math.PI * 0.46}
        target={[0, 0.4, 0]}
      />
    </>
  );
}

/** Soft neutral studio lighting. */
export function Lighting() {
  return (
    <>
      <ambientLight intensity={0.7} />
      <hemisphereLight args={['#8FA6BD', '#0B1622', 0.45]} />
      <directionalLight
        position={[9, 14, 7]}
        intensity={1.1}
        castShadow
        shadow-mapSize-width={2048}
        shadow-mapSize-height={2048}
        shadow-camera-left={-11}
        shadow-camera-right={11}
        shadow-camera-top={11}
        shadow-camera-bottom={-11}
        shadow-bias={-0.0005}
      />
      <directionalLight position={[-8, 6, -6]} intensity={0.25} />
    </>
  );
}
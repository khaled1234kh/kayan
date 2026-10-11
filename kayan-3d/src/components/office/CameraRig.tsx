import { useRef } from 'react';
import type { ElementRef } from 'react';
import { useFrame } from '@react-three/fiber';
import { OrbitControls, PerspectiveCamera } from '@react-three/drei';

/**
 * Camera rig.
 *
 * Three framing modes share one orbit camera:
 *
 *   orbit        free inspection — the default, unchanged from the foundation
 *                build, still the right tool for debugging
 *   presentation the reference-matching isometric shot used for stills
 *   interior     a low in-room shot that sits below the ceiling
 *
 * The two still presets are not arbitrary. Both were solved numerically rather
 * than eyeballed (`scripts/camera-search.mjs`): for each candidate eye/target
 * every required point — five desks, five monitors, the four LED-cross arms, the
 * glazing — was projected to NDC and rejected if any fell outside [-1, 1]. The
 * winning positions are the ones that frame the most points at the highest
 * usable pitch.
 *
 * Why `presentation` sits ABOVE the ceiling: the reference is an isometric view,
 * and pitch is bounded by atan(camY / horizontalDistance). The room is 3.4 high
 * and 12.8 across, so from anywhere inside it the steepest achievable look-down
 * is ~20 degrees. Measured, not assumed — the interior preset below tops out at
 * 20.4 degrees. Hitting the reference's 25-35 degree band requires a camera
 * above ROOM_H. That is not the old bug (the old `wide` preset was y = 8 with a
 * bad target and cropped the floor); it is what an isometric angle costs. The
 * ceiling is single-sided facing down, so it is culled from above and the
 * interior stays visible.
 */

export type CameraMode = 'orbit' | 'presentation' | 'interior';

export interface CameraPreset {
  /** Camera eye, world space. */
  position: [number, number, number];
  /** Orbit target, world space. */
  target: [number, number, number];
}

export const FOV = 42;
export const NEAR = 0.1;
export const FAR = 120;

/**
 * Solved presets. See the file header for how these were derived and why
 * `presentation` is above the ceiling.
 */
export const CAMERA_PRESETS: Record<CameraMode, CameraPreset> = {
  orbit: { position: [11, 11, 13], target: [0, 0.4, 0] },
  // pitch 33.0 deg, dist 13.96, all required points inside the frustum
  presentation: { position: [8, 8, 9], target: [0.5, 0.4, 0] },
  // pitch 20.4 deg — the steepest available from inside a 3.4-high room
  interior: { position: [-6, 2.4, 6], target: [-2, 0.3, 2] },
};

export function CameraRig({
  focusTarget,
  onFocusArrived,
  mode = 'orbit',
}: {
  focusTarget?: [number, number, number] | null;
  onFocusArrived?: () => void;
  mode?: CameraMode;
}) {
  const controls = useRef<ElementRef<typeof OrbitControls>>(null);
  const settled = useRef(false);
  const preset = CAMERA_PRESETS[mode] ?? CAMERA_PRESETS.orbit;

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
      <PerspectiveCamera
        makeDefault
        position={preset.position}
        fov={FOV}
        near={NEAR}
        far={FAR}
      />
      <OrbitControls
        ref={controls}
        makeDefault
        enableDamping
        dampingFactor={0.08}
        enablePan
        enableZoom
        enableRotate
        minDistance={0.5}
        maxDistance={34}
        minPolarAngle={0.18}
        maxPolarAngle={Math.PI * 0.46}
        target={preset.target}
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
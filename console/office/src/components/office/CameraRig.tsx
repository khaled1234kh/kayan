import { useLayoutEffect, useRef } from 'react';
import type { ElementRef } from 'react';
import { useFrame, useThree } from '@react-three/fiber';
import { OrbitControls, PerspectiveCamera } from '@react-three/drei';
import type { PerspectiveCamera as ThreeCamera } from 'three';
import { OVERVIEW_TARGET, overviewPosition } from './cameraFraming';

/** Orbit controls with viewport-aware framing and a resettable office overview. */

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
  // Position is fitted to the actual canvas aspect before the first frame.
  presentation: { position: [8, 8, 9], target: OVERVIEW_TARGET },
  // pitch 20.4 deg — the steepest available from inside a 3.4-high room
  interior: { position: [-6, 2.4, 6], target: [-2, 0.3, 2] },
};

export function CameraRig({
  focusTarget,
  onFocusArrived,
  mode = 'orbit',
  resetKey = 0,
}: {
  focusTarget?: [number, number, number] | null;
  onFocusArrived?: () => void;
  mode?: CameraMode;
  resetKey?: number;
}) {
  const controls = useRef<ElementRef<typeof OrbitControls>>(null);
  const camera = useRef<ThreeCamera>(null);
  const size = useThree((state) => state.size);
  const settled = useRef(false);
  const preset = CAMERA_PRESETS[mode] ?? CAMERA_PRESETS.orbit;

  useLayoutEffect(() => {
    const view = camera.current;
    const orbit = controls.current;
    if (!view || !orbit) return;
    view.position.fromArray(mode === 'presentation' ? overviewPosition(size.width / size.height) : preset.position);
    orbit.target.fromArray(preset.target);
    view.lookAt(orbit.target);
    orbit.update();
  }, [mode, preset, size.width, size.height, resetKey]);

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
        ref={camera}
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
        minDistance={3}
        maxDistance={55}
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

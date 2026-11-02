import { useRef } from 'react';
import { useFrame } from '@react-three/fiber';
import type { Mesh, PointLight } from 'three';
import { COLORS } from '../../data/layout';
import { beaconMaterial } from './materials';

/**
 * Attention beacon.
 *
 * A small red sphere floats just above the actor's head while they are waiting
 * on an approval or blocked, with a soft red point light beneath it. The pulse
 * is a slow, gentle breathe — never a blink — and it reuses the muted palette so
 * it accents the actor's state ring instead of competing with it.
 */

/** Height of the beacon above the figure's feet (head crown is at ~1.5). */
export const BEACON_Y = 1.6;

const BEACON_RADIUS = 0.06;
const PULSE_FREQ = 2.6;
const LIGHT_BASE = 0.4;
const LIGHT_RANGE = 1.5;

export function AttentionBeacon() {
  const mesh = useRef<Mesh>(null);
  const light = useRef<PointLight>(null);

  useFrame(({ clock }) => {
    const wave = 0.5 + 0.5 * Math.sin(clock.elapsedTime * PULSE_FREQ);
    if (mesh.current) mesh.current.scale.setScalar(1 + wave * 0.08);
    if (light.current) light.current.intensity = LIGHT_BASE + wave * 0.08;
  });

  return (
    <group position={[0, BEACON_Y, 0]}>
      <mesh ref={mesh} material={beaconMaterial(COLORS.red)}>
        <sphereGeometry args={[BEACON_RADIUS, 16, 12]} />
      </mesh>
      <pointLight ref={light} color={COLORS.red} intensity={LIGHT_BASE} distance={LIGHT_RANGE} decay={2} />
    </group>
  );
}
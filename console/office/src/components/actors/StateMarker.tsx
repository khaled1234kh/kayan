import { useRef } from 'react';
import { useFrame } from '@react-three/fiber';
import type { MeshBasicMaterial } from 'three';
import type { Actor } from '../../types';
import { COLORS, STATE_COLOR } from '../../data/layout';

/** A restrained floor marker; only actual working state animates. */
export function StateMarker({ actor }: { actor: Actor }) {
  const material = useRef<MeshBasicMaterial>(null);
  useFrame(({ clock }) => {
    if (material.current) material.current.opacity = actor.state === 'working'
      ? 0.45 + 0.2 * Math.sin(clock.elapsedTime * 2.4) : 0.35;
  });
  return <mesh position={[0, 0.02, -0.95]} rotation={[-Math.PI / 2, 0, 0]}>
    <ringGeometry args={[0.29, 0.32, 48]} />
    <meshBasicMaterial ref={material} color={STATE_COLOR[actor.state] ?? COLORS.muted}
      transparent opacity={0.35} depthWrite={false} toneMapped={false} />
  </mesh>;
}

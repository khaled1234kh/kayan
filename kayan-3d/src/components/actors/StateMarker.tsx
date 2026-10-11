import { useEffect, useRef, useState } from 'react';
import { useFrame } from '@react-three/fiber';
import { Html } from '@react-three/drei';
import type { Group, Mesh, MeshStandardMaterial } from 'three';
import type { Actor } from '../../types';
import { COLORS, STATE_COLOR } from '../../data/layout';
import { BODY, innerRingMaterial, outerRingMaterial } from './materials';

/**
 * State visualisation for one actor.
 *
 * - Outer ring: always present, always static.
 * - Inner ring: concentric with the outer, pulses only while state is 'working'.
 * - 'blocked' keeps its bar, 'awaiting_approval' its crossbar.
 * - An HTML chip fades in on every state change, holds 2s, then fades out, so
 *   state is unambiguous while orbiting.
 */
export function StateMarker({ actor }: { actor: Actor }) {
  const accent = STATE_COLOR[actor.state] ?? COLORS.muted;
  const inner = useRef<Mesh>(null);
  const floating = useRef<Group>(null);
  const [chipOn, setChipOn] = useState(false);

  // Fade in on mount and on every state transition; hold, then fade out.
  useEffect(() => {
    setChipOn(true);
    const t = window.setTimeout(() => setChipOn(false), 2000);
    return () => window.clearTimeout(t);
  }, [actor.state]);

  // Inner ring breathes only while working. Everything else stays still.
  useFrame(({ clock }) => {
    if (inner.current) {
      const active = actor.state === 'working';
      const s = active ? 1 + Math.sin(clock.elapsedTime * 2.4) * 0.07 : 1;
      inner.current.scale.setScalar(s);
      const m = inner.current.material as MeshStandardMaterial;
      m.opacity = active ? 0.55 + 0.35 * (0.5 + 0.5 * Math.sin(clock.elapsedTime * 2.4)) : 0.55;
      m.emissiveIntensity = active ? 1.25 : 0.8;
    }
    if (floating.current) {
      floating.current.position.y = BODY.ringY + Math.sin(clock.elapsedTime * 1.1) * 0.03;
    }
  });

  return (
    <>
      <group ref={floating} position={[0, BODY.ringY, 0]}>
        {/* ground-relative double ring */}
        <mesh rotation={[-Math.PI / 2, 0, 0]} material={outerRingMaterial(accent)}>
          <torusGeometry args={[0.22, 0.026, 10, 32]} />
        </mesh>
        <mesh ref={inner} rotation={[-Math.PI / 2, 0, 0]} material={innerRingMaterial(accent)}>
          <torusGeometry args={[0.185, 0.018, 10, 28]} />
        </mesh>

        {/* blocked indicator bar */}
        {actor.state === 'blocked' && (
          <mesh position={[0, 0.28, 0]}>
            <boxGeometry args={[0.26, 0.05, 0.05]} />
            <meshBasicMaterial color={COLORS.red} />
          </mesh>
        )}
        {/* awaiting approval crossbar */}
        {actor.state === 'awaiting_approval' && (
          <mesh position={[0, 0.28, 0]}>
            <boxGeometry args={[0.05, 0.05, 0.26]} />
            <meshBasicMaterial color={COLORS.orange} />
          </mesh>
        )}

        {/* HTML chip, 0.4 units above the ring */}
        <Html position={[0, 0.4, 0]} center zIndexRange={[8, 0]} style={{ pointerEvents: 'none' }}>
          <span className={`status-chip${chipOn ? ' is-visible' : ''}`} data-state={actor.state}>
            {actor.state.replace('_', ' ')}
          </span>
        </Html>
      </group>
    </>
  );
}
import { useMemo, useRef } from 'react';
import { useFrame } from '@react-three/fiber';
import type { Group } from 'three';
import type { AgentMessage } from '../../agents/agentMessages';
import { SEED_ACTORS } from '../../data/actors';
import { tileToWorld } from '../office/Office';
import { COLORS } from '../../data/layout';

/**
 * Communication visualization.
 *
 * A short-lived beam is drawn between two desks only while a message between
 * them is being delivered. It is driven exclusively by real `AgentMessage`
 * objects from the event stream — no connection is ever invented — and it fades
 * out, so the floor never accumulates permanent spaghetti.
 */

const BEAM_LIFETIME_MS = 1600;
/** Height of the beam above the floor, in world units. */
const BEAM_Y = 1.9;

const POSITION: Record<string, [number, number]> = {};
SEED_ACTORS.forEach((a) => {
  POSITION[a.id] = tileToWorld(a.gridPosition.x, a.gridPosition.z);
});

/** Most recent messages, newest first (the store keeps that order). */
function useActiveBeams(messages: AgentMessage[], now: number) {
  return useMemo(() => {
    const seen = new Set<string>();
    const out: Array<{ from: [number, number]; to: [number, number]; born: number }> = [];
    for (const m of messages) {
      const age = now - m.timestamp;
      if (age > BEAM_LIFETIME_MS) break; // messages are newest-first
      const key = `${m.fromAgentId}->${m.toAgentId}`;
      if (seen.has(key)) continue;
      const from = POSITION[m.fromAgentId];
      const to = POSITION[m.toAgentId];
      if (!from || !to) continue;
      seen.add(key);
      out.push({ from, to, born: m.timestamp });
    }
    return out;
  }, [messages, now]);
}

function Beam({ from, to, born }: { from: [number, number]; to: [number, number]; born: number }) {
  const group = useRef<Group>(null);

  useFrame(() => {
    if (!group.current) return;
    const age = Date.now() - born;
    const t = Math.min(1, Math.max(0, age / BEAM_LIFETIME_MS));
    // Fade in fast, then out.
    const opacity = t < 0.15 ? t / 0.15 : 1 - (t - 0.15) / 0.85;
    group.current.visible = opacity > 0.02;
    group.current.traverse((child) => {
      const mesh = child as unknown as { material?: { opacity: number } };
      if (mesh.material) mesh.material.opacity = Math.max(0, opacity) * 0.5;
    });
  });

  const dx = to[0] - from[0];
  const dz = to[1] - from[1];
  const len = Math.hypot(dx, dz);
  const angle = Math.atan2(dx, dz);
  const midX = (from[0] + to[0]) / 2;
  const midZ = (from[1] + to[1]) / 2;

  return (
    <group ref={group}>
      {/* Thin line between desks */}
      <mesh position={[midX, BEAM_Y, midZ]} rotation={[-Math.PI / 2, 0, -angle]}>
        <planeGeometry args={[0.05, len]} />
        <meshBasicMaterial color={COLORS.teal} transparent opacity={0.4} depthWrite={false} />
      </mesh>
      {/* Travelling marker at the midpoint */}
      <mesh position={[midX, BEAM_Y, midZ]}>
        <sphereGeometry args={[0.07, 10, 8]} />
        <meshBasicMaterial color={COLORS.teal} transparent opacity={0.6} depthWrite={false} />
      </mesh>
    </group>
  );
}

export function HandoffBeams({ messages }: { messages: AgentMessage[] }) {
  const beams = useActiveBeams(messages, Date.now());
  return (
    <>
      {beams.map((b, i) => (
        <Beam key={`${b.from[0]}-${b.from[1]}-${b.born}-${i}`} from={b.from} to={b.to} born={b.born} />
      ))}
    </>
  );
}
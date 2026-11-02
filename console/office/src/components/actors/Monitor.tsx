import { COLORS, DESK_TOP_Y } from '../../data/layout';
import { MONITOR } from './monitorGeometry';
import { LiveMonitorScreen } from './LiveMonitorScreen';
import type { Actor } from '../../types';

/** A single opaque monitor, with its live display facing the seated worker. */
export function Monitor({ actor }: { actor: Actor }) {
  const baseHeight = 0.018;
  const neckHeight = 0.2;
  return <group position={[0, 0, MONITOR.baseZ]}>
    <mesh position={[0, DESK_TOP_Y + baseHeight / 2, 0]} castShadow receiveShadow>
      <boxGeometry args={[0.26, baseHeight, 0.19]} />
      <meshStandardMaterial color={COLORS.monitorBezel} roughness={0.6} metalness={0.3} />
    </mesh>
    {/* Rear-mounted support: the neck must not intersect the worker-facing display. */}
    <mesh position={[0, DESK_TOP_Y + baseHeight + neckHeight / 2, 0.06]} castShadow>
      <boxGeometry args={[0.07, neckHeight, 0.05]} />
      <meshStandardMaterial color={COLORS.monitorBezel} roughness={0.55} metalness={0.35} />
    </mesh>
    <group position={[0, DESK_TOP_Y + baseHeight + neckHeight + 0.06, 0.01]} rotation={[MONITOR.tilt, 0, 0]}>
      <mesh name="monitor-casing" castShadow>
        <boxGeometry args={[MONITOR.width, MONITOR.height, MONITOR.depth]} />
        <meshStandardMaterial color={COLORS.monitorBezel} roughness={0.5} metalness={0.25} />
      </mesh>
      {/* Plane normals start at +Z. Rotate once to put the display on -Z. */}
      <group position={[0, 0, -(MONITOR.depth / 2 + 0.0005)]} rotation={[0, Math.PI, 0]}>
        <LiveMonitorScreen actor={actor} />
      </group>
      {/* Restrained rear ventilation; no duplicate or mirrored display. */}
      {[-0.1, -0.05, 0, 0.05, 0.1].map(x => <mesh key={x} position={[x, -0.08, MONITOR.depth/2 + 0.0005]}>
        <boxGeometry args={[0.025, 0.035, 0.001]} />
        <meshStandardMaterial color="#20272D" roughness={0.9} />
      </mesh>)}
    </group>
  </group>;
}
export default Monitor;

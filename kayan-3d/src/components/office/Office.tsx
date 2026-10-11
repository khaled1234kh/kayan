import { Grid } from '@react-three/drei';
import { COLORS, GRID, ZONES } from '../../data/layout';

/** Tile coordinate → world XZ, floor centred on the origin. */
export function tileToWorld(x: number, z: number): [number, number] {
  return [x - GRID / 2, z - GRID / 2];
}

/** Base floor slab. */
export function Floor() {
  return (
    <mesh rotation-x={-Math.PI / 2} receiveShadow>
      <planeGeometry args={[GRID + 0.8, GRID + 0.8]} />
      <meshStandardMaterial color={COLORS.floor} roughness={0.95} metalness={0.05} />
    </mesh>
  );
}

/** Faint tile grid so the floor reads as a measured space, not a plain plane. */
export function FloorGrid() {
  return (
    <Grid
      position={[0, 0.008, 0]}
      args={[GRID, GRID]}
      cellSize={1}
      cellThickness={0.4}
      cellColor="#1B3049"
      sectionSize={4}
      sectionThickness={0.7}
      sectionColor="#22405E"
      fadeDistance={40}
      infiniteGrid={false}
    />
  );
}

/** Zone floors, one subtle tint per room. */
export function Zones() {
  return (
    <>
      {ZONES.map((zone) => {
        const w = zone.x1 - zone.x0 + 1;
        const d = zone.z1 - zone.z0 + 1;
        const cx = (zone.x0 + zone.x1 + 1) / 2;
        const cz = (zone.z0 + zone.z1 + 1) / 2;
        const [wx, wz] = tileToWorld(cx, cz);
        return (
          <mesh key={zone.id} position={[wx, 0.012, wz]} rotation-x={-Math.PI / 2} receiveShadow>
            <planeGeometry args={[w, d]} />
            <meshStandardMaterial
              color={zone.tint}
              roughness={0.95}
              metalness={0.02}
              polygonOffset
              polygonOffsetFactor={-1}
            />
          </mesh>
        );
      })}
    </>
  );
}

/** Perimeter walls, 1.5 units high, with an entrance gap on the reception side. */
export function Walls() {
  const h = 1.5;
  const t = 0.35;
  const half = GRID / 2 + 0.1;
  const material = <meshStandardMaterial color={COLORS.wall} roughness={0.9} metalness={0.05} />;
  return (
    <group>
      {/* back wall */}
      <mesh position={[0, h / 2, -half]} castShadow receiveShadow>
        <boxGeometry args={[GRID + 0.6, h, t]} />
        {material}
      </mesh>
      {/* front wall, split around the entrance gap at x 4..6 */}
      <mesh position={[-3.5, h / 2, half]} castShadow receiveShadow>
        <boxGeometry args={[5, h, t]} />
        <meshStandardMaterial color={COLORS.wall} roughness={0.9} metalness={0.05} />
      </mesh>
      <mesh position={[3.25, h / 2, half]} castShadow receiveShadow>
        <boxGeometry args={[5.5, h, t]} />
        <meshStandardMaterial color={COLORS.wall} roughness={0.9} metalness={0.05} />
      </mesh>
      {/* side walls */}
      <mesh position={[-half, h / 2, 0]} castShadow receiveShadow>
        <boxGeometry args={[t, h, GRID + 0.6]} />
        <meshStandardMaterial color={COLORS.wall} roughness={0.9} metalness={0.05} />
      </mesh>
      <mesh position={[half, h / 2, 0]} castShadow receiveShadow>
        <boxGeometry args={[t, h, GRID + 0.6]} />
        <meshStandardMaterial color={COLORS.wall} roughness={0.9} metalness={0.05} />
      </mesh>
    </group>
  );
}

/** Meeting table in the meeting room, offset south so it never overlaps a desk. */
export function MeetingTable() {
  const legs: Array<[number, number]> = [
    [-1.3, -0.6],
    [1.3, -0.6],
    [-1.3, 0.6],
    [1.3, 0.6],
  ];
  return (
    <group position={[0, 0, 0.75]}>
      <mesh position={[0, 0.72, 0]} castShadow receiveShadow>
        <boxGeometry args={[3, 0.14, 1.5]} />
        <meshStandardMaterial color={COLORS.deskTop} roughness={0.85} metalness={0.05} />
      </mesh>
      {legs.map(([lx, lz], i) => (
        <mesh key={i} position={[lx, 0.36, lz]} castShadow>
          <boxGeometry args={[0.1, 0.72, 0.1]} />
          <meshStandardMaterial color={COLORS.deskSide} roughness={0.9} metalness={0.05} />
        </mesh>
      ))}
    </group>
  );
}

/** TrustGate rack. Visual marker only — enforcement is a later task. */
export function TrustGateRack({ alerting }: { alerting: boolean }) {
  return (
    <group position={[-3, 0, 3]}>
      <mesh position={[0, 1, 0]} castShadow receiveShadow>
        <boxGeometry args={[1, 2, 0.5]} />
        <meshStandardMaterial color={COLORS.deskSide} roughness={0.8} metalness={0.1} />
      </mesh>
      <mesh position={[0, 1, 0.27]}>
        <boxGeometry args={[0.06, 1.5, 0.02]} />
        <meshStandardMaterial
          color="#06202B"
          emissive={alerting ? COLORS.red : COLORS.teal}
          emissiveIntensity={alerting ? 2.2 : 1.1}
          roughness={0.5}
        />
      </mesh>
    </group>
  );
}
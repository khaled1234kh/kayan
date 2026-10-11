import { useMemo } from 'react';
import { Grid } from '@react-three/drei';
import * as THREE from 'three';
import { COLORS, GRID, ROOM_D, ROOM_H, ROOM_W, ZONES } from '../../data/layout';

/**
 * Office room shell.
 *
 * Rebuilt against the reference: an open, tall space rather than a low-walled
 * box. There is no back wall and no front wall — the far side is floor-to-ceiling
 * glazing onto a night city, and the near side is left open so the camera looks
 * in. Only the two side walls remain, full height, to frame the volume without
 * boxing it in. The ceiling is solid at ROOM_H; the reference implies a high
 * ceiling without showing it.
 */

/** Tile coordinate → world XZ, floor centred on the origin. */
export function tileToWorld(x: number, z: number): [number, number] {
  return [x - GRID / 2, z - GRID / 2];
}

/** Dark polished concrete. Low roughness gives the sheen the reference has. */
export function Floor() {
  return (
    <mesh rotation-x={-Math.PI / 2} receiveShadow>
      <planeGeometry args={[ROOM_W, ROOM_D]} />
      <meshStandardMaterial color={COLORS.floor} roughness={0.35} metalness={0.05} />
    </mesh>
  );
}

/** Faint tile grid so the floor reads as a measured space, not a void. */
export function FloorGrid() {
  return (
    <Grid
      position={[0, 0.008, 0]}
      args={[ROOM_W - 0.4, ROOM_D - 0.4]}
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

/**
 * Night-city backdrop, generated procedurally onto a canvas.
 *
 * No image asset is loaded — the reference needs a plausible city at a glance,
 * not a photo. Seeded so the skyline is identical on every render, otherwise
 * the office would shimmer between screenshots.
 */
function createCityTexture(): THREE.CanvasTexture {
  const W = 1024;
  const H = 512;
  const canvas = document.createElement('canvas');
  canvas.width = W;
  canvas.height = H;
  const ctx = canvas.getContext('2d');
  if (!ctx) return new THREE.CanvasTexture(canvas);

  let seed = 0x5eed;
  const rnd = () => {
    seed = (seed * 1664525 + 1013904223) % 4294967296;
    return seed / 4294967296;
  };

  // Sky: deep blue-black down to a warmer haze at the horizon.
  const sky = ctx.createLinearGradient(0, 0, 0, H);
  sky.addColorStop(0, '#05070C');
  sky.addColorStop(0.5, '#0A1220');
  sky.addColorStop(0.62, '#1B2B44');
  sky.addColorStop(0.64, '#0A0E14');
  sky.addColorStop(1, '#06080C');
  ctx.fillStyle = sky;
  ctx.fillRect(0, 0, W, H);

  const horizon = H * 0.64;

  // Two depth layers of towers, far (hazy) then near (darker).
  const layers = [
    { count: 46, wMin: 14, wMax: 42, hMin: 40, hMax: 150, body: '#0B1220', lit: 0.34, win: '#FFD79A' },
    { count: 30, wMin: 26, wMax: 74, hMin: 70, hMax: 250, body: '#060A12', lit: 0.5, win: '#FFC46B' },
  ];

  for (const layer of layers) {
    for (let i = 0; i < layer.count; i++) {
      const bw = layer.wMin + rnd() * (layer.wMax - layer.wMin);
      const bx = rnd() * (W - bw);
      const bh = layer.hMin + rnd() * (layer.hMax - layer.hMin);
      const by = horizon - bh;

      ctx.fillStyle = layer.body;
      ctx.fillRect(bx, by, bw, bh);

      // Window grid. Each window gets an independent lit/unlit roll so the
      // towers read as inhabited rather than uniformly striped.
      const cw = 3;
      const ch = 4;
      const gap = 4;
      for (let wy = by + 6; wy < horizon - 4; wy += ch + gap) {
        for (let wx = bx + 4; wx < bx + bw - 4; wx += cw + gap) {
          if (rnd() > layer.lit) continue;
          ctx.fillStyle = rnd() > 0.82 ? '#FFF3D6' : layer.win;
          ctx.fillRect(wx, wy, cw, ch);
        }
      }
    }
  }

  // Water: a horizon band carrying smeared reflections of the city lights.
  const water = ctx.createLinearGradient(0, horizon, 0, H);
  water.addColorStop(0, '#0C1522');
  water.addColorStop(1, '#05070B');
  ctx.fillStyle = water;
  ctx.fillRect(0, horizon, W, H - horizon);

  for (let i = 0; i < 130; i++) {
    const rx = rnd() * W;
    const ry = horizon + rnd() * (H - horizon);
    const rh = 3 + rnd() * 16;
    ctx.globalAlpha = 0.05 + rnd() * 0.13;
    ctx.fillStyle = rnd() > 0.75 ? '#FFC46B' : '#7FD6E4';
    ctx.fillRect(rx, ry, 2 + rnd() * 7, rh);
  }
  ctx.globalAlpha = 1;

  const tex = new THREE.CanvasTexture(canvas);
  tex.colorSpace = THREE.SRGBColorSpace;
  return tex;
}

/**
 * Room shell: two dark side walls, a solid ceiling, and a floor-to-ceiling
 * glazing on the far side with the city behind it.
 */
export function Walls() {
  const city = useMemo(() => createCityTexture(), []);
  const halfW = ROOM_W / 2;
  const halfD = ROOM_D / 2;
  const t = 0.3;

  return (
    <group>
      {/* Side walls — the only solid walls in the shell. They run deeper than the
          floor so they enclose the city backdrop; otherwise the skyline shows
          past their rear edge on an angled camera. */}
      <mesh position={[-halfW, ROOM_H / 2, -0.8]} castShadow receiveShadow>
        <boxGeometry args={[t, ROOM_H, ROOM_D + 3.2]} />
        <meshStandardMaterial color={COLORS.wall} roughness={0.92} metalness={0.04} />
      </mesh>
      <mesh position={[halfW, ROOM_H / 2, -0.8]} castShadow receiveShadow>
        <boxGeometry args={[t, ROOM_H, ROOM_D + 3.2]} />
        <meshStandardMaterial color={COLORS.wall} roughness={0.92} metalness={0.04} />
      </mesh>

      {/* Ceiling. */}
      <mesh position={[0, ROOM_H, 0]} rotation={[Math.PI / 2, 0, 0]} receiveShadow>
        <planeGeometry args={[ROOM_W, ROOM_D]} />
        <meshStandardMaterial color={COLORS.backgroundDark} roughness={0.98} metalness={0.02} />
      </mesh>

      {/* Night city, sitting behind the glazing on the far side. Sized to the
          glazing width so it never protrudes beyond the side walls. */}
      <mesh position={[0, ROOM_H / 2, -halfD - 1.1]}>
        <planeGeometry args={[ROOM_W + 1.2, ROOM_H + 1.0]} />
        <meshBasicMaterial map={city} toneMapped={false} />
      </mesh>

      {/* Floor-to-ceiling glazing. Cheap transparent standard material rather
          than `transmission`, which would cost a full extra render pass. */}
      <mesh position={[0, ROOM_H / 2, -halfD]}>
        <planeGeometry args={[ROOM_W, ROOM_H]} />
        <meshStandardMaterial
          color={COLORS.glass}
          transparent
          opacity={0.1}
          roughness={0.08}
          metalness={0.1}
          side={THREE.DoubleSide}
          depthWrite={false}
        />
      </mesh>

      {/* Mullions: dark vertical frames breaking up the glazing. */}
      {[-4, -2, 0, 2, 4].map((x) => (
        <mesh key={x} position={[x, ROOM_H / 2, -halfD + 0.06]}>
          <boxGeometry args={[0.09, ROOM_H, 0.09]} />
          <meshStandardMaterial color={COLORS.glassFrame} roughness={0.6} metalness={0.35} />
        </mesh>
      ))}
      <mesh position={[0, ROOM_H, -halfD + 0.06]}>
        <boxGeometry args={[ROOM_W, 0.12, 0.12]} />
        <meshStandardMaterial color={COLORS.glassFrame} roughness={0.6} metalness={0.35} />
      </mesh>
      <mesh position={[0, ROOM_H * 0.52, -halfD + 0.06]}>
        <boxGeometry args={[ROOM_W, 0.08, 0.08]} />
        <meshStandardMaterial color={COLORS.glassFrame} roughness={0.6} metalness={0.35} />
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
    /* Moved off the cross-aisle: this table used to sit at (0, 0.75) with a 3x1.5
       footprint, which straddled the x, z ∈ (-1.75, 1.75) square that has to stay
       empty for the floor LED path. It now sits against the back glazing on the
       right, clear of the cross-aisle, the back-right pod, and the task board
       (which occupies roughly x -3.1..0.1 at z -5.9). */
    <group position={[4, 0, -5.2]}>
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
    /* Was at (-3, 3), where its 1x0.5 footprint overlapped the front-left pod's
       desk (x -4.2..-2.8, z 3.05..3.95). Moved into the front-left corner, tucked
       against the side wall and clear of the sales desk and its glass. */
    <group position={[-5.9, 0, 5.9]}>
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
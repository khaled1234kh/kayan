import { useEffect, useMemo, useRef } from 'react';
import { useFrame } from '@react-three/fiber';
import { Grid } from '@react-three/drei';
import * as THREE from 'three';
import { createCityTexture } from './cityBackdrop';
import { COLORS, GRID, ROOM_D, ROOM_H, ROOM_W, ZONES } from '../../data/layout';

/**
 * Office room shell.
 *
 * Rebuilt against the reference: an open, tall space rather than a low-walled
 * box. There is no back wall and no front wall — the far side is floor-to-ceiling
 * glazing onto a night city, and the near side is left open so the camera looks
 * in. Only the two side walls remain, full height, to frame the volume without
 * boxing it in. This is an open-top cutaway so close-up cameras do not expose
 * the nearly black underside of a ceiling plane across the viewport.
 */

/** Tile coordinate → world XZ, floor centred on the origin. */
export function tileToWorld(x: number, z: number): [number, number] {
  return [x - GRID / 2, z - GRID / 2];
}

/** Matte concrete surface with a continuous structural slab edge. */
export function Floor() {
  return (
    <group><mesh position={[0,-0.09,0]} receiveShadow><boxGeometry args={[ROOM_W+0.3,0.18,ROOM_D+0.3]}/><meshStandardMaterial color="#29333C" roughness={0.92}/></mesh>
    <mesh rotation-x={-Math.PI / 2} receiveShadow>
      <planeGeometry args={[ROOM_W, ROOM_D]} />
      <meshStandardMaterial color={COLORS.floor} roughness={0.9} metalness={0.02} />
    </mesh></group>
  );
}

/** Faint tile grid so the floor reads as a measured space, not a void. */
export function FloorGrid() {
  return (
    <Grid
      position={[0, 0.008, 0]}
      args={[ROOM_W - 0.4, ROOM_D - 0.4]}
      cellSize={1}
      cellThickness={0.45}
      cellColor="#273A4A"
      sectionSize={4}
      sectionThickness={0.7}
      sectionColor="#334D60"
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

export const REAR_OPENING={width:ROOM_W-.3,height:ROOM_H-.16,z:-ROOM_D/2-.095};

/** Cut away only the camera-near side; retain a structural parapet and the far wall. */
export function wallUpperVisible(side:number,cameraX:number){return side*cameraX<=0.5;}
export function visibleWallRaycast(this:THREE.Mesh,ray:THREE.Raycaster,hits:THREE.Intersection[]){if(this.visible)THREE.Mesh.prototype.raycast.call(this,ray,hits);}
export function CutawayWall({side}:{side:-1|1}){
  const upper=useRef<THREE.Mesh>(null);
  useFrame(({camera})=>{if(upper.current)upper.current.visible=wallUpperVisible(side,camera.position.x);});
  return <group position={[side*ROOM_W/2,0,0]}>
    <mesh position={[0,.22,0]} castShadow receiveShadow><boxGeometry args={[.3,.44,ROOM_D+.3]}/><meshStandardMaterial color={COLORS.wall} roughness={.92}/></mesh>
    <mesh ref={upper} raycast={visibleWallRaycast} position={[0,(ROOM_H+.44)/2,0]} castShadow receiveShadow><boxGeometry args={[.3,ROOM_H-.44,ROOM_D+.3]}/><meshStandardMaterial color={COLORS.wall} roughness={.92}/></mesh>
  </group>;
}

/**
 * Room shell: two dark side walls, an open top, and floor-to-ceiling
 * glazing on the far side with the city behind it.
 */
export function Walls() {
  const city = useMemo(() => createCityTexture(), []);
  useEffect(()=>()=>city.dispose(),[city]);
  const halfD = ROOM_D / 2;

  return (
    <group>
      <CutawayWall side={-1}/><CutawayWall side={1}/>
      {/* The backdrop is contained INSIDE the rear opening, just behind glazing.
          Backing thickness closes its exterior face; no oversized floating card. */}
      <mesh position={[0,ROOM_H/2,-halfD-.14]}><boxGeometry args={[ROOM_W-.3,ROOM_H-.16,.08]}/><meshStandardMaterial color={COLORS.wall} roughness={.92}/></mesh>
      <mesh position={[0,ROOM_H/2,REAR_OPENING.z]}>
        <planeGeometry args={[REAR_OPENING.width,REAR_OPENING.height]}/><meshBasicMaterial map={city} toneMapped={false}/>
      </mesh>

      {/* Floor-to-ceiling glazing. Cheap transparent standard material rather
          than `transmission`, which would cost a full extra render pass. */}
      <mesh raycast={()=>null} position={[0, ROOM_H / 2, -halfD]}>
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
      {[-halfD, -4, -2, 0, 2, 4, halfD].map((x) => (
        <mesh key={x} position={[x, ROOM_H / 2, -halfD + 0.06]}>
          <boxGeometry args={[0.09, ROOM_H, 0.09]} />
          <meshStandardMaterial color={COLORS.glassFrame} roughness={0.6} metalness={0.35} />
        </mesh>
      ))}
      <mesh position={[0,.06,-halfD+.06]}><boxGeometry args={[ROOM_W,.12,.12]}/><meshStandardMaterial color={COLORS.glassFrame} roughness={.6}/></mesh>
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

/** Architectural rack marker; actual authorization lives in the Rust service. */
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

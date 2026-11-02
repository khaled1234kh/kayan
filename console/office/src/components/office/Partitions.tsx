import { useMemo } from 'react';
import * as THREE from 'three';
import { COLORS, PARTITION_HEIGHT } from '../../data/layout';

/**
 * Frosted-glass cubicle partitions.
 *
 * Arranged as four pods around a central cross-aisle, which is the layout the
 * reference uses: each workstation sits in a corner cell formed by two glass
 * walls, and the gaps between pods form the walkway the floor LED path later
 * traces (Phase F).
 *
 * The aisle is deliberately left open — partitions frame it, never block it.
 *
 * Seat mapping (world space, matching `data/actors.ts` via `tileToWorld`):
 *   front-left   (-3.5, +3.5)  sales       front-right  (+3.5, +3.5)  ceo
 *   back-left    (-3.5, -3.5)  employee    back-right   (+3.5, -3.5)  operations
 *   manager      ( 0.0, +4.5)  — unpartitioned, in the open front-centre
 *     pocket between the two x = ±POD panels, overlooking the pods.
 * Each actor sits 0.575 inboard of its pod's cell centre, toward the aisle,
 * which leaves the desk 1.05 clear of the inner X glass line and 1.30 clear of
 * the inner Z one. The cross-aisle square x, z ∈ (-POD, +POD) is intentionally
 * empty.
 */

/** Half the room footprint. Walls sit at ±this. */
const EDGE = 6.4;
/** Offset of each pod's inner glass line from the centre cross. */
const POD = 1.75;

type Axis = 'x' | 'z';
interface PanelSpec {
  /** Centre of the panel. */
  x: number;
  z: number;
  /** Run length along the panel's own axis. */
  length: number;
  /** 'x' = runs along X (a wall facing ±Z). 'z' = runs along Z. */
  axis: Axis;
}

/**
 * Eight panels: two per pod, on the pod's inner X and inner Z edges.
 * Panels that share a pod line are split by the aisle, so the centre stays open.
 */
const PANELS: PanelSpec[] = [
  { axis: 'x', x: -(EDGE + POD) / 2, z: -POD, length: EDGE - POD },
  { axis: 'x', x: (EDGE + POD) / 2, z: -POD, length: EDGE - POD },
  { axis: 'x', x: -(EDGE + POD) / 2, z: POD, length: EDGE - POD },
  { axis: 'x', x: (EDGE + POD) / 2, z: POD, length: EDGE - POD },
  { axis: 'z', x: -POD, z: -(EDGE + POD) / 2, length: EDGE - POD },
  { axis: 'z', x: POD, z: -(EDGE + POD) / 2, length: EDGE - POD },
  { axis: 'z', x: -POD, z: (EDGE + POD) / 2, length: EDGE - POD },
  { axis: 'z', x: POD, z: (EDGE + POD) / 2, length: EDGE - POD },
];

const FRAME = 0.05;
const LED_H = 0.035;

export function Partitions() {
  // One shared glass material and one shared frame material for all panels:
  // 8 panels x 5 meshes would otherwise be 40 materials.
  const glass = useMemo(
    () =>
      new THREE.MeshPhysicalMaterial({
        color: COLORS.glass,
        // Frosted: low transmission, high roughness, so it diffuses rather than
        // refracts. `transmission` proper would add a full extra render pass
        // per frame, which the software-GL still renderer cannot afford.
        transparent: true,
        opacity: 0.25,
        roughness: 0.55,
        metalness: 0.0,
        side: THREE.DoubleSide,
        depthWrite: false,
      }),
    [],
  );

  const frame = useMemo(
    () =>
      new THREE.MeshStandardMaterial({
        color: COLORS.glassFrame,
        roughness: 0.45,
        metalness: 0.6,
      }),
    [],
  );

  const led = useMemo(
    () =>
      new THREE.MeshStandardMaterial({
        color: COLORS.ledCool,
        emissive: COLORS.ledCool,
        emissiveIntensity: 2.4,
        roughness: 0.5,
        toneMapped: false,
      }),
    [],
  );

  return (
    <group>
      {PANELS.map((p, i) => {
        const h = PARTITION_HEIGHT;
        const cy = h / 2;
        // Glass dimensions along each local axis.
        const [glassW, glassD] = p.axis === 'x' ? [p.length, 0.02] : [0.02, p.length];
        const [railW, railD] = p.axis === 'x' ? [p.length, FRAME] : [FRAME, p.length];
        const [ledW, ledD] =
          p.axis === 'x' ? [p.length - 0.1, LED_H] : [LED_H, p.length - 0.1];

        return (
          <group key={i} position={[p.x, 0, p.z]}>
            {/* frosted panel */}
            <mesh position={[0, cy, 0]} material={glass}>
              <boxGeometry args={[glassW, h, glassD]} />
            </mesh>

            {/* top and bottom rails */}
            <mesh position={[0, h - FRAME / 2, 0]} material={frame}>
              <boxGeometry args={[railW, FRAME, railD]} />
            </mesh>
            <mesh position={[0, FRAME / 2, 0]} material={frame}>
              <boxGeometry args={[railW, FRAME, railD]} />
            </mesh>

            {/* vertical posts at each end */}
            {[-1, 1].map((end) => (
              <mesh
                key={end}
                position={p.axis === 'x' ? [(end * (p.length - FRAME)) / 2, cy, 0] : [0, cy, (end * (p.length - FRAME)) / 2]}
                material={frame}
              >
                <boxGeometry
                  args={p.axis === 'x' ? [FRAME, h, FRAME] : [FRAME, h, FRAME]}
                />
              </mesh>
            ))}

            {/* cyan LED at the base — the reference lights partition feet cyan
                and keeps warm orange for the desk undersides. */}
            <mesh position={[0, 0.035, 0]} material={led}>
              <boxGeometry args={[ledW, LED_H, ledD]} />
            </mesh>
          </group>
        );
      })}
    </group>
  );
}

export default Partitions;
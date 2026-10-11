import { useMemo } from 'react';
import * as THREE from 'three';

/**
 * Desk keyboard with real keys.
 *
 * The 70 keys are a single InstancedMesh, so the whole keyboard costs two draw
 * calls instead of seventy-one.
 */

const BASE_W = 0.45;
const BASE_D = 0.16;
const BASE_H = 0.02;
const ROWS = 5;
const COLS = 14;
const KEY = 0.026;
const GAP = 0.004;
const PITCH = KEY + GAP;

const keyMatrices = () => {
  const out: THREE.Matrix4[] = [];
  const m = new THREE.Matrix4();
  const startX = -((COLS - 1) * PITCH) / 2;
  const startZ = -((ROWS - 1) * PITCH) / 2;
  for (let r = 0; r < ROWS; r++) {
    for (let c = 0; c < COLS; c++) {
      out.push(
        m.clone().setPosition(
          startX + c * PITCH,
          BASE_H / 2 + KEY / 2,
          startZ + r * PITCH,
        ),
      );
    }
  }
  return out;
};

export function Keyboard() {
  const matrices = useMemo(() => keyMatrices(), []);

  const keyMaterial = useMemo(
    () =>
      new THREE.MeshStandardMaterial({
        color: '#3A4A55',
        roughness: 0.65,
        metalness: 0.05,
      }),
    [],
  );

  return (
    <group>
      <mesh position={[0, BASE_H / 2, 0]} castShadow receiveShadow>
        <boxGeometry args={[BASE_W, BASE_H, BASE_D]} />
        <meshStandardMaterial color="#1A2C45" roughness={0.75} metalness={0.05} />
      </mesh>

      <instancedMesh
        args={[undefined, undefined, ROWS * COLS]}
        ref={(mesh) => {
          if (!mesh) return;
          matrices.forEach((mat, i) => mesh.setMatrixAt(i, mat));
          mesh.instanceMatrix.needsUpdate = true;
        }}
        castShadow
        material={keyMaterial}
      >
        <boxGeometry args={[KEY, KEY / 2, KEY]} />
      </instancedMesh>
    </group>
  );
}

export default Keyboard;
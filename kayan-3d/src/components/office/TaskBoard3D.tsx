import { useLayoutEffect, useMemo, useRef } from 'react';
import * as THREE from 'three';
import { PlaneGeometry } from 'three';
import { useStore } from '../../state/useStore';
import type { CompanyTaskColumn } from '../../state/eventReducer';

/**
 * Wall-mounted task board inside the 3D office.
 *
 * It mirrors the live Kanban state — four columns with abstract card shapes —
 * without readable text: at the operating camera distance text turns to noise,
 * so a card is a coloured bar whose column and accent say everything the floor
 * needs to say (same constraint as the monitor screens).
 *
 * Draw-call budget: 1 backboard + 4 column panels + 1 instanced card mesh = 6.
 * Columns share one geometry; every card is one instance of a second shared
 * geometry, tinted per column via instance colours.
 */

/** Shared by the backboard and the four column panels. */
const PANEL_GEO = new PlaneGeometry(1, 1);
/** Shared by every card instance. */
const CARD_GEO = new PlaneGeometry(1, 1);

const BOARD_W = 4.6;
const BOARD_H = 1.06;
const COL_W = 1.02;
const COL_H = 0.88;
const COL_GAP = 0.09;
const CARD_H = 0.13;
const CARD_GAP = 0.045;
const CARD_PAD = 0.07;
const HEADER_H = 0.16;
const MAX_PER_COLUMN = 4;
const MAX_CARDS = MAX_PER_COLUMN * 4;

const COLUMNS: CompanyTaskColumn[] = ['todo', 'in_progress', 'blocked', 'done'];

/** Dark tints so the bright card bars read at a distance. */
const COLUMN_TINT: Record<CompanyTaskColumn, string> = {
  todo: '#1B3A52',
  in_progress: '#14343C',
  blocked: '#3D2C17',
  done: '#123332',
};

/** Card accent = the UI status language (muted / teal / orange / teal). */
const COLUMN_ACCENT: Record<CompanyTaskColumn, string> = {
  todo: '#8B9AAB',
  in_progress: '#1FB8C4',
  blocked: '#F5A623',
  done: '#1FB8C4',
};

const COLUMN_MATERIALS: Record<CompanyTaskColumn, THREE.MeshStandardMaterial> = {
  todo: new THREE.MeshStandardMaterial({ color: COLUMN_TINT.todo, roughness: 0.9 }),
  in_progress: new THREE.MeshStandardMaterial({ color: COLUMN_TINT.in_progress, roughness: 0.9 }),
  blocked: new THREE.MeshStandardMaterial({ color: COLUMN_TINT.blocked, roughness: 0.9 }),
  done: new THREE.MeshStandardMaterial({ color: COLUMN_TINT.done, roughness: 0.9 }),
};

const BOARD_MATERIAL = new THREE.MeshStandardMaterial({ color: '#0C1A26', roughness: 0.85 });

/** Deterministic pseudo-width so cards feel like varied content, not a grid. */
function cardWidth(taskId: string): number {
  let hash = 0;
  for (let i = 0; i < taskId.length; i += 1) {
    hash = (hash * 31 + taskId.charCodeAt(i)) % 997;
  }
  return COL_W - CARD_PAD * 2 - (hash % 3) * 0.07;
}

const TOTAL_COLS_W = COLUMNS.length * COL_W + (COLUMNS.length - 1) * COL_GAP;
const colCenterX = (index: number): number =>
  -TOTAL_COLS_W / 2 + COL_W / 2 + index * (COL_W + COL_GAP);
const cardY = (row: number): number => COL_H / 2 - HEADER_H - CARD_H / 2 - row * (CARD_H + CARD_GAP);

export function TaskBoard3D() {
  const companyTasks = useStore((s) => s.companyTasks);
  const meshRef = useRef<THREE.InstancedMesh>(null!);
  const scratch = useMemo(
    () => ({ matrix: new THREE.Matrix4(), color: new THREE.Color() }),
    [],
  );

  const cards = useMemo(
    () =>
      COLUMNS.flatMap((column) =>
        companyTasks
          .filter((t) => t.column === column)
          .sort((a, b) => a.id.localeCompare(b.id))
          .slice(0, MAX_PER_COLUMN)
          .map((t, row) => ({ column, id: t.id, row })),
      ),
    [companyTasks],
  );

  useLayoutEffect(() => {
    const mesh = meshRef.current;
    if (!mesh) return;
    cards.forEach((card, i) => {
      const w = cardWidth(card.id);
      const x = colCenterX(COLUMNS.indexOf(card.column)) - COL_W / 2 + CARD_PAD + w / 2;
      scratch.matrix.makeTranslation(x, cardY(card.row), 0.012);
      // Non-uniform scale on the shared unit plane: width varies, height fixed.
      scratch.matrix.scale(new THREE.Vector3(w, CARD_H, 1));
      mesh.setMatrixAt(i, scratch.matrix);
      mesh.setColorAt(i, scratch.color.set(COLUMN_ACCENT[card.column]));
    });
    mesh.count = cards.length;
    mesh.instanceMatrix.needsUpdate = true;
    if (mesh.instanceColor) mesh.instanceColor.needsUpdate = true;
  }, [cards, scratch]);

  return (
    <group position={[-1.5, 0.98, -5.9]}>
      {/* backboard */}
      <mesh geometry={PANEL_GEO} material={BOARD_MATERIAL} scale={[BOARD_W, BOARD_H, 1]} />
      {/* one panel per column, sharing the geometry */}
      {COLUMNS.map((column, i) => (
        <mesh
          key={column}
          geometry={PANEL_GEO}
          material={COLUMN_MATERIALS[column]}
          position={[colCenterX(i), -0.03, 0.006]}
          scale={[COL_W, COL_H, 1]}
        />
      ))}
      {/* every visible card: a single instanced draw call */}
      <instancedMesh ref={meshRef} args={[CARD_GEO, undefined, MAX_CARDS]} frustumCulled={false}>
        <meshBasicMaterial toneMapped={false} />
      </instancedMesh>
    </group>
  );
}

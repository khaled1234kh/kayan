import { PlaneGeometry } from 'three';
import type { Material } from 'three';
import { LOOKS, SCREEN, screenAccentMaterial, type ActorRole } from './materials';

/**
 * Monitor face.
 *
 * The screen carries abstract UI shapes only — a task graph, an inventory grid,
 * or a quotation table. Nothing is spelled out: bars, cells and connectors,
 * never glyphs. That is a deliberate constraint, not an omission; real text at
 * the operating camera distance (15–25 units) turns to noise, and the screen's
 * job is to say "this agent is looking at structure", not to be legible.
 *
 * Layouts are fixed per role and fully deterministic, so a desk looks identical
 * across reloads and can be compared between agents.
 *
 * `screenShapes` is pure data, deliberately: the renderer only maps it to
 * meshes, so the layout can also be rasterised offline and checked for
 * overflow and overlap without a browser.
 */

const PANEL = new PlaneGeometry(1, 1);

/** Panel size in world units, inside the monitor's 0.66 x 0.42 bezel. */
export const SCREEN_W = 0.56;
export const SCREEN_H = 0.33;
/** Height of the window title bar, shared by all three layouts. */
const TITLE_H = 0.022;

/**
 * Painter's layers. Content within a layer never overlaps in the panel plane,
 * so a flat stack of three depths is enough — no per-shape z bookkeeping and
 * no coplanar z-fighting.
 */
const LAYER_BG = 0.001;
const LAYER_ROW = 0.002;
const LAYER_INK = 0.003;

export type ScreenLayout = 'graph' | 'grid' | 'table';

/**
 * Which view each role works in. The manager plans (graph), sales quotes
 * (table), operations counts stock (grid); the two humans mirror the view of
 * the AI role they sit beside.
 */
export const SCREEN_LAYOUT: Record<ActorRole, ScreenLayout> = {
  ceo: 'table',
  human: 'grid',
  'ai-manager': 'graph',
  'ai-sales': 'table',
  'ai-ops': 'grid',
};

export interface ScreenShape {
  /** Centre, in panel-local units: x right, y up, origin at the panel centre. */
  x: number;
  y: number;
  w: number;
  h: number;
  /** Rotation about the panel normal, radians. Zero for everything but edges. */
  angle: number;
  layer: number;
  material: Material;
}

const bar = (
  x: number,
  y: number,
  w: number,
  h: number,
  material: Material,
  layer: number,
  angle = 0,
): ScreenShape => ({ x, y, w, h, angle, layer, material });

/** Window title bar: accent tab, title block, then empty chrome. */
function titleBar(accent: Material): ScreenShape[] {
  const y = SCREEN_H / 2 - TITLE_H / 2 - 0.006;
  return [
    bar(0, y, SCREEN_W - 0.02, TITLE_H, SCREEN.chrome, LAYER_BG),
    bar(-SCREEN_W / 2 + 0.045, y, 0.05, 0.012, accent, LAYER_INK),
    bar(-SCREEN_W / 2 + 0.115, y, 0.085, 0.012, SCREEN.ink, LAYER_INK),
  ];
}

/** A connector between two nodes, as a rotated bar of the right length. */
function edge(ax: number, ay: number, bx: number, by: number, material: Material): ScreenShape {
  return bar(
    (ax + bx) / 2,
    (ay + by) / 2,
    Math.hypot(bx - ax, by - ay),
    0.007,
    material,
    LAYER_ROW,
    Math.atan2(by - ay, bx - ax),
  );
}

/** Task graph — a queue strip down the left, then a dependency tree. */
const GRAPH_NODES: Array<[number, number]> = [
  [-0.175, 0.055],
  [-0.04, 0.095],
  [-0.04, -0.015],
  [0.095, 0.055],
  [0.095, -0.065],
  [0.205, 0.0],
];
const GRAPH_EDGES: Array<[number, number]> = [
  [0, 1],
  [0, 2],
  [1, 3],
  [2, 3],
  [2, 4],
  [3, 5],
  [4, 5],
];
/** The two nodes downstream of the fan-out carry the role accent. */
const GRAPH_LIVE = [4, 5];

function graph(accent: Material): ScreenShape[] {
  const shapes: ScreenShape[] = [...titleBar(accent)];
  shapes.push(bar(-0.235, 0.05, 0.048, 0.13, SCREEN.inkDim, LAYER_BG));
  [0.108, 0.05, -0.008].forEach((y, i) => {
    shapes.push(bar(-0.235, y, 0.034, 0.026, i === 0 ? accent : SCREEN.ink, i === 0 ? LAYER_INK : LAYER_ROW));
  });
  for (const [a, b] of GRAPH_EDGES) {
    const [ax, ay] = GRAPH_NODES[a];
    const [bx, by] = GRAPH_NODES[b];
    shapes.push(edge(ax, ay, bx, by, SCREEN.ink));
  }
  GRAPH_NODES.forEach(([x, y], i) => {
    shapes.push(bar(x, y, 0.038, 0.038, GRAPH_LIVE.includes(i) ? accent : SCREEN.ink, LAYER_INK));
  });
  return shapes;
}

/** Inventory grid — rows of stock cells, some filled, most empty. */
const GRID_ROWS = 4;
const GRID_COLS = 6;
const GRID_PITCH = 0.066;
const GRID_CELL = 0.05;
/** 1 = occupied. Fixed, so a shelf never shimmers between frames. */
const GRID_FILL = [1, 0, 1, 1, 0, 0, 0, 1, 0, 1, 0, 0, 1, 1, 0, 0, 1, 0, 0, 1, 0, 1, 0, 0];

function inventoryGrid(accent: Material): ScreenShape[] {
  const shapes: ScreenShape[] = [...titleBar(accent)];
  const x0 = -((GRID_COLS - 1) * GRID_PITCH) / 2;
  const y0 = ((GRID_ROWS - 1) * GRID_PITCH) / 2 - 0.012;
  for (let r = 0; r < GRID_ROWS; r += 1) {
    const y = y0 - r * GRID_PITCH;
    shapes.push(bar(0, y - GRID_CELL * 0.62, GRID_COLS * GRID_PITCH, 0.004, SCREEN.inkDim, LAYER_ROW));
    for (let c = 0; c < GRID_COLS; c += 1) {
      const i = r * GRID_COLS + c;
      shapes.push(
        bar(
          x0 + c * GRID_PITCH,
          y,
          GRID_CELL,
          GRID_CELL * 0.7,
          GRID_FILL[i] === 1 ? accent : SCREEN.inkDim,
          GRID_FILL[i] === 1 ? LAYER_INK : LAYER_ROW,
        ),
      );
    }
  }
  return shapes;
}

/** Quotation table — column headings, five line items, a footer total. */
/** Column centres. Kept in one array so headings and rows can never drift. */
const QUOTE_COLS = { qty: -0.15, unit: 0.03, total: 0.19 } as const;
const QUOTE_HEADINGS: Array<[number, number, boolean]> = [
  [QUOTE_COLS.qty, 0.13, false],
  [QUOTE_COLS.unit, 0.11, false],
  [QUOTE_COLS.total, 0.09, true],
];
/** [quantity, unit price, line total] widths, as abstract bars. */
const QUOTE_ITEMS: Array<[number, number, number]> = [
  [0.2, 0.16, 0.09],
  [0.14, 0.22, 0.13],
  [0.24, 0.1, 0.07],
  [0.17, 0.18, 0.11],
  [0.11, 0.13, 0.08],
];

function quotationTable(accent: Material): ScreenShape[] {
  const shapes: ScreenShape[] = [...titleBar(accent)];
  for (const [x, w, hot] of QUOTE_HEADINGS) {
    shapes.push(bar(x, 0.112, w, 0.016, hot ? accent : SCREEN.ink, hot ? LAYER_INK : LAYER_ROW));
  }
  shapes.push(bar(0, 0.088, SCREEN_W - 0.02, 0.004, SCREEN.inkDim, LAYER_ROW));
  QUOTE_ITEMS.forEach(([qty, unit, total], i) => {
    const y = 0.058 - i * 0.036;
    shapes.push(bar(-0.245, y, 0.014, 0.016, SCREEN.inkDim, LAYER_ROW));
    shapes.push(bar(QUOTE_COLS.qty, y, qty, 0.012, SCREEN.ink, LAYER_ROW));
    shapes.push(bar(QUOTE_COLS.unit, y, unit, 0.012, SCREEN.ink, LAYER_ROW));
    shapes.push(bar(QUOTE_COLS.total, y, total, 0.012, accent, LAYER_INK));
  });
  shapes.push(bar(0, -0.13, SCREEN_W - 0.02, 0.004, SCREEN.inkDim, LAYER_ROW));
  shapes.push(bar(QUOTE_COLS.total, -0.118, 0.14, 0.014, accent, LAYER_INK));
  return shapes;
}

/** Builds the shape list for a layout. Pure — no React, no scene. */
export function screenShapes(layout: ScreenLayout, accent: string): ScreenShape[] {
  const accentMat = screenAccentMaterial(accent);
  if (layout === 'graph') return graph(accentMat);
  if (layout === 'grid') return inventoryGrid(accentMat);
  return quotationTable(accentMat);
}

/**
 * Renders the panel and its shapes at the origin of its parent, facing +Z.
 * `layout` defaults to the role's own view, so callers only pass a role.
 */
export function MonitorScreen({
  role,
  layout,
}: {
  role: ActorRole;
  layout?: ScreenLayout;
}) {
  const shapes = screenShapes(layout ?? SCREEN_LAYOUT[role], LOOKS[role].accent);
  return (
    <group>
      <mesh geometry={PANEL} material={SCREEN.glass} scale={[SCREEN_W, SCREEN_H, 1]} />
      {shapes.map((s, i) => (
        <mesh
          key={i}
          geometry={PANEL}
          material={s.material}
          position={[s.x, s.y, s.layer]}
          rotation={[0, 0, s.angle]}
          scale={[s.w, s.h, 1]}
        />
      ))}
    </group>
  );
}
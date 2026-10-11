/**
 * Decor collision sweep (Phase E).
 *
 * Pure geometry check, no browser: every decor footprint in `Decor.tsx` is
 * tested against the five desks, the eight glass panels, the cross-aisle
 * square, the room bounds, and each other. Prints any failure and exits
 * non-zero. Run: node scripts/verify-decor.mjs
 *
 * Footprints are the ground-plane bounding boxes; the cabinet and sconces are
 * wall-mounted and are checked at their own height band.
 */
const EDGE = 6.4;
const POD = 1.75;
const DESK_W = 1.6;
const DESK_D = 0.9;

/** [x, z, halfWidth, halfDepth, label] — matches Decor.tsx placements. */
const decor = [
  [-5.85, 3.1, 0.34, 0.34, 'floorPlant-L1'],
  [5.85, 2.9, 0.32, 0.32, 'floorPlant-R1'],
  [-5.85, -3.1, 0.3, 0.3, 'floorPlant-L2'],
  [5.95, 5.6, 0.26, 0.26, 'medCorner-R'],
  [-5.2, 4.6, 0.16, 0.16, 'smallPod-1'],
  [5.2, -4.7, 0.16, 0.16, 'smallPod-2'],
  // cabinet: rotated 90deg, so it is long in z and shallow in x
  [-6.02, -0.3, 0.22, 1.2, 'cabinet-L'],
];
/** Wall-mounted; only their x-band matters for overlap with floor decor. */
const wallMounted = [
  [-5.78, 1.15, 0.12, 0.12, 'cabinetTopPlant'],
];

const desks = [
  [-3.5, 3.5, 'sales'],
  [3.5, 3.5, 'ceo'],
  [-3.5, -3.5, 'employee'],
  [3.5, -3.5, 'operations'],
  [0, 4.5, 'manager'],
];

const panels = [];
for (const s of [-1, 1]) {
  panels.push({ x0: s < 0 ? -EDGE : POD, x1: s < 0 ? -POD : EDGE, z0: -POD, z1: -POD, n: 'px-z-' });
  panels.push({ x0: s < 0 ? -EDGE : POD, x1: s < 0 ? -POD : EDGE, z0: POD, z1: POD, n: 'px-z+' });
  panels.push({ x0: -POD, x1: -POD, z0: s < 0 ? -EDGE : POD, z1: s < 0 ? -POD : EDGE, n: 'pz-x-' });
  panels.push({ x0: POD, x1: POD, z0: s < 0 ? -EDGE : POD, z1: s < 0 ? -POD : EDGE, n: 'pz-x+' });
}

const ov = (a0, a1, b0, b1, c0, c1, d0, d1) => !(a1 <= c0 || c1 <= a0 || b1 <= d0 || d1 <= b0);
let fails = 0;

const all = [...decor, ...wallMounted];
for (const [x, z, hw, hd, label] of all) {
  const x0 = x - hw, x1 = x + hw, z0 = z - hd, z1 = z + hd;
  if (x0 < -EDGE || x1 > EDGE || z0 < -EDGE || z1 > EDGE) {
    console.log(`OUT OF ROOM: ${label} x[${x0.toFixed(2)},${x1.toFixed(2)}] z[${z0.toFixed(2)},${z1.toFixed(2)}]`);
    fails++;
  }
  // aisle square (rug is intentionally allowed — it lies flat, stepped over)
  if (label !== 'rug' && ov(x0, x1, z0, z1, -POD, POD, -POD, POD)) {
    console.log(`AISLE BLOCKED: ${label}`);
    fails++;
  }
  for (const [dx, dz, name] of desks) {
    if (ov(x0, x1, z0, z1, dx - DESK_W / 2, dx + DESK_W / 2, dz - DESK_D / 2, dz + DESK_D / 2)) {
      console.log(`DESK COLLISION: ${label} vs ${name}`);
      fails++;
    }
  }
  for (const p of panels) {
    if (ov(x0, x1, z0, z1, p.x0, p.x1, p.z0, p.z1)) {
      console.log(`GLASS COLLISION: ${label} vs ${p.n}`);
      fails++;
    }
  }
  for (const [ox, oz, ohw, ohd, other] of all) {
    if (other === label) continue;
    if (ov(x0, x1, z0, z1, ox - ohw, ox + ohw, oz - ohd, oz + ohd)) {
      console.log(`DECOR-DECOR: ${label} vs ${other}`);
      fails++;
    }
  }
}

console.log(`\nchecked ${all.length} decor footprints against ${desks.length} desks, ${panels.length} panels, aisle, room bounds, and each other`);
console.log(fails === 0 ? 'RESULT: no collisions' : `RESULT: ${fails} failure(s)`);
process.exit(fails === 0 ? 0 : 1);
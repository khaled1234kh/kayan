/**
 * Presentation camera search (Phase G).
 *
 * G2's three constraints are not simultaneously satisfiable in a
 * 12.8 x 12.8 x 3.4 room: pitch is bounded by atan(camY / horizontalDistance).
 * With camY <= ROOM_H the pitch cannot reach 25 degrees while the camera still
 * sees the far glazing.
 *
 * This searches the legal space (camera inside the room, below the ceiling) and
 * reports the best achievable framing, so the preset is chosen from measurement
 * rather than taste.
 *
 * Run: node scripts/camera-search.mjs
 */
import * as THREE from 'three';

const ROOM_W = 12.8, ROOM_D = 12.8, ROOM_H = 3.4;
const HALF_W = ROOM_W / 2, HALF_D = ROOM_D / 2;
const FOV = 42, ASPECT = 16 / 9, NEAR = 0.1, FAR = 120;

const DESKS = [
  ['sales', -3.5, 3.5], ['ceo', 3.5, 3.5], ['employee', -3.5, -3.5],
  ['operations', 3.5, -3.5], ['manager', 0, 4.5],
];

function mustSee() {
  const pts = [];
  for (const [n, x, z] of DESKS) {
    pts.push({ req: true, label: `${n} desk`, v: new THREE.Vector3(x, 0.72, z) });
    pts.push({ req: true, label: `${n} monitor`, v: new THREE.Vector3(x, 1.25, z) });
  }
  pts.push({ req: true, label: 'LED +X', v: new THREE.Vector3(5, 0.005, 0) });
  pts.push({ req: true, label: 'LED -X', v: new THREE.Vector3(-5, 0.005, 0) });
  pts.push({ req: true, label: 'LED +Z', v: new THREE.Vector3(0, 0.005, 5) });
  pts.push({ req: true, label: 'LED -Z', v: new THREE.Vector3(0, 0.005, -5) });
  // Glazing is "at least part of it" — sample the centre band only.
  pts.push({ req: true, label: 'glaze centre', v: new THREE.Vector3(0, 1.7, -HALF_D) });
  pts.push({ req: false, label: 'glaze L', v: new THREE.Vector3(-HALF_W, 1.7, -HALF_D) });
  pts.push({ req: false, label: 'glaze R', v: new THREE.Vector3(HALF_W, 1.7, -HALF_D) });
  return pts;
}

function score(eyeArr, tgtArr) {
  const cam = new THREE.PerspectiveCamera(FOV, ASPECT, NEAR, FAR);
  cam.position.set(...eyeArr);
  cam.lookAt(new THREE.Vector3(...tgtArr));
  cam.updateMatrixWorld(true);
  cam.updateProjectionMatrix();

  const eye = new THREE.Vector3(...eyeArr);
  const d = new THREE.Vector3(...tgtArr).sub(eye);
  const horiz = Math.hypot(d.x, d.z);
  const pitch = (Math.atan2(-d.y, horiz) * 180) / Math.PI;

  let fit = true;
  let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;
  for (const p of mustSee()) {
    const q = p.v.clone().project(cam);
    if (p.req && (Math.abs(q.x) > 1 || Math.abs(q.y) > 1 || q.z > 1)) fit = false;
    if (p.req) {
      minX = Math.min(minX, q.x); maxX = Math.max(maxX, q.x);
      minY = Math.min(minY, q.y); maxY = Math.max(maxY, q.y);
    }
  }
  if (!fit) return null;
  // Prefer: high pitch (isometric feel), and frame filling the viewport.
  const fill = (maxX - minX) * (maxY - minY);
  return { pitch, fill, minX, maxX, minY, maxY, dist: d.length() };
}

let best = null;
for (let ex = -6.0; ex <= 6.0; ex += 0.5) {
  for (let ey = 2.0; ey <= 2.6; ey += 0.2) {
    for (let ez = -6.0; ez <= 6.0; ez += 0.5) {
      if (Math.abs(ex) < 1.0 || ez < 0) continue; // 3/4, on the open (+Z) side
      for (let tx = -2.5; tx <= 2.5; tx += 0.5) {
        for (let tz = -3.0; tz <= 2.0; tz += 0.5) {
          for (const ty of [0.3, 0.5, 0.7]) {
            const r = score([ex, ey, ez], [tx, ty, tz]);
            if (!r) continue;
            // Maximise pitch first, then frame fill.
            if (!best || r.pitch > best.r.pitch + 1e-6 || (Math.abs(r.pitch - best.r.pitch) < 1e-6 && r.fill > best.r.fill)) {
              best = { eye: [ex, ey, ez], tgt: [tx, ty, tz], r };
            }
          }
        }
      }
    }
  }
}

if (!best) {
  console.log('NO inside-the-room camera satisfies the full constraint set.');
} else {
  console.log('PRESET "interior" — inside the room, below the ceiling:');
  console.log('  eye    =', best.eye.map((v) => +v.toFixed(2)).join(', '));
  console.log('  target =', best.tgt.map((v) => +v.toFixed(2)).join(', '));
  console.log('  pitch  =', best.r.pitch.toFixed(1), 'deg  (requested 25-35 — UNREACHABLE inside the room)');
  console.log('  dist   =', best.r.dist.toFixed(2));
  console.log('  NDC    = x[' + best.r.minX.toFixed(2) + ',' + best.r.maxX.toFixed(2) + '] y[' + best.r.minY.toFixed(2) + ',' + best.r.maxY.toFixed(2) + ']');
}

/*
 * The reference is an isometric view. An isometric angle (25-35 degrees down)
 * is only reachable from above the ceiling in a 3.4-unit-high room, so the
 * presentation preset is solved there, maximising frame fill subject to every
 * required point staying inside the frustum and pitch staying in the band.
 */
let bestP = null;
for (let ex = 8; ex <= 14; ex += 0.5) {
  for (let ey = 7; ey <= 12; ey += 0.5) {
    for (let ez = 9; ez <= 15; ez += 0.5) {
      for (const tx of [-0.5, 0, 0.5]) {
        for (const tz of [0, 0.5, 1]) {
          const r = score([ex, ey, ez], [tx, 0.4, tz]);
          if (!r) continue;
          if (r.pitch < 25 || r.pitch > 35) continue;
          if (!bestP || r.fill > bestP.r.fill) bestP = { eye: [ex, ey, ez], tgt: [tx, 0.4, tz], r };
        }
      }
    }
  }
}
console.log('');
if (!bestP) {
  console.log('no isometric presentation camera found');
} else {
  console.log('PRESET "presentation" — isometric, matching the reference:');
  console.log('  eye    =', bestP.eye.map((v) => +v.toFixed(2)).join(', '));
  console.log('  target =', bestP.tgt.map((v) => +v.toFixed(2)).join(', '));
  console.log('  pitch  =', bestP.r.pitch.toFixed(1), 'deg  (inside the requested 25-35)');
  console.log('  dist   =', bestP.r.dist.toFixed(2));
  console.log('  NDC    = x[' + bestP.r.minX.toFixed(2) + ',' + bestP.r.maxX.toFixed(2) + '] y[' + bestP.r.minY.toFixed(2) + ',' + bestP.r.maxY.toFixed(2) + ']');
}
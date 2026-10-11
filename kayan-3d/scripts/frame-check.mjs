/**
 * Presentation-camera framing solver (Phase G).
 *
 * G2 asks for three things at once: camera inside the room (y below ROOM_H),
 * pitched 25-35 degrees below horizontal, and all five workstations plus the
 * partitions, LED cross and glazing inside the frustum. Those may not be
 * simultaneously satisfiable in a 12.8 x 12.8 x 3.4 room, so this measures it
 * instead of assuming.
 *
 * Projects a set of must-see world points through a candidate eye/target and
 * reports NDC bounds, pitch, and what falls outside the frustum.
 *
 * Run: node scripts/frame-check.mjs
 */
import * as THREE from 'three';

const ROOM_W = 12.8;
const ROOM_D = 12.8;
const ROOM_H = 3.4;
const HALF_W = ROOM_W / 2;
const HALF_D = ROOM_D / 2;
const FOV = 42;
const ASPECT = 16 / 9;
const NEAR = 0.1;
const FAR = 120;

/** Points that must be in frame for the presentation shot to work. */
const DESKS = [
  ['sales', -3.5, 3.5],
  ['ceo', 3.5, 3.5],
  ['employee', -3.5, -3.5],
  ['operations', 3.5, -3.5],
  ['manager', 0, 4.5],
];

/** Must-see points: desk tops + monitor tops, LED cross ends, glazing corners. */
function mustSee() {
  const pts = [];
  for (const [n, x, z] of DESKS) {
    pts.push({ label: `${n} desk`, v: new THREE.Vector3(x, 0.72, z) });
    pts.push({ label: `${n} monitor`, v: new THREE.Vector3(x, 1.2, z) });
  }
  pts.push({ label: 'LED +X', v: new THREE.Vector3(5, 0.005, 0) });
  pts.push({ label: 'LED -X', v: new THREE.Vector3(-5, 0.005, 0) });
  pts.push({ label: 'LED +Z', v: new THREE.Vector3(0, 0.005, 5) });
  pts.push({ label: 'LED -Z', v: new THREE.Vector3(0, 0.005, -5) });
  pts.push({ label: 'glaze TL', v: new THREE.Vector3(-HALF_W, ROOM_H, -HALF_D) });
  pts.push({ label: 'glaze TR', v: new THREE.Vector3(HALF_W, ROOM_H, -HALF_D) });
  pts.push({ label: 'glaze BC', v: new THREE.Vector3(0, 0, -HALF_D) });
  return pts;
}

function evaluate(eyeArr, targetArr) {
  const cam = new THREE.PerspectiveCamera(FOV, ASPECT, NEAR, FAR);
  cam.position.set(...eyeArr);
  cam.lookAt(new THREE.Vector3(...targetArr));
  cam.updateMatrixWorld(true);
  cam.updateProjectionMatrix();

  const eye = new THREE.Vector3(...eyeArr);
  const target = new THREE.Vector3(...targetArr);
  const dir = target.clone().sub(eye);
  const horiz = Math.hypot(dir.x, dir.z);
  const pitchDeg = (Math.atan2(-dir.y, horiz) * 180) / Math.PI;

  let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;
  const outside = [];
  let behind = 0;
  for (const { label, v } of mustSee()) {
    const p = v.clone().project(cam);
    if (p.z > 1) { behind++; }
    if (p.x < minX) minX = p.x;
    if (p.x > maxX) maxX = p.x;
    if (p.y < minY) minY = p.y;
    if (p.y > maxY) maxY = p.y;
    if (Math.abs(p.x) > 1 || Math.abs(p.y) > 1) {
      outside.push(`${label} (${p.x.toFixed(2)},${p.y.toFixed(2)})`);
    }
  }
  return {
    eye, pitchDeg, minX, maxX, minY, maxY, outside, behind,
    dist: dir.length(),
    fovH: (2 * Math.atan(Math.tan((FOV / 2) * Math.PI / 180) * ASPECT) * 180) / Math.PI,
    fovV: FOV,
  };
}

const candidates = [
  { n: 'A inside, front-right high-ish', eye: [4.6, 2.5, 5.9], tgt: [-0.3, 0.5, -0.2] },
  { n: 'B inside, centre-front', eye: [1.6, 2.5, 6.0], tgt: [0, 0.4, 0.5] },
  { n: 'C inside, corner high', eye: [5.9, 3.2, 5.9], tgt: [-0.4, 0.4, -0.4] },
  { n: 'D above ceiling (old wide)', eye: [9, 7, 9], tgt: [0, 0.5, 0] },
  { n: 'E above ceiling, wider', eye: [11, 9, 12], tgt: [0, 0.4, 0.5] },
  { n: 'F inside, far corner', eye: [6.2, 3.3, 6.2], tgt: [0, 0.4, -0.3] },
];

console.log(`FOV vertical ${FOV}deg, aspect ${ASPECT} -> horizontal FOV ${evaluate([0,0,0],[0,0,1]).fovH.toFixed(1)}deg`);
console.log(`room ${ROOM_W} x ${ROOM_D} x ${ROOM_H}\n`);
for (const c of candidates) {
  const r = evaluate(c.eye, c.tgt);
  const ok = r.outside.length === 0 && r.behind === 0;
  console.log(`${c.n}`);
  console.log(`  eye(${c.eye.join(',')}) pitch ${r.pitchDeg.toFixed(1)}deg  dist ${r.dist.toFixed(2)}`);
  console.log(`  NDC x[${r.minX.toFixed(2)},${r.maxX.toFixed(2)}] y[${r.minY.toFixed(2)},${r.maxY.toFixed(2)}] ${ok ? 'ALL IN FRAME' : `OUT: ${r.outside.join(' ')}`}`);
  if (r.behind) console.log(`  ${r.behind} point(s) beyond far plane`);
  console.log('');
}
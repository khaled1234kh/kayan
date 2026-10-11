/**
 * Elbow / desk-height measurement (Phase D2).
 *
 * DESK_TOP_Y is justified in layout.ts by "the seat pan sits at ~0.48, a seated
 * elbow rests ~0.25 above that". This measures the real rig rather than trusting
 * the comment: it walks the FBX skeleton in the live scene and reports the
 * standing elbow height, plus the seated projection implied by the chair.
 *
 * Run: node scripts/measure-elbow.mjs
 */
import { spawn } from 'node:child_process';
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import puppeteer from 'puppeteer';

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const DESK_TOP_Y = 0.72;
const SEAT_TOP = 0.48;

async function waitForServer(url, timeoutMs) {
  const t0 = Date.now();
  while (Date.now() - t0 < timeoutMs) {
    try {
      const r = await fetch(url);
      if (r.ok) return true;
    } catch {
      /* not up yet */
    }
    await new Promise((r) => setTimeout(r, 500));
  }
  return false;
}

let server = null;
if (!(await waitForServer('http://localhost:5173/', 3000))) {
  server = spawn('npx', ['vite', '--port', '5173', '--strictPort'], {
    cwd: ROOT,
    shell: true,
    stdio: 'ignore',
  });
  if (!(await waitForServer('http://localhost:5173/', 90000))) {
    console.error('FAIL: dev server never came up');
    process.exit(1);
  }
}

const browser = await puppeteer.launch({
  headless: true,
  args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--no-sandbox'],
});
const page = await browser.newPage();
await page.goto('http://localhost:5173/', { waitUntil: 'networkidle2', timeout: 120000 });
await page.waitForFunction('window.__setCamera !== undefined', { timeout: 60000 });
for (let i = 0; i < 90; i++) {
  const s = await page.evaluate(() => window.__sceneStats());
  if (s.skinned > 0) break;
  await new Promise((r) => setTimeout(r, 1000));
}
await new Promise((r) => setTimeout(r, 2500));

const data = await page.evaluate(() => {
  const V = window.__camera.position.constructor;
  const bones = [];
  let sceneRoot = null;
  window.__camera.parent.traverse((o) => {
    if (!o.isBone) return;
    if (!sceneRoot && /mixamorig|armature/i.test(o.name)) sceneRoot = o;
  });
  // Collect distinct skeleton roots (one per actor).
  const seen = new Set();
  window.__camera.parent.traverse((o) => {
    if (!o.isBone) return;
    let root = o;
    while (root.parent && root.parent.isBone) root = root.parent;
    if (seen.has(root.uuid)) return;
    seen.add(root.uuid);
    const rows = [];
    root.traverse((b) => {
      if (!b.isBone) return;
      if (!/shoulder|upperarm|forearm|hand|hip|spine|head/i.test(b.name)) return;
      const p = b.getWorldPosition(new V());
      rows.push({ name: b.name, y: +p.y.toFixed(4), x: +p.x.toFixed(4), z: +p.z.toFixed(4) });
    });
    if (rows.length) bones.push(rows);
  });
  return bones;
});

console.log(`skeletons found: ${data.length}`);
if (data.length) {
  console.log('sample bone names:', data[0].map((b) => b.name).join(', '));
  console.log('');
  for (const skel of data.slice(0, 1)) {
    for (const b of skel) console.log(`  ${b.name.padEnd(28)} y=${String(b.y).padStart(8)}`);
  }
}

await browser.close();
if (server) server.kill();

console.log('');
console.log(`SEAT_TOP (Chair.tsx)      = ${SEAT_TOP}`);
console.log(`DESK_TOP_Y (layout.ts)    = ${DESK_TOP_Y}`);
console.log(`seat -> desk delta        = ${(DESK_TOP_Y - SEAT_TOP).toFixed(3)}`);
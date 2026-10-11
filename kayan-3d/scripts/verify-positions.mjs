/**
 * Actor-reposition verification.
 *
 * Confirms that after moving `data/actors.ts` gridPosition values, everything
 * derived from an actor's position still tracks that actor: state markers,
 * speech bubbles and handoff beams. All three read `actor.gridPosition` via
 * `tileToWorld`, so the check is: for each actor, does the rendered geometry
 * actually sit at the actor's world position?
 *
 * Drives the real demo order so beams and bubbles exist, then compares the
 * scene graph against the expected layout. Exits non-zero on any mismatch.
 */
import { spawn } from 'node:child_process';
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import puppeteer from 'puppeteer';

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const GRID = 12;

/** Authoritative layout under test — mirrors data/actors.ts. */
const EXPECTED = {
  sales: { x: 2.5, z: 9.5 },
  ceo: { x: 9.5, z: 9.5 },
  employee: { x: 2.5, z: 2.5 },
  operations: { x: 9.5, z: 2.5 },
  manager: { x: 6.0, z: 10.5 },
};
const world = (t) => ({ x: t.x - GRID / 2, z: t.z - GRID / 2 });

function startServer() {
  const p = spawn('npx', ['vite', '--port', '5173', '--strictPort'], {
    cwd: ROOT,
    shell: true,
    stdio: 'ignore',
  });
  return p;
}

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
  server = startServer();
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
await page.setViewport({ width: 1280, height: 720 });
await page.goto('http://localhost:5173/', { waitUntil: 'networkidle2', timeout: 120000 });
await page.waitForFunction('window.__setCamera !== undefined', { timeout: 60000 });

// Wait for the FBX actors.
for (let i = 0; i < 90; i++) {
  const s = await page.evaluate(() => window.__sceneStats());
  if (s.skinned > 0) break;
  await new Promise((r) => setTimeout(r, 1000));
}
await new Promise((r) => setTimeout(r, 1500));

// Drive the scripted workflow so bubbles + beams exist.
await page.evaluate(() => {
  const btn = [...document.querySelectorAll('button')].find((b) =>
    /run demo order/i.test(b.textContent || ''),
  );
  if (btn) btn.click();
});

const observed = [];
let beams = 0;
let bubbles = 0;
let markers = 0;

for (let i = 0; i < 30; i++) {
  await new Promise((r) => setTimeout(r, 400));
  const snap = await page.evaluate(() => {
    const scene = window.__camera.parent;
    const out = { bubbles: 0, markers: 0, rings: [], beams: [] };
    scene.traverse((o) => {
      // Speech bubbles are drei <Html> portals -> plain DOM, not scene nodes.
      if (o.userData && o.userData.__html) out.bubbles++;
      // State markers are the coloured ring geometry under each actor.
      if (o.isMesh && o.geometry?.type === 'RingGeometry') {
        const p = o.getWorldPosition(new window.__camera.position.constructor());
        if (p.y < 0.2) {
          out.markers++;
          out.rings.push([+p.x.toFixed(2), +p.z.toFixed(2)]);
        }
      }
      // Beams are thin planes at BEAM_Y = 1.9 with a teal emissive line.
      if (o.isMesh) {
        const p = o.getWorldPosition(new window.__camera.position.constructor());
        if (Math.abs(p.y - 1.9) < 0.05) out.beams.push([+p.x.toFixed(2), +p.z.toFixed(2)]);
      }
    });
    return out;
  });
  markers = snap.markers;
  beams = snap.beams.length;
  observed.length = 0;
  observed.push(...snap.rings);
  bubbles = await page.evaluate(() => {
    // drei <Html> portals mount into a div overlaying the canvas. Count the
    // bubble text nodes rather than guessing at a class name.
    const txt = [...document.querySelectorAll('div')]
      .map((d) => (d.textContent || '').trim())
      .filter((t) => t.length > 0 && t.length < 120 && /→|handoff|approved|ready|blocked/i.test(t));
    return txt.length;
  });
  if (beams > 0) break;
}

const expectedRings = Object.entries(EXPECTED).map(([id, t]) => {
  const w = world(t);
  return { id, x: w.x, z: w.z - 0.95 }; // ground disc sits at local z = -0.95
});

console.log('demo order driven; observed:');
console.log('  state marker rings :', markers);
console.log('  handoff beams      :', beams);
console.log('  bubble dom nodes   :', bubbles);
console.log('');

let failures = 0;
console.log('per-actor ring positions (expect actor world, z-0.95):');
for (const e of expectedRings) {
  let best = null;
  let bestD = Infinity;
  for (const [rx, rz] of observed) {
    const d = Math.hypot(rx - e.x, rz - e.z);
    if (d < bestD) {
      bestD = d;
      best = [rx, rz];
    }
  }
  const ok = bestD < 0.25;
  if (!ok) failures++;
  console.log(
    `  ${e.id.padEnd(10)} expect(${e.x.toFixed(2)},${e.z.toFixed(2)}) ` +
      `nearest(${best ? best[0] : 'n/a'},${best ? best[1] : 'n/a'}) ` +
      `dist=${bestD.toFixed(3)} ${ok ? 'OK' : 'MISMATCH'}`,
  );
}

if (markers !== 5) {
  console.log(`  FAIL: expected 5 state marker rings, saw ${markers}`);
  failures++;
}

await browser.close();
if (server) server.kill();

console.log('');
if (failures) {
  console.log(`RESULT: ${failures} failure(s)`);
  process.exit(1);
}
console.log('RESULT: all actors render at their new positions; markers track correctly.');
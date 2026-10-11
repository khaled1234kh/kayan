/**
 * Headless still renderer for the KAYAN 3D office.
 *
 * Drives the running Vite dev server with Puppeteer, positions the camera with
 * the dev-only DebugBridge helpers, and writes a 1920x1080 PNG.
 *
 * The five Mixamo FBX actors are ~250 MB and stream in asynchronously, so this
 * waits on scene readiness (skinned-mesh count) rather than a fixed timer — a
 * timer-only wait captures a half-built scene.
 *
 * Usage:
 *   node scripts/render-still.mjs --camera front-left --out out/shot.png
 *   node scripts/render-still.mjs --camera wide --out out/scene.png --port 5173
 */

import { spawn } from 'node:child_process';
import { mkdirSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import puppeteer from 'puppeteer';

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '..');

const args = process.argv.slice(2);
const arg = (name, fallback) => {
  const i = args.indexOf(`--${name}`);
  return i !== -1 && args[i + 1] ? args[i + 1] : fallback;
};

const CAMERA = arg('camera', 'front-left');
const OUT = resolve(ROOT, arg('out', 'out/still.png'));
const PORT = Number(arg('port', '5173'));

/**
 * `--time <seconds>` — advance the running animation to a given elapsed time
 * before capture, instead of using the fixed settle delay.
 *
 * The scene animates continuously via r3f's frameloop, so a still's animation
 * phase is otherwise decided by wall-clock and cannot be reproduced. With this
 * flag the same point in the clip can be captured repeatedly, which is what
 * makes time-dependent behaviour (drift, spin, compounding) observable in
 * stills at all.
 */
const TIME_ARG = arg('time', null);
const TIME = TIME_ARG === null ? null : Number(TIME_ARG);

/**
 * CEO seat, in tile coordinates — front-right pod.
 *
 * z was 2.5, which was the CEO's seat before the Phase C actor reposition; it
 * framed an empty gap between two pods. The CEO is now at (9.5, 9.5), matching
 * PLACEMENT in src/data/actors.ts.
 */
const CEO_TILE = { x: 9.5, z: 9.5 };
const GRID = 12; // must match GRID in src/data/layout.ts
const TILE = { x: CEO_TILE.x - GRID / 2, z: CEO_TILE.z - GRID / 2 };

/**
 * Desk/keyboard live at the seat origin; the actor sits 0.6 behind it.
 *
 * y was 0.86, hard-coded against the old DESK_TOP_Y of 0.72 (+0.14). The desk
 * surface is now DESK_TOP_Y = 0.6325, derived from where the Mixamo typing
 * clip actually puts the fingertips, so the same +0.14 offset gives 0.7725.
 */
const DESK = { x: TILE.x, y: 0.7725, z: TILE.z - 0.35 };

const VIEWS = {
  // Elevated and off to one side: the keyboard sits *in front of* the monitor
  // (nearer the actor), so a low front camera is blocked by the monitor itself.
  'front-left': { eye: [DESK.x - 1.25, DESK.y + 1.55, DESK.z + 0.75], target: [DESK.x - 0.05, DESK.y - 0.16, DESK.z] },
  front: { eye: [DESK.x, DESK.y + 1.6, DESK.z + 0.7], target: [DESK.x, DESK.y - 0.16, DESK.z] },
  side: { eye: [DESK.x + 2.0, DESK.y + 1.1, DESK.z + 0.2], target: [DESK.x, DESK.y - 0.14, DESK.z] },
  wide: { eye: [TILE.x + 7.5, 8.0, TILE.z + 11.0], target: [TILE.x, 0.6, TILE.z - 0.6] },
};

let view = VIEWS[CAMERA];
// Explicit eye/target override, for tight inspection shots.
const eyeArg = arg('eye', null);
const targetArg = arg('target', null);
if (eyeArg || targetArg) {
  const base = view ?? VIEWS['front-left'];
  view = {
    eye: eyeArg ? eyeArg.split(',').map(Number) : base.eye,
    target: targetArg ? targetArg.split(',').map(Number) : base.target,
  };
}
if (!view) {
  console.error(`unknown --camera "${CAMERA}". one of: ${Object.keys(VIEWS).join(', ')}`);
  process.exit(1);
}

const log = (m) => process.stdout.write(`[render-still] ${m}\n`);

async function waitForServer(url, timeoutMs) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    try {
      const res = await fetch(url);
      if (res.ok) return true;
    } catch {
      /* not up yet */
    }
    await new Promise((r) => setTimeout(r, 400));
  }
  return false;
}

let vite = null;

async function main() {
  const url = `http://localhost:${PORT}/`;
  log(`dev server: ${url}`);

  if (!(await waitForServer(url, 3000))) {
    log('starting vite dev server...');
    vite = spawn('npx', ['vite', '--port', String(PORT), '--strictPort'], {
      cwd: ROOT,
      stdio: 'ignore',
      shell: true,
    });
    if (!(await waitForServer(url, 90000))) {
      throw new Error('vite dev server did not come up on port ' + PORT);
    }
  }
  log('server responding');

  const browser = await puppeteer.launch({
    headless: true,
    args: [
      '--use-gl=angle',
      '--use-angle=swiftshader',
      '--enable-unsafe-swiftshader',
      '--no-sandbox',
      '--disable-dev-shm-usage',
      '--window-size=1920,1080',
    ],
  });

  try {
    const page = await browser.newPage();
    await page.setViewport({ width: 1920, height: 1080, deviceScaleFactor: 1 });

    const errors = [];
    page.on('pageerror', (e) => errors.push(String(e.message)));
    page.on('console', (m) => {
      if (m.type() === 'error') errors.push(m.text());
    });

    log('navigating...');
    await page.goto(url, { waitUntil: 'networkidle2', timeout: 120000 });

    await page.waitForFunction('window.__setCamera !== undefined', { timeout: 60000 });

    // Wait for the actors to finish streaming in.
    log('waiting for scene (FBX actors)...');
    let stats = { skinned: 0, bones: 0 };
    const deadline = Date.now() + 300000;
    let stable = 0;
    let last = -1;
    while (Date.now() < deadline) {
      stats = await page.evaluate(() => window.__sceneStats());
      if (stats.skinned === last && stats.skinned > 0) {
        stable++;
        if (stable >= 3) break;
      } else {
        stable = 0;
      }
      last = stats.skinned;
      await new Promise((r) => setTimeout(r, 1000));
    }
    log(`scene ready: ${stats.skinned} skinned meshes, ${stats.bones} bones`);
    if (stats.skinned === 0) throw new Error('no skinned meshes loaded — models never arrived');

    // Let the idle animation settle and damping finish.
    await new Promise((r) => setTimeout(r, 2500));

    log(`camera "${CAMERA}" -> eye ${view.eye} target ${view.target}`);
    await page.evaluate(
      (e, t) => window.__setCamera(...e, ...t),
      view.eye,
      view.target,
    );

    if (TIME === null) {
      await new Promise((r) => setTimeout(r, 1200));
    } else {
      // Hold for the requested elapsed animation time, counting from here, and
      // never capture sooner than the camera settle.
      const MIN_SETTLE = 400;
      const deadline = Date.now() + TIME * 1000;
      const remaining = deadline - Date.now();
      log(`holding to animation time t=${TIME}s (${Math.max(0, Math.round(remaining))}ms)`);
      await new Promise((r) => setTimeout(r, Math.max(MIN_SETTLE, remaining)));
      log(`actual elapsed ${((Date.now() - deadline + TIME * 1000) / 1000).toFixed(2)}s`);
    }

    mkdirSync(dirname(OUT), { recursive: true });
    await page.screenshot({ path: OUT, type: 'png' });
    log(`wrote ${OUT}`);

    if (errors.length) {
      log(`page reported ${errors.length} error(s):`);
      errors.slice(0, 10).forEach((e) => log(`   ${e}`));
    } else {
      log('no page errors');
    }
  } finally {
    await browser.close();
    if (vite) vite.kill();
  }
}

main()
  .then(() => process.exit(0))
  .catch((err) => {
    console.error(`[render-still] FAILED: ${err && err.message ? err.message : err}`);
    if (vite) vite.kill();
    process.exit(1);
  });
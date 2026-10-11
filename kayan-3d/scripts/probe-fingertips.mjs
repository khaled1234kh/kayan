/**
 * Native-typing fingertip probe (Phase H, Part 1).
 *
 * With the arm-track stripping removed and ARM_POSE emptied, the FBX clip alone
 * drives the arms. This reports where each actor's fingertips actually land in
 * world space, so the keyboard/mouse/desk can be moved to MEET the animation
 * rather than the animation being fought.
 *
 * Reports every actor, not just one, so we can confirm they share a pose.
 *
 * Run: node out/probe-fingertips.mjs
 */
import { spawn } from 'node:child_process';
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import puppeteer from 'puppeteer';

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const AT_SECONDS = Number(process.argv[2] ?? 1.01);

async function waitForServer(url, ms) {
  const t0 = Date.now();
  while (Date.now() - t0 < ms) {
    try {
      if ((await fetch(url)).ok) return true;
    } catch {
      /* not up */
    }
    await new Promise((r) => setTimeout(r, 400));
  }
  return false;
}

let vite = null;
if (!(await waitForServer('http://localhost:5173/', 3000))) {
  vite = spawn('npx', ['vite', '--port', '5173', '--strictPort'], {
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
for (let i = 0; i < 120; i++) {
  const s = await page.evaluate(() => window.__sceneStats());
  if (s.skinned > 0) break;
  await new Promise((r) => setTimeout(r, 1000));
}
await new Promise((r) => setTimeout(r, 2500));
await new Promise((r) => setTimeout(r, AT_SECONDS * 1000));

const out = await page.evaluate(() => {
  const V = window.__camera.position.constructor;
  // One skeleton root per actor.
  const seen = new Set();
  const out = [];
  window.__camera.parent.traverse((o) => {
    if (!o.isBone || !/Hips$/.test(o.name)) return;
    let root = o;
    while (root.parent && root.parent.isBone) root = root.parent;
    if (seen.has(root.uuid)) return;
    seen.add(root.uuid);

    const grab = (hand) => {
      let wrist = null;
      root.traverse((b) => {
        if (!wrist && b.isBone && b.name.endsWith(`${hand}Hand`)) wrist = b;
      });
      if (!wrist) return null;
      // Fingertip = descendant of the wrist furthest from it.
      let tip = null;
      let best = 0;
      const wp = wrist.getWorldPosition(new V());
      wrist.traverse((b) => {
        if (!b.isBone || b === wrist) return;
        const d = b.getWorldPosition(new V()).distanceTo(wp);
        if (d > best) {
          best = d;
          tip = b;
        }
      });
      const w = wrist.getWorldPosition(new V());
      const t = tip ? tip.getWorldPosition(new V()) : null;
      const r = (n) => +n.toFixed(4);
      return {
        wrist: [r(w.x), r(w.y), r(w.z)],
        tip: t ? [r(t.x), r(t.y), r(t.z)] : null,
        tipBone: tip ? tip.name.replace(/^.*Hand/, 'Hand') : null,
      };
    };

    // Elbow for the ergonomic check.
    let elbow = null;
    root.traverse((b) => {
      if (!elbow && b.isBone && b.name.endsWith('RightForeArm')) elbow = b;
    });

    out.push({
      root: root.name.replace(/^.*?(mixamorig\d*)/, '$1') || root.name,
      Hips: (() => {
        const p = o.getWorldPosition(new V());
        return [+p.x.toFixed(4), +p.y.toFixed(4), +p.z.toFixed(4)];
      })(),
      Left: grab('Left'),
      Right: grab('Right'),
      elbowY: elbow ? +elbow.getWorldPosition(new V()).y.toFixed(4) : null,
    });
  });
  return out;
});

console.log(`fingertips at t = ${AT_SECONDS}s (native clip, no offsets)\n`);
for (const a of out) {
  console.log(`actor root: ${a.root}   hips=${JSON.stringify(a.Hips)}`);
  if (a.Left) console.log(`  left_fingertip_world  = (${a.Left.tip})   wrist=(${a.Left.wrist})  tipBone=${a.Left.tipBone}`);
  if (a.Right) console.log(`  right_fingertip_world = (${a.Right.tip})   wrist=(${a.Right.wrist})  tipBone=${a.Right.tipBone}`);
  if (a.Left?.tip && a.Right?.tip) {
    const mid = a.Left.tip.map((v, i) => +(((v + a.Right.tip[i]) / 2)).toFixed(4));
    console.log(`  midpoint(left,right)  = (${mid})`);
  }
  console.log(`  elbow(RightForeArm) y = ${a.elbowY}`);
  console.log('');
}

await browser.close();
if (vite) vite.kill();
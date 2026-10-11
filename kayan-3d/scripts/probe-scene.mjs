/** Scene probe: what is actually in the graph near the CEO desk. */
import { spawn } from 'node:child_process';
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import puppeteer from 'puppeteer';

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const GRID = 12;
const TILE = { x: 9.5 - GRID / 2, z: 2.5 - GRID / 2 };

const browser = await puppeteer.launch({
  headless: true,
  args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--no-sandbox'],
});
const page = await browser.newPage();
await page.setViewport({ width: 1280, height: 720 });
await page.goto('http://localhost:5173/', { waitUntil: 'networkidle2', timeout: 120000 });
await page.waitForFunction('window.__setCamera !== undefined', { timeout: 60000 });

for (let i = 0; i < 90; i++) {
  const s = await page.evaluate(() => window.__sceneStats());
  if (s.skinned > 0) break;
  await new Promise((r) => setTimeout(r, 1000));
}
await new Promise((r) => setTimeout(r, 2000));

const report = await page.evaluate(({ tx, tz }) => {
  const out = { instanced: [], meshes: 0, near: [] };
  const scene = window.__camera.parent;
  scene.traverse((o) => {
    if (o.isInstancedMesh) {
      out.instanced.push({
        name: o.name || '(unnamed)',
        count: o.count,
        visible: o.visible,
        pos: o.getWorldPosition(new window.__camera.position.constructor()).toArray().map((v) => +v.toFixed(3)),
      });
    }
    if (o.isMesh) out.meshes++;
  });
  return out;
}, { tx: TILE.x, tz: TILE.z });

console.log('mesh count:', report.meshes);
console.log('instanced meshes:', JSON.stringify(report.instanced, null, 2));

// what sits on the desk surface near the keyboard?
const deskItems = await page.evaluate(({ tx, tz }) => {
  const V = window.__camera.position.constructor;
  const rows = [];
  window.__camera.parent.traverse((o) => {
    if (!o.isMesh && !o.isInstancedMesh) return;
    const p = o.getWorldPosition(new V());
    if (Math.abs(p.y - 0.8) < 0.25 && Math.abs(p.x - tx) < 0.8 && Math.abs(p.z - (tz - 0.35)) < 0.6) {
      o.geometry.computeBoundingBox?.();
      const bb = o.geometry.boundingBox;
      rows.push({
        type: o.type,
        name: o.name || '(unnamed)',
        pos: [+p.x.toFixed(3), +p.y.toFixed(3), +p.z.toFixed(3)],
        visible: o.visible,
        size: bb ? [+(bb.max.x - bb.min.x).toFixed(3), +(bb.max.y - bb.min.y).toFixed(3), +(bb.max.z - bb.min.z).toFixed(3)] : null,
        matColor: o.material?.color?.getHexString?.() ?? null,
      });
    }
  });
  return rows;
}, { tx: TILE.x, tz: TILE.z });

console.log('objects on the desk surface:', JSON.stringify(deskItems, null, 2));

await browser.close();
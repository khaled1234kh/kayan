/** Measures the real character bbox and room proportions from the live scene. */
import puppeteer from 'puppeteer';

const browser = await puppeteer.launch({
  headless: true,
  args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--no-sandbox'],
});
const page = await browser.newPage();
await page.setViewport({ width: 1280, height: 720 });
await page.goto('http://localhost:5173/', { waitUntil: 'networkidle2', timeout: 120000 });
await page.waitForFunction('window.__setCamera !== undefined', { timeout: 60000 });
for (let i = 0; i < 120; i++) {
  const s = await page.evaluate(() => window.__sceneStats());
  if (s.skinned > 0) break;
  await new Promise((r) => setTimeout(r, 1000));
}
await new Promise((r) => setTimeout(r, 2500));

const out = await page.evaluate(() => {
  const scene = window.__camera.parent;
  // Character bbox: union of all SkinnedMesh world bounds.
  const box = new (window.__THREE_Box3__ ?? Object)();
  const res = { charMinY: Infinity, charMaxY: -Infinity, charSpanX: 0 };
  let minY = Infinity, maxY = -Infinity, minX = Infinity, maxX = -Infinity;
  scene.traverse((o) => {
    if (!o.isSkinnedMesh) return;
    o.updateWorldMatrix(true, true);
    o.geometry.computeBoundingBox();
    const bb = o.geometry.boundingBox.clone();
    bb.applyMatrix4(o.matrixWorld);
    minY = Math.min(minY, bb.min.y);
    maxY = Math.max(maxY, bb.max.y);
    minX = Math.min(minX, bb.min.x);
    maxX = Math.max(maxX, bb.max.x);
  });
  res.charMinY = +minY.toFixed(4);
  res.charMaxY = +maxY.toFixed(4);
  res.charHeight = +(maxY - minY).toFixed(4);
  res.charWidth = +(maxX - minX).toFixed(4);

  // Wall + board measurements by name/size heuristics.
  const walls = [];
  scene.traverse((o) => {
    if (!o.isMesh) return;
    o.geometry.computeBoundingBox();
    const bb = o.geometry.boundingBox.clone().applyMatrix4(o.matrixWorld);
    const size = [bb.max.x - bb.min.x, bb.max.y - bb.min.y, bb.max.z - bb.min.z];
    // A wall is a large, tall, thin slab.
    if (size[0] > 5 && size[1] > 0.8 && size[1] < 6 && size[2] < 2) {
      walls.push({ pos: [+o.position.x.toFixed(2), +o.position.y.toFixed(2), +o.position.z.toFixed(2)], size: size.map((v) => +v.toFixed(3)) });
    }
  });
  res.walls = walls.slice(0, 6);
  return res;
});

console.log(JSON.stringify(out, null, 2));

// Recommendation, computed from the measurement.
const target = 0.575; // character should be ~57.5% of wall height
const suggested = out.charHeight / target;
console.log(`\ncharacter height      : ${out.charHeight}`);
console.log(`character feet at y   : ${out.charMinY}`);
console.log(`target ratio          : ${target}`);
console.log(`SUGGESTED WALL HEIGHT : ${suggested.toFixed(3)}`);
console.log(`current wall height   : 1.5  -> character is ${((out.charHeight / 1.5) * 100).toFixed(1)}% of it`);
console.log(`board 1.06 / wall 1.5 = ${(1.06 / 1.5).toFixed(3)}`);
console.log(`board 1.06 / wall ${suggested.toFixed(2)} = ${(1.06 / suggested).toFixed(3)}`);

await browser.close();
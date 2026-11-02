// Offline equivalence check. Texture decoding is deliberately excluded here;
// embedded payload identity is checked by the binary writer tests/manifest.
import fs from 'node:fs';
import path from 'node:path';
import assert from 'node:assert/strict';
import * as THREE from 'three';
import { FBXLoader } from 'three-stdlib';
globalThis.window = { URL };
THREE.TextureLoader.prototype.load = function () { return new THREE.Texture(); };
const [originalDir, candidateDir, reportPath] = process.argv.slice(2);
assert(originalDir && candidateDir && reportPath, 'Provide original candidate report paths');
const reports = [];
function load(file) {
  const buffer = fs.readFileSync(file), warnings = [], previous = console.warn;
  console.warn = (...args) => warnings.push(args.join(' '));
  try { return { scene: new FBXLoader().parse(buffer.buffer.slice(buffer.byteOffset, buffer.byteOffset + buffer.byteLength), ''), warnings }; }
  finally { console.warn = previous; }
}
function meshes(scene) { const out = []; scene.traverse(n => { if (n.isMesh) out.push(n); }); return out; }
function near(a, b, tolerance = 2e-6) {
  assert.equal(a.length, b.length);
  for (let i = 0; i < a.length; i++) assert(Math.abs(a[i] - b[i]) <= tolerance, `Value ${i}: ${a[i]} != ${b[i]}`);
}
function influences(mesh, vertex) {
  const ids = mesh.geometry.attributes.skinIndex, weights = mesh.geometry.attributes.skinWeight, out = new Map();
  for (let i = 0; i < 4; i++) {
    const w = weights.array[vertex * 4 + i], bone = ids.array[vertex * 4 + i];
    assert(Number.isFinite(w) && w >= 0);
    if (w) out.set(bone, (out.get(bone) || 0) + w);
  }
  assert(Math.abs([...out.values()].reduce((a,b) => a+b, 0) - 1) < 2e-6);
  return out;
}
for (const file of fs.readdirSync(originalDir).filter(n => n.endsWith('.fbx')).sort()) {
  const before = load(path.join(originalDir, file)), after = load(path.join(candidateDir, file));
  const a = meshes(before.scene), b = meshes(after.scene);
  assert.equal(a.length, b.length);
  let vertices = 0;
  for (let m = 0; m < a.length; m++) {
    const old = a[m], next = b[m]; assert.equal(old.name, next.name);
    assert.deepEqual(old.matrix.elements, next.matrix.elements);
    assert.deepEqual(Object.keys(old.geometry.attributes), Object.keys(next.geometry.attributes));
    for (const key of Object.keys(old.geometry.attributes).filter(k => !['skinIndex','skinWeight'].includes(k))) {
      assert.deepEqual(old.geometry.attributes[key].array, next.geometry.attributes[key].array);
    }
    assert.deepEqual(old.geometry.index?.array, next.geometry.index?.array);
    assert.deepEqual(old.geometry.groups, next.geometry.groups);
    if (old.isSkinnedMesh) {
      assert.deepEqual(old.skeleton.bones.map(n => n.name), next.skeleton.bones.map(n => n.name));
      assert.deepEqual(old.skeleton.boneInverses.map(n => n.elements), next.skeleton.boneInverses.map(n => n.elements));
      assert.deepEqual(old.bindMatrix.elements, next.bindMatrix.elements);
      const count = old.geometry.attributes.position.count; vertices += count;
      for (let v = 0; v < count; v++) {
        const left = influences(old, v), right = influences(next, v);
        assert.deepEqual([...left.keys()].sort(), [...right.keys()].sort());
        near([...left.keys()].map(k => left.get(k)), [...left.keys()].map(k => right.get(k)));
      }
    }
    const materials = x => (Array.isArray(x.material) ? x.material : [x.material]).map(mat => ({
      name: mat.name, color: mat.color?.toArray(), opacity: mat.opacity,
      maps: ['map','normalMap','alphaMap','aoMap','emissiveMap','specularMap','bumpMap'].map(k => Boolean(mat[k]))
    }));
    assert.deepEqual(materials(old), materials(next));
  }
  assert.equal(before.scene.animations.length, after.scene.animations.length);
  before.scene.animations.forEach((clip, i) => {
    const other = after.scene.animations[i];
    assert.equal(clip.name, other.name); assert.equal(clip.duration, other.duration);
    assert.equal(clip.tracks.length, other.tracks.length);
    clip.tracks.forEach((track, j) => {
      assert.equal(track.name, other.tracks[j].name);
      assert.deepEqual(track.times, other.tracks[j].times); assert.deepEqual(track.values, other.tracks[j].values);
    });
  });
  // Compare deformed positions at several actual animation times, not just bind pose.
  const mixA = new THREE.AnimationMixer(before.scene), mixB = new THREE.AnimationMixer(after.scene);
  const clipA = before.scene.animations.find(c => c.tracks.length), clipB = after.scene.animations.find(c => c.tracks.length);
  if (clipA) { mixA.clipAction(clipA).play(); mixB.clipAction(clipB).play(); }
  for (const time of [0, 4, 8, 16]) {
    mixA.setTime(time); mixB.setTime(time); before.scene.updateMatrixWorld(true); after.scene.updateMatrixWorld(true);
    a.forEach((mesh, index) => {
      if (!mesh.isSkinnedMesh) return;
      mesh.skeleton.update(); b[index].skeleton.update();
      for (let v = 0; v < mesh.geometry.attributes.position.count; v += 23) {
        const p = new THREE.Vector3().fromBufferAttribute(mesh.geometry.attributes.position, v);
        const q = p.clone(); mesh.applyBoneTransform(v, p); b[index].applyBoneTransform(v, q);
        near(p.toArray(), q.toArray(), 0.00015);
      }
    });
  }
  assert(before.warnings.some(w => w.includes('ShininessExponent')));
  assert(before.warnings.some(w => w.includes('more than 4 skinning weights')));
  assert.equal(after.warnings.length, 0, after.warnings.join('\n'));
  reports.push({file, meshes:a.length, expandedVertices:vertices, poseTimes:[0,4,8,16], beforeWarnings:before.warnings, afterWarnings:after.warnings});
  console.log(`${file}: geometry, effective weights, materials, animation and sampled poses equivalent; no loader warnings`);
}
fs.writeFileSync(reportPath, JSON.stringify({textureDecoding:'excluded; check actual browser separately', reports}, null, 2));

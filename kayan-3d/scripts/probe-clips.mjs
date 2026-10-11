/**
 * FBX animation-clip inventory (Phase H investigation).
 *
 * Answers one question: does any actor model ship a typing clip, or are these
 * single-clip idle FBX files with no typing animation at all?
 *
 * Parses the FBX directly with the project's own three + FBXLoader. Text
 * grepping is unreliable on 45-55 MB binary-ish ASCII files; asking the actual
 * loader is definitive.
 *
 * Run: node out/probe-clips.mjs
 */
import * as THREE from 'three';
import { FBXLoader } from 'three/examples/jsm/loaders/FBXLoader.js';
import { readFileSync, statSync } from 'node:fs';

// FBXLoader resolves embedded textures via browser APIs. Stub what it touches.
globalThis.window = globalThis.window || {
  URL: { createObjectURL: () => 'blob:stub' },
};
globalThis.Blob = globalThis.Blob || class {
  constructor() {}
};
THREE.ImageLoader.prototype.load = function () {
  return { isTexture: true, image: {}, needsUpdate: true };
};
THREE.FileLoader.prototype.load = function () {};

const TYPO = /typ|type|keyboard|key|punch|write/i;

const loader = new FBXLoader();
for (const name of ['CEO', 'Employee', 'AIManager', 'AISales', 'AIOps']) {
  const path = `public/models/${name}.fbx`;
  const buf = readFileSync(path);
  const ab = buf.buffer.slice(buf.byteOffset, buf.byteOffset + buf.byteLength);
  const group = loader.parse(ab, '');
  const clips = group.animations || [];
  console.log(
    `${name}.fbx  (${(statSync(path).size / 1048576).toFixed(1)} MB)  clips=${clips.length}`,
  );
  for (const c of clips) {
    const typing = TYPO.test(c.name || '');
    console.log(
      `     name=${JSON.stringify(c.name)}  duration=${c.duration.toFixed(3)}s  ` +
        `tracks=${c.tracks.length}${typing ? '   <-- POSSIBLE TYPING CLIP' : ''}`,
    );
  }
}
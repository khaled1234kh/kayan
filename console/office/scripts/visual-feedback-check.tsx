import assert from 'node:assert/strict';
import { Children, isValidElement } from 'react';
import { DirectionalLight, Object3D, PerspectiveCamera, Vector3 } from 'three';
import { monitorTextLines } from '../src/components/actors/monitorText';
import { boundedLabelPosition } from '../src/components/actors/labelPosition';
import SceneLighting from '../src/components/scene/SceneLighting';
import { ROOM_D, ROOM_H, ROOM_W } from '../src/data/layout';

const measure = (text: string) => Array.from(text).length;
assert.deepEqual(monitorTextLines('No active task', measure, 30, 2), ['No active task']);
for (const text of ['Completed with independently reproduced findings and detailed notes', 'X'.repeat(80), 'Verified-finding report saved successfully']) {
  const lines = monitorTextLines(text, measure, 15, 2);
  assert(lines.length <= 2 && lines.every(line => measure(line) <= 15));
  assert(lines[lines.length - 1].endsWith('…'), 'Overflow must be explicitly marked');
}
assert.deepEqual(monitorTextLines('abc', measure, 0, 2), []);
const camera = new PerspectiveCamera(42, 1.4, .1, 120);
camera.position.set(0, 2, 3); camera.lookAt(0, 1, 0); camera.updateMatrixWorld();
for (const size of [{ width: 300, height: 200 }, { width: 1600, height: 900 }]) {
  for (const point of [[-100, 100, 0], [100, -100, 0], [0, 1, 0]]) {
    const object = new Object3D(); object.position.fromArray(point); object.updateMatrixWorld();
    const [x, y] = boundedLabelPosition(object, camera, size);
    if(point[0]===0) assert(x >= 98 && x <= size.width - 98 && y >= 24 && y <= size.height - 24);
    else assert.deepEqual([x,y],[-10000,-10000], 'Offscreen labels must not pile up on viewport edges');
  }
}
const key = Children.toArray(SceneLighting().props.children).find(element =>
  isValidElement<Record<string, any>>(element) && element.type === 'directionalLight' && element.props.castShadow);
assert(isValidElement<Record<string, any>>(key));
const light = new DirectionalLight(); light.position.fromArray(key.props.position);
Object.assign(light.shadow.camera, { left: key.props['shadow-camera-left'], right: key.props['shadow-camera-right'],
  top: key.props['shadow-camera-top'], bottom: key.props['shadow-camera-bottom'] });
// WebGLShadowMap refreshes this when allocating the map; reproduce that here.
light.shadow.camera.updateProjectionMatrix();
light.updateMatrixWorld(); light.target.updateMatrixWorld(); light.shadow.updateMatrices(light);
let maximum = 0;
for (const x of [-ROOM_W / 2 - .3, ROOM_W / 2 + .3]) for (const y of [0, ROOM_H]) for (const z of [-ROOM_D / 2 - 1.6, ROOM_D / 2 + .3]) {
  const p = new Vector3(x, y, z).project(light.shadow.camera);
  maximum = Math.max(maximum, Math.abs(p.x), Math.abs(p.y));
  assert(Math.abs(p.x) < 1 && Math.abs(p.y) < 1 && p.z > -1 && p.z < 1, 'Room clips the key shadow frustum');
}
console.log(`PASS agent-label viewport bounds, monitor wrapping/ellipsis and key-shadow room coverage (max NDC ${maximum.toFixed(3)}). Geometry/text checks, not rendered acceptance.`);

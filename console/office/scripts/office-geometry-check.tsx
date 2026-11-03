/** Geometry/raycast checks, not a rendered screenshot. */
import assert from 'node:assert/strict';
import { Children, isValidElement } from 'react';
import { BoxGeometry, FrontSide, Group, Mesh, MeshBasicMaterial, Object3D, PerspectiveCamera, Raycaster, Vector3 } from 'three';
import { Monitor } from '../src/components/actors/Monitor';
import { LiveMonitorScreen } from '../src/components/actors/LiveMonitorScreen';
import { createDisplayGeometry, DISPLAY_SIDE } from '../src/components/actors/monitorGeometry';
import { overviewPosition } from '../src/components/office/cameraFraming';
import { SEED_ACTORS, workstationRotation } from '../src/data/actors';
import { deskPropLayout } from '../src/components/actors/DeskProps';

// Build the actual Monitor JSX transforms and casing geometry without a browser.
function build(element: unknown): Object3D | null {
  if (!isValidElement<Record<string, any>>(element)) return null;
  const p = element.props;
  if (element.type === LiveMonitorScreen) {
    const display = new Mesh(createDisplayGeometry(), new MeshBasicMaterial({ side: DISPLAY_SIDE }));
    display.position.z = 0.001; display.name = 'display'; return display;
  }
  if (element.type !== 'group' && element.type !== 'mesh') return null;
  const object = element.type === 'mesh' ? new Mesh() : new Group();
  object.name = p.name ?? '';
  if (p.position) object.position.fromArray(p.position);
  if (p.rotation) object.rotation.fromArray(p.rotation);
  for (const child of Children.toArray(p.children)) {
    if (isValidElement<Record<string, any>>(child) && object instanceof Mesh) {
      if (child.type === 'boxGeometry') object.geometry = new BoxGeometry(...child.props.args as [number, number, number]);
      if (String(child.type).endsWith('Material')) object.material = new MeshBasicMaterial({ side: child.props.side ?? FrontSide });
    }
    const nested = build(child); if (nested) object.add(nested);
  }
  return object;
}
const workstation = build(Monitor({ actor: SEED_ACTORS[0] }))!;
workstation.updateMatrixWorld(true);
const display = workstation.getObjectByName('display') as Mesh;
const center = display.getWorldPosition(new Vector3());
const normal = new Vector3(0, 0, 1).transformDirection(display.matrixWorld);
assert(normal.z < -0.9 && normal.y > 0, 'Face must point toward the seated worker and slightly upward');
const fromFront = new Raycaster(center.clone().addScaledVector(normal, .8), normal.clone().negate());
assert.equal(fromFront.intersectObject(workstation, true)[0].object, display, 'Display must sit in front of its casing');
const fromRear = new Raycaster(center.clone().addScaledVector(normal, -.8), normal);
assert.equal(fromRear.intersectObject(display).length, 0, 'Screen must never render through its rear face');
assert.equal(fromRear.intersectObject(workstation, true)[0].object.name, 'monitor-casing', 'Rear must be solid casing');

// Check the room remains framed on typical window shapes, including a narrow viewport.
for (const aspect of [.65, 1, 1.4, 16/9, 2.3]) {
  const camera = new PerspectiveCamera(42, aspect, .1, 120);
  camera.position.fromArray(overviewPosition(aspect)); camera.lookAt(0, .7, 0); camera.updateMatrixWorld();
  for (const x of [-6.7, 6.7]) for (const y of [0, 3.4]) for (const z of [-7.8, 6.7]) {
    const projected = new Vector3(x, y, z).project(camera);
    assert(Math.abs(projected.x) < .92 && Math.abs(projected.y) < .92, `Room cropped at aspect ${aspect}`);
  }
}
const positions = SEED_ACTORS.map(a => new Vector3(a.gridPosition.x - 6, 0, a.gridPosition.z - 6));
for (const actor of SEED_ACTORS) {
  const assembly = new Group();
  assembly.rotation.y = workstationRotation(actor);
  assembly.add(build(Monitor({ actor }))!);
  assembly.updateMatrixWorld(true);
  const face = assembly.getObjectByName('display') as Mesh;
  const faceCenter = face.getWorldPosition(new Vector3());
  const faceNormal = new Vector3(0,0,1).transformDirection(face.matrixWorld);
  const workerEye = assembly.localToWorld(new Vector3(0,1.01,-.6));
  assert(faceNormal.dot(workerEye.sub(faceCenter)) > 0, `${actor.name} monitor faces away from its worker`);
  const workerForward = new Vector3(0,0,1).transformDirection(assembly.matrixWorld);
  assert(actor.gridPosition.z > 6 ? workerForward.z < -.9 : workerForward.z > .9, 'Workstation faces away from the central floor');
}
for (let i = 0; i < positions.length; i++) for (let j = i+1; j < positions.length; j++) {
  assert(positions[i].distanceTo(positions[j]) > 2.5, 'Workstation footprints overlap');
}
const dressing = new Set<string>();
for (let variant = 0; variant < 5; variant++) {
  const layout = deskPropLayout(variant);
  assert(Math.hypot(layout.plantX + .68, layout.plantZ - layout.lampZ) > .07 + .055 + .02, 'Plant intersects lamp base');
  assert(layout.plantZ - .075 > .24 && layout.lampZ - .09 > .24, 'Tall props extend in front of display');
  assert(Math.abs(layout.plantX) + .075 < .8 && Math.abs(layout.plantZ) + .075 < .45, 'Plant extends outside desktop');
  assert(Math.hypot(layout.plantX - layout.mugX, layout.plantZ - .18) > .075 + .038, 'Plant intersects mug');
  dressing.add(JSON.stringify(layout));
}
assert.equal(dressing.size, 5, 'Roles should have five stable dressing combinations');
console.log('PASS monitor front/rear raycasts, solid casing, upward worker-facing normal, five viewport fits, workstation separation and plant/lamp/mug clearances (no visual claim)');

// New architecture regressions: oversize rear cards and invisible-wall label occlusion.
const {REAR_OPENING,wallUpperVisible,visibleWallRaycast}=await import('../src/components/office/Office');
assert(REAR_OPENING.width<12.8&&REAR_OPENING.height<3.4&&REAR_OPENING.z < -6.4);
assert.equal(wallUpperVisible(1,10),false);assert.equal(wallUpperVisible(-1,10),true);
assert.equal(wallUpperVisible(-1,-10),false);assert.equal(wallUpperVisible(1,-10),true);
const hiddenWall=new Mesh(new BoxGeometry(2,2,.2),new MeshBasicMaterial());hiddenWall.position.set(0,0,-2);hiddenWall.updateMatrixWorld();
const ray=new Raycaster(new Vector3(0,0,0),new Vector3(0,0,-1));const hits:any[]=[];
hiddenWall.visible=false;visibleWallRaycast.call(hiddenWall,ray,hits);assert.equal(hits.length,0);
hiddenWall.visible=true;visibleWallRaycast.call(hiddenWall,ray,hits);assert(hits.length>0);
const {OFFICE_VIEW_DIRECTIONS}=await import('../src/components/office/cameraFraming');
for(const direction of Object.values(OFFICE_VIEW_DIRECTIONS))for(const aspect of [.65,1,1.4,16/9,2.3]){
 const camera=new PerspectiveCamera(42,aspect,.1,120);camera.position.fromArray(overviewPosition(aspect,42,direction));camera.lookAt(0,.7,0);camera.updateMatrixWorld();
 for(const x of [-6.7,6.7])for(const y of [0,3.4])for(const z of [-7.8,6.7]){const projected=new Vector3(x,y,z).project(camera);assert(Math.abs(projected.x)<.92&&Math.abs(projected.y)<.92);}
}
console.log('PASS contained rear opening, near-wall cutaway direction, invisible-wall raycast and all three overview preset fits. These checks do not establish rendered acceptance.');

const {workstationCameraPosition}=await import('../src/components/office/cameraFraming');
for(const actor of SEED_ACTORS){const target=new Vector3(actor.gridPosition.x-6,1,actor.gridPosition.z-6);const position=workstationCameraPosition(target,workstationRotation(actor));assert(Math.abs(position.x)<=5.6+1e-9&&Math.abs(position.z)<=5.6+1e-9,'Selected camera crosses shell');assert(position.distanceTo(target)>=3,'Focus conflicts with orbit near-distance limit');}
console.log('PASS selected cameras remain inside the shell for all five actual workstation placements.');

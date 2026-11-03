import { MathUtils, Vector3 } from 'three';
import { ROOM_W, ROOM_D } from '../../data/layout';

export const OVERVIEW_TARGET: [number, number, number] = [0, 0.7, 0];

/** Fit the room, including wall height, at the actual viewport aspect ratio. */
export function overviewPosition(aspect: number, fov = 42, directionValues:[number,number,number]=[5.8,9.2,12]): [number, number, number] {
  const target = new Vector3().fromArray(OVERVIEW_TARGET);
  const direction = new Vector3().fromArray(directionValues).normalize();
  const right = new Vector3().crossVectors(new Vector3(0, 1, 0), direction).normalize();
  const up = new Vector3().crossVectors(direction, right).normalize();
  const tanY = Math.tan(fov * Math.PI / 360) / 1.1;
  const tanX = tanY * Math.max(0.25, aspect);
  let distance = 0;
  for (const x of [-6.7, 6.7]) for (const y of [0, 3.4]) for (const z of [-7.8, 6.7]) {
    const point = new Vector3(x, y, z).sub(target);
    distance = Math.max(distance, point.dot(direction) + Math.abs(point.dot(right)) / tanX,
      point.dot(direction) + Math.abs(point.dot(up)) / tanY);
  }
  return target.addScaledVector(direction, distance).toArray() as [number, number, number];
}

export type OfficeView='overview'|'isometric'|'front'|'elevated'|'selected';
export const OFFICE_VIEW_DIRECTIONS={overview:[5.8,9.2,12],isometric:[10,10,10],front:[0,9.5,14],elevated:[6,17,10]} satisfies Record<Exclude<OfficeView,'selected'>,[number,number,number]>;

/** Focus stays inside the glazing/side walls, even for rear-corner stations. */
export function workstationCameraPosition(target:Vector3,rotation:number):Vector3 {
  const position=target.clone().add(new Vector3(2.8,2.5,-3.6).applyAxisAngle(new Vector3(0,1,0),rotation));
  position.x=MathUtils.clamp(position.x,-ROOM_W/2+.8,ROOM_W/2-.8);
  position.z=MathUtils.clamp(position.z,-ROOM_D/2+.8,ROOM_D/2-.8);
  return position;
}

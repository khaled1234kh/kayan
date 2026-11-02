import { Vector3 } from 'three';

export const OVERVIEW_TARGET: [number, number, number] = [0, 0.7, 0];

/** Fit the room, including wall height, at the actual viewport aspect ratio. */
export function overviewPosition(aspect: number, fov = 42): [number, number, number] {
  const target = new Vector3().fromArray(OVERVIEW_TARGET);
  const direction = new Vector3(8, 7.6, 9).normalize();
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

import { Vector3, type Camera, type Object3D } from 'three';

const projected = new Vector3();
/** Keep visible labels bounded; do not pin offscreen agents onto the same edge. */
export function boundedLabelPosition(object: Object3D, camera: Camera, size: { width: number; height: number }): [number, number] {
  projected.setFromMatrixPosition(object.matrixWorld).project(camera);
  if (projected.z < -1 || projected.z > 1 || Math.abs(projected.x) > 1 || Math.abs(projected.y) > 1) return [-10000,-10000];
  const x = (projected.x + 1) * size.width / 2;
  const y = (1 - projected.y) * size.height / 2;
  const mx = Math.min(98, size.width / 2);
  const my = Math.min(24, size.height / 2);
  return [Math.max(mx, Math.min(size.width - mx, x)), Math.max(my, Math.min(size.height - my, y))];
}

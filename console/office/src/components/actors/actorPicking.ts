import { Box3, Mesh, SkinnedMesh, Vector3, type Object3D } from 'three';

/** One posed bounding box for picking, not thousands of skinned triangles per
 * pointer event. This changes hit testing only; source geometry/materials stay. */
export function prepareActorPicking(object: Object3D) {
  object.updateMatrixWorld(true);
  object.traverse((child) => {
    if (child instanceof SkinnedMesh) child.computeBoundingBox();
    if (child instanceof Mesh) child.raycast = () => {};
  });
  const bounds = new Box3().setFromObject(object).expandByScalar(2);
  const center = bounds.getCenter(new Vector3()).toArray() as [number, number, number];
  const size = bounds.getSize(new Vector3()).toArray() as [number, number, number];
  return { center, size };
}

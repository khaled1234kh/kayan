import { FrontSide, PlaneGeometry } from 'three';

/** Display normal is +Z here; Monitor mounts it toward the seated worker (-Z). */
export const DISPLAY_SIDE = FrontSide;
export const DISPLAY_SIZE = [0.56, 0.33] as const;
export const MONITOR = {
  width: 0.64, height: 0.4, depth: 0.05,
  baseZ: 0.225, tilt: 0.14,
} as const;
export function createDisplayGeometry() {
  return new PlaneGeometry(...DISPLAY_SIZE);
}

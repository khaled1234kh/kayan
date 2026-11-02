import { createContext, useContext, useMemo, useRef, type ReactNode, type RefObject } from 'react';
import type { Group } from 'three';

// Measured whole-scene label tests spent 6.58s/10.36s traversing detailed
// employees during orbit. Labels only need the enclosing static room/furniture
// as occluders. Physical monitor screens keep their normal GPU depth tests.
const OccluderContext = createContext<RefObject<Group> | null>(null);

export function OfficeLabelOcclusion({ children }: { children: ReactNode }) {
  const room = useRef<Group>(null);
  return <OccluderContext.Provider value={room}>{children}</OccluderContext.Provider>;
}

export function LabelOccluderGeometry({ children }: { children: ReactNode }) {
  const room = useContext(OccluderContext);
  return <group ref={room} name="label-occluders">{children}</group>;
}

export function useLabelOcclusionTargets() {
  const room = useContext(OccluderContext);
  return useMemo(() => room ? [room] : [], [room]);
}

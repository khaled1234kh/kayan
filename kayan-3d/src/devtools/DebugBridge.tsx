import { useEffect } from 'react';
import { useThree } from '@react-three/fiber';
import * as THREE from 'three';
import { useStore } from '../state/useStore';
import { tileToWorld } from '../components/office/Office';
import { EVENT_DEFS } from '../types/events';
import { buildAuditRows, buildSecurityEvidence } from '../audit/derive';
import { buildAuditCsv, buildAuditJson } from '../audit/exporters';
import { runComparison, stepSignature } from '../experiments/experimentRunner';
import { buildExperimentCsv, buildExperimentJson } from '../experiments/exporters';
import type { ExperimentResult } from '../experiments/experimentTypes';

/**
 * Development-only bridge.
 *
 * Exposes the store and a world→screen projection so automated checks can drive
 * real raycast clicks instead of calling component handlers directly, plus
 * read-only access to the audit and experiment exports. Stripped from production
 * builds by the `import.meta.env.DEV` guard in App.
 */
export function DebugBridge() {
  const { camera, size, gl, controls, scene } = useThree();

  useEffect(() => {
    const w = window as unknown as Record<string, unknown>;
    w.__kayanStore = useStore;
    w.__camera = camera;
    /** Dev-only camera framing helper, for close-up visual verification. */
    w.__focus = (tileX: number, tileZ: number) => {
      const [wx, wz] = tileToWorld(tileX, tileZ);
      camera.position.set(wx + 2.2, 1.9, wz + 2.6);
      const c = controls as unknown as { target?: THREE.Vector3; update?: () => void } | null;
      if (c && c.target) {
        c.target.set(wx, 1.0, wz);
        c.update?.();
      } else {
        camera.lookAt(wx, 1.0, wz);
      }
      camera.updateProjectionMatrix();
    };
    /**
     * Projects a tile coordinate (with optional world height `y` and extra
     * world-space depth offset `dz`) to canvas pixels.
     */
    w.__project = (tileX: number, tileZ: number, y = 0.4, dz = 0) => {
      const [wx, wz] = tileToWorld(tileX, tileZ);
      const v = new THREE.Vector3(wx, y, wz + dz).project(camera);
      return {
        x: ((v.x + 1) / 2) * size.width,
        y: ((1 - v.y) / 2) * size.height,
      };
    };
    /** Renderer stats, so draw-call claims are measured rather than asserted. */
    w.__stats = () => ({ calls: gl.info.render.calls, triangles: gl.info.render.triangles });
    /**
     * Dev-only scene introspection: material colours actually present in the
     * graph. Lets automated checks verify attire without guessing at lit pixels.
     */
    w.__meshColours = () => {
      const tally: Record<string, number> = {};
      scene.traverse((o) => {
        const m = (o as THREE.Mesh).material as THREE.MeshStandardMaterial | undefined;
        if (m && m.color && typeof m.color.getHexString === 'function') {
          const key = m.color.getHexString();
          tally[key] = (tally[key] ?? 0) + 1;
        }
      });
      return tally;
    };
    /**
     * Dev-only audit export access. Returns the exact strings the Export buttons
     * download, so automated checks can assert content without a file download.
     */
    w.__exportAudit = () => {
      const s = useStore.getState();
      const input = {
        events: s.events,
        messages: s.collaboration.messages,
        handoffs: s.collaboration.handoffs,
        actors: s.actors,
        tasks: s.tasks,
        generatedAt: new Date().toISOString(),
      };
      return {
        json: JSON.stringify(buildAuditJson(input)),
        csv: buildAuditCsv(input),
        eventCount: s.events.length,
      };
    };
    w.__auditRows = () =>
      buildAuditRows(useStore.getState().events, EVENT_DEFS).map((r) => ({
        id: r.eventId,
        time: r.time,
        type: r.event.type,
        actor: r.actor,
        target: r.target,
        result: r.result,
        category: r.category,
      }));
    w.__securityEvidence = () => buildSecurityEvidence(useStore.getState().events);
    /** Dev-only experiment harness access for automated checks. */
    w.__experiment = {
      runComparison: (opts: { runs?: number; seed?: string }) => runComparison(opts),
      stepSignature: () => stepSignature(),
      exportJson: (res: ExperimentResult) =>
        buildExperimentJson(res, new Date().toISOString()),
      exportCsv: (res: ExperimentResult) => buildExperimentCsv(res.runs),
    };
    /**
     * Arbitrary camera placement for automated stills. `__focus` only frames a
     * fixed 3/4 view; this lets a render script choose an explicit eye and target
     * (front-left, front, side, wide) and keep the orbit target in sync so
     * OrbitControls does not immediately override the position.
     */
    w.__setCamera = (px: number, py: number, pz: number, tx: number, ty: number, tz: number) => {
      camera.position.set(px, py, pz);
      const c = controls as unknown as {
        target?: THREE.Vector3;
        update?: () => void;
        minDistance?: number;
        maxDistance?: number;
      } | null;
      if (c && c.target) {
        // OrbitControls clamps to minDistance (7 by default), which silently
        // overrides any close inspection placement. Relax it for stills.
        if (c.minDistance !== undefined) c.minDistance = 0;
        if (c.maxDistance !== undefined) c.maxDistance = 200;
        c.target.set(tx, ty, tz);
        c.update?.();
      } else {
        camera.lookAt(tx, ty, tz);
      }
      camera.updateProjectionMatrix();
    };
    /**
     * Scene-load readiness. The five FBX actors are ~250 MB and stream in
     * asynchronously, so a still taken on a fixed timer catches a half-built
     * scene. Counts skinned meshes, which only exist once a model has loaded.
     */
    w.__sceneStats = () => {
      let skinned = 0;
      let bones = 0;
      scene.traverse((o) => {
        if ((o as THREE.SkinnedMesh).isSkinnedMesh) skinned++;
        if ((o as THREE.Bone).isBone) bones++;
      });
      return { skinned, bones };
    };
    return () => {
      delete w.__kayanStore;
      delete w.__project;
      delete w.__camera;
      delete w.__focus;
      delete w.__stats;
      delete w.__meshColours;
      delete w.__exportAudit;
      delete w.__auditRows;
      delete w.__securityEvidence;
      delete w.__experiment;
      delete w.__setCamera;
      delete w.__sceneStats;
    };
  }, [camera, size.width, size.height, gl, controls, scene]);

  return null;
}
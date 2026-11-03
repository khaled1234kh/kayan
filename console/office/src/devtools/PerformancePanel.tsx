import { useEffect, useRef, useState, type ProfilerOnRenderCallback } from 'react';
import { useFrame, useThree } from '@react-three/fiber';
import { useStore } from '../state/useStore';
import { summarizeFrames } from './performanceMetrics';
import type { Intersection, Object3D } from 'three';

type Mode = 'idle' | 'orbit-click';
type Capture = {
  mode: Mode; phase: string; started: number; checked_at: string; visible: boolean;
  frames: number[]; pointers: { down: number; move: number; wheel: number; click: number };
  store: { updates: number; actor_arrays: number; changed_actor_references: number };
  react: { scene_commits: number; actual_ms: number; max_commit_ms: number };
  longtasks: { supported: boolean; count: number; total_ms: number; max_ms: number };
  renderer: Record<string, unknown>; environment: Record<string, unknown>;
  draw_calls: number[]; triangles: number[];
  raycasts: Record<'scene_occlusion' | 'pointer_picking' | 'other_batches', { calls: number; total_ms: number; max_ms: number }>;
};
let capture: Capture | null = null;
const finishedEvent = 'kayan-performance-sample-finished';

export const recordSceneCommit: ProfilerOnRenderCallback = (_id, _phase, actualDuration) => {
  if (!capture) return;
  capture.react.scene_commits++;
  capture.react.actual_ms += actualDuration;
  capture.react.max_commit_ms = Math.max(capture.react.max_commit_ms, actualDuration);
};

/** Opt-in observation only: never changes frameloop, DPR, shadows or scene state. */
export function PerformanceSampler() {
  const { gl, frameloop, raycaster } = useThree();
  useFrame(() => {
    if (!capture) return;
    capture.frames.push(performance.now() - capture.started);
    capture.renderer = { pixel_ratio: gl.getPixelRatio(), frameloop,
      antialias: gl.getContext().getContextAttributes()?.antialias,
      shadows: gl.shadowMap.enabled, shadow_type: gl.shadowMap.type,
      geometries: gl.info.memory.geometries, textures: gl.info.memory.textures,
      note: 'Renderer.info counters sampled before the next draw; not a GPU timer.' };
    capture.draw_calls.push(gl.info.render.calls);
    capture.triangles.push(gl.info.render.triangles);
  });
  useEffect(() => {
    const single = raycaster.intersectObject;
    const batch = raycaster.intersectObjects;
    function measured<T>(kind: keyof Capture['raycasts'], action: () => T): T {
      const current = capture;
      if (!current) return action();
      const start = performance.now();
      try { return action(); } finally {
        const elapsed = performance.now() - start;
        const metric = current.raycasts[kind];
        metric.calls++; metric.total_ms += elapsed; metric.max_ms = Math.max(metric.max_ms, elapsed);
      }
    }
    raycaster.intersectObject = function<T extends Object3D>(object: Object3D, recursive?: boolean, target?: Intersection<T>[]) {
      return measured('pointer_picking', () => single.call(raycaster, object, recursive, target) as Intersection<T>[]);
    };
    raycaster.intersectObjects = function<T extends Object3D>(objects: Object3D[], recursive?: boolean, target?: Intersection<T>[]) {
      return measured(objects.some((object) => object.type === 'Scene' || object.name === 'label-occluders') ? 'scene_occlusion' : 'other_batches',
        () => batch.call(raycaster, objects, recursive, target) as Intersection<T>[]);
    };
    const stopStore = useStore.subscribe((state, previous) => {
      if (!capture) return;
      capture.store.updates++;
      if (state.actors !== previous.actors) {
        capture.store.actor_arrays++;
        capture.store.changed_actor_references += state.actors.filter((actor) =>
          actor !== previous.actors.find((old) => old.id === actor.id)).length;
      }
    });
    const hidden = () => { if (capture && document.hidden) capture.visible = false; };
    const count = (key: keyof Capture['pointers']) => () => { if (capture) capture.pointers[key]++; };
    const events = { pointerdown: count('down'), pointermove: count('move'), wheel: count('wheel'), click: count('click') };
    for (const [name, handler] of Object.entries(events)) gl.domElement.addEventListener(name, handler, { passive: true });
    document.addEventListener('visibilitychange', hidden);
    return () => {
      raycaster.intersectObject = single;
      raycaster.intersectObjects = batch;
      stopStore();
      document.removeEventListener('visibilitychange', hidden);
      for (const [name, handler] of Object.entries(events)) gl.domElement.removeEventListener(name, handler);
    };
  }, [gl, raycaster]);
  return null;
}

function range(values: number[]) {
  return values.length ? { min: Math.min(...values), max: Math.max(...values), mean: values.reduce((a,b) => a+b,0)/values.length } : null;
}

export function PerformancePanel() {
  const actorCount = useStore((state) => state.actors.length);
  const [running, setRunning] = useState<Mode | null>(null);
  const [phase, setPhase] = useState('baseline');
  const [samples, setSamples] = useState<Record<string, unknown>[]>([]);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const observer = useRef<PerformanceObserver | null>(null);
  useEffect(() => {
    const finished = (event: Event) => {
      setSamples((old) => [...old, (event as CustomEvent<Record<string, unknown>>).detail]);
      setRunning(null);
    };
    window.addEventListener(finishedEvent, finished);
    return () => {
      window.removeEventListener(finishedEvent, finished);
      if (timer.current) clearTimeout(timer.current);
      observer.current?.disconnect();
      capture = null;
    };
  }, []);

  function start(mode: Mode) {
    if (capture) return;
    const state = useStore.getState();
    if (state.actors.length !== 5) return;
    capture = { mode, phase, started: performance.now(), checked_at: new Date().toISOString(), visible: !document.hidden,
      frames: [], pointers: { down: 0, move: 0, wheel: 0, click: 0 },
      store: { updates: 0, actor_arrays: 0, changed_actor_references: 0 },
      react: { scene_commits: 0, actual_ms: 0, max_commit_ms: 0 },
      longtasks: { supported: false, count: 0, total_ms: 0, max_ms: 0 },
      renderer: {}, draw_calls: [], triangles: [],
      raycasts: { scene_occlusion: { calls: 0, total_ms: 0, max_ms: 0 },
        pointer_picking: { calls: 0, total_ms: 0, max_ms: 0 }, other_batches: { calls: 0, total_ms: 0, max_ms: 0 } },
      environment: { viewport: [window.innerWidth, window.innerHeight], device_pixel_ratio: window.devicePixelRatio,
        profile_revision: 'cohesive_workspace_office_v6',
        user_agent: navigator.userAgent, actors: state.actors.length, source: state.eventSourceKind,
        workflow_running: state.workflowRunning, connection: state.connection,
        conditions: 'Human must record model/GPU activity and visual state separately. No render acceptance implied.' } };
    if (typeof PerformanceObserver !== 'undefined' && PerformanceObserver.supportedEntryTypes?.includes('longtask')) {
      capture.longtasks.supported = true;
      observer.current = new PerformanceObserver((list) => {
        if (!capture) return;
        for (const entry of list.getEntries()) {
          capture.longtasks.count++;
          capture.longtasks.total_ms += entry.duration;
          capture.longtasks.max_ms = Math.max(capture.longtasks.max_ms, entry.duration);
        }
      });
      observer.current.observe({ type: 'longtask' });
    }
    setRunning(mode);
    timer.current = setTimeout(() => {
      const done = capture;
      if (!done) return;
      capture = null;
      observer.current?.disconnect();
      const duration = performance.now() - done.started;
      const report = { ...done, started: undefined, duration_ms: duration,
        summary: summarizeFrames(done.frames, duration, done.visible),
        draw_calls: range(done.draw_calls), triangles: range(done.triangles),
        input_check: done.mode === 'orbit-click' && done.pointers.move === 0 ? 'No canvas movement observed; repeat interaction sample.' :
          done.mode === 'idle' && Object.values(done.pointers).some((n) => n > 0) ? 'Canvas interaction observed; repeat idle sample.' : 'Check sample conditions manually.',
        authority: 'Opt-in browser-reported telemetry; no browser automation or screenshot. Not visual acceptance.' };
      window.dispatchEvent(new CustomEvent(finishedEvent, { detail: report }));
    }, 10000);
  }

  function download() {
    const blob = new Blob([JSON.stringify({ schema: 2, samples }, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `kayan-performance-${new Date().toISOString().replace(/[:.]/g, '-')}.json`;
    link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  return <details style={{ position: 'absolute', top: 76, left: 12, zIndex: 50, maxWidth: 370,
    background: '#101820', color: '#dce6ed', border: '1px solid #415565', padding: 10, fontSize: 12 }} open>
    <summary>Performance measurement · opt-in dev tool</summary>
    <p>Wait for assets. Keep this tab visible. For idle, move the pointer onto this panel before starting, then do not move it for 10s. Next capture 10s orbiting/clicking desks. Raycast timers are included; no renderer settings are changed.</p>
    <p>{actorCount} agents loaded. Use five agents for comparable samples; for an idle baseline, wait for the owned-lab assessment to complete.</p>
    <label>Sample phase <select value={phase} onChange={(e) => setPhase(e.target.value)} disabled={!!running}>
      <option value="baseline">Baseline</option><option value="after-measured-fix">After measured fix</option>
    </select></label>
    <p>{running ? `Recording ${running} for 10 seconds…` : 'Ready — captures start only when you click.'}</p>
    <button disabled={!!running || actorCount !== 5} onClick={() => start('idle')}>Capture idle</button>{' '}
    <button disabled={!!running || actorCount !== 5} onClick={() => start('orbit-click')}>Capture orbit/click</button>{' '}
    <button disabled={!!running || samples.length === 0} onClick={download}>Export JSON</button>
    {samples.map((sample, i) => <pre key={i} style={{ whiteSpace: 'pre-wrap' }}>{JSON.stringify({ mode: sample.mode, summary: sample.summary, input_check: sample.input_check }, null, 2)}</pre>)}
    <small>Canvas cadence and diagnostics only. This does not verify rendered correctness.</small>
  </details>;
}

import { Profiler, Suspense, useEffect, useState } from 'react';
import { Canvas } from '@react-three/fiber';
import { Html } from '@react-three/drei';
import { useStore } from './state/useStore';
import { ActorLayer } from './components/actors/ActorSeat';
import { Floor, FloorGrid, MeetingTable, TrustGateRack, Walls, tileToWorld } from './components/office/Office';
import { Partitions } from './components/office/Partitions';
import { Decor } from './components/office/Decor';
import { FloorLedPath } from './components/office/FloorLedPath';
import { CameraRig } from './components/office/CameraRig';
import SceneLighting from './components/scene/SceneLighting';
import { LabelOccluderGeometry, OfficeLabelOcclusion } from './components/scene/LabelOcclusion';
import { PerformancePanel, PerformanceSampler, recordSceneCommit } from './devtools/PerformancePanel';
import { LiveAgentPanel } from './components/ui/LiveAgentPanel';
import { EngagementOverview } from './components/ui/EngagementOverview';
import { PlanningPanel } from './components/ui/PlanningPanel';
import { apiUrl } from './transport';
import { TopBar, TrustGatePanel, Legend } from './components/ui/Panels';
import { TranscriptAudit } from './components/ui/TranscriptAudit';
import { agentDecision } from './security/agentDecision';

/** Live security console only. The original prepared office geometry is retained. */
export default function TrustGateApp() {
  const profiling = import.meta.env.DEV && new URLSearchParams(window.location.search).get('profile') === '1';
  const actors = useStore(s => s.actors);
  const running = useStore(s => s.workflowRunning);
  const selectedId = useStore(s => s.selectedActorId);
  const lastDecision = useStore(s => s.lastDecision);
  const collaboration = useStore(s => s.collaboration);
  const connection = useStore(s => s.connection);
  const reconnect = useStore(s=>s.reconnect);
  const selectActor = useStore(s => s.selectActor);
  const [presenting,setPresenting] = useState(false);
  const [planningOpen,setPlanningOpen] = useState(false);
  const [gate,setGate] = useState<'checking'|'available'|'unavailable'|'unknown'>('checking');
  useEffect(() => {
    const controller=new AbortController();
    async function check() { try { const response=await fetch(apiUrl.replace(/\/$/,'')+'/runtime/health',{signal:controller.signal});
      if(!response.ok) throw new Error('Console health unavailable');
      const value=await response.json();setGate(value.gate?.available===true ? 'available' : value.gate?.available===false ? 'unavailable' : 'unknown');
    } catch { if(!controller.signal.aborted) setGate('unknown'); } }
    void check();const timer=window.setInterval(()=>void check(),15000);
    return ()=>{controller.abort();window.clearInterval(timer);};
  },[]);
  const [auditOpen, setAuditOpen] = useState(false);
  const [viewReset, setViewReset] = useState(0);
  const [cameraFocus, setCameraFocus] = useState<[number, number, number] | null>(null);
  const actor = actors.find(a => a.id === selectedId) ?? null;
  const transcript = collaboration.toolTranscript ?? [];
  const decision = actor ? agentDecision(actor, transcript) : lastDecision;
  useEffect(() => {
    const nextAttention = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement | null;
      if (event.key.toLowerCase() !== 'n' || event.ctrlKey || event.metaKey || event.altKey ||
          target?.closest('input, textarea, select, [contenteditable="true"], dialog')) return;
      const state = useStore.getState();
      const attention = state.actors.filter(a => a.state === 'blocked' || a.state === 'awaiting_approval');
      if (!attention.length) return;
      const next = attention[(attention.findIndex(a => a.id === state.selectedActorId) + 1) % attention.length];
      state.selectActor(next.id);
      const [x,z] = tileToWorld(next.gridPosition.x, next.gridPosition.z);
      setCameraFocus([x,1,z]);
    };
    window.addEventListener('keydown', nextAttention);
    return () => window.removeEventListener('keydown', nextAttention);
  }, []);
  return <div className={`app ${presenting ? 'is-presenting' : ''}`}>
    <TopBar onAudit={() => setAuditOpen(true)} onPlanning={()=>setPlanningOpen(true)} onReconnect={reconnect} connection={connection} />
    <main className="stage"><EngagementOverview actors={actors} running={running} onSelect={selectActor} gate={gate} transcript={transcript} /><section className="viewport" aria-label="3D operations office">
      <Canvas shadows dpr={[1,2]} onPointerMissed={event => {
        if (event.target instanceof HTMLCanvasElement) selectActor(null);
      }}>
        {profiling && <PerformanceSampler />}
        <Profiler id="office-scene" onRender={recordSceneCommit}>
          <OfficeLabelOcclusion><color attach="background" args={['#0B0F14']} />
            <Suspense fallback={<Html center><div className="scene-loading">Loading prepared office assets…</div></Html>}>
              <CameraRig focusTarget={cameraFocus} onFocusArrived={() => setCameraFocus(null)} mode="presentation" resetKey={viewReset} />
              <SceneLighting />
              <LabelOccluderGeometry><Floor /><FloorGrid /><FloorLedPath /><Walls /><Partitions /><Decor /><MeetingTable />
                <TrustGateRack alerting={actors.some(a => a.state === 'blocked')} />
              </LabelOccluderGeometry>
              <ActorLayer actors={actors} selectedId={selectedId} onSelect={selectActor} />
            </Suspense>
          </OfficeLabelOcclusion>
        </Profiler>
      </Canvas>
      {profiling && <PerformancePanel />}

    </section><div className="sidebar">
      <LiveAgentPanel gateAvailable={gate==='available'} actor={actor} transcript={transcript} findings={collaboration.findings ?? []} decision={<TrustGatePanel decision={decision} scopeLabel={actor?.name ?? 'engagement latest'}
        emptyMessage={actor ? `No recorded authorization decision for ${actor.name}.` : undefined} />} />
    </div></main>
    <footer className="workspace-footer"><Legend /><button className="btn" type="button" aria-pressed={presenting} onClick={()=>setPresenting(v=>!v)}>Projector text</button><span className="orbit-hint">Drag to orbit · Scroll to zoom</span><button type="button" className="btn" onClick={() => {setCameraFocus(null);setViewReset(k=>k+1);}}>Reset view</button></footer>
    {planningOpen && <PlanningPanel onClose={()=>setPlanningOpen(false)} />}
    {auditOpen && <TranscriptAudit transcript={transcript} engagementId={collaboration.liveEngagementId} onClose={() => setAuditOpen(false)} />}
  </div>;
}

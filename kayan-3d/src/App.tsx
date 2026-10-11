import { useEffect, useState } from 'react';
import { Canvas } from '@react-three/fiber';
import { Suspense } from 'react';
import { useStore } from './state/useStore';
import { ActorLayer } from './components/actors/ActorSeat';
import { HandoffBeams } from './components/actors/HandoffBeams';
import { SpeechBubbles } from './components/actors/SpeechBubbles';
import { Floor, FloorGrid, MeetingTable, TrustGateRack, Walls, tileToWorld } from './components/office/Office';
import { Partitions } from './components/office/Partitions';
import { Decor } from './components/office/Decor';
import { FloorLedPath } from './components/office/FloorLedPath';
import { CameraRig } from './components/office/CameraRig';
import SceneLighting from './components/scene/SceneLighting';
import { DemoControls, EventFeed, Inspector, Legend, TopBar, TrustGatePanel } from './components/ui/Panels';
import { AuditView } from './components/ui/AuditView';
import { ExperimentView } from './components/ui/ExperimentView';
import { runComparison } from './experiments/experimentRunner';
import { fetchRunEvents } from './experiments/backendExperiment';
import { apiUrl } from './transport';
import type { KayanEvent } from './types/events';
import type { ExperimentResult } from './experiments/experimentTypes';
import { DebugBridge } from './devtools/DebugBridge';
import { OnboardingWizard } from './components/onboarding';
import { TaskBoard } from './components/tasks/TaskBoard';
import { TaskBoard3D } from './components/office/TaskBoard3D';

export default function App() {
  const actors = useStore((s) => s.actors);
  const tasks = useStore((s) => s.tasks);
  const events = useStore((s) => s.events);
  const workflowRunning = useStore((s) => s.workflowRunning);
  const selectedId = useStore((s) => s.selectedActorId);
  const lastDecision = useStore((s) => s.lastDecision);
  const collaboration = useStore((s) => s.collaboration);
  const selectActor = useStore((s) => s.selectActor);
  const runDemoOrder = useStore((s) => s.runDemoOrder);
  const replayDemo = useStore((s) => s.replayDemo);
  const canReplay = useStore((s) => s.source.history().length > 0);
  const eventSourceKind = useStore((s) => s.eventSourceKind);
  const connection = useStore((s) => s.connection);
  const experimentSourceIsMock = eventSourceKind === 'mock';
  const activeCompany = useStore((s) => s.activeCompany);
  const isCheckingActiveCompany = useStore((s) => s.isCheckingActiveCompany);
  const checkActiveCompany = useStore((s) => s.checkActiveCompany);

  const selectedActor = actors.find((a) => a.id === selectedId) ?? null;
  const selectedTask = selectedActor?.taskId
    ? tasks.find((t) => t.id === selectedActor.taskId) ?? null
    : null;

  // A blocked actor anywhere means the floor should surface the alert.
  const alerting = actors.some((a) => a.state === 'blocked');
  const [auditOpen, setAuditOpen] = useState(false);
  const [experimentOpen, setExperimentOpen] = useState(false);
  const [experiment, setExperiment] = useState<ExperimentResult | null>(null);
  /** When set, the audit view inspects one experiment run instead of the live run. */
  const [auditRunId, setAuditRunId] = useState<string | null>(null);
  /**
   * Backend mode: a trial's recorded events, fetched by their owning run so its
   * evidence is isolated from every other trial.
   */
  const [trialEvents, setTrialEvents] = useState<KayanEvent[] | null>(null);
  const [showOnboarding, setShowOnboarding] = useState(false);
  const [tasksOpen, setTasksOpen] = useState(false);
  /** Where the overview camera should ease to (N attention shortcut). */
  const [cameraFocus, setCameraFocus] = useState<[number, number, number] | null>(null);

  // N cycles the selection + camera focus to the next actor that needs
  // attention (awaiting approval or blocked). Ignored while typing so the
  // shortcut never rides keyboard input.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key.toLowerCase() !== 'n') return;
      if (e.metaKey || e.ctrlKey || e.altKey) return;
      const target = e.target as HTMLElement | null;
      if (
        target &&
        (target.tagName === 'INPUT' ||
          target.tagName === 'TEXTAREA' ||
          target.tagName === 'SELECT' ||
          target.isContentEditable)
      ) {
        return;
      }
      const s = useStore.getState();
      const attention = s.actors.filter(
        (a) => a.state === 'awaiting_approval' || a.state === 'blocked',
      );
      if (attention.length === 0) return;
      const idx = attention.findIndex((a) => a.id === s.selectedActorId);
      const next = attention[(idx + 1) % attention.length];
      s.selectActor(next.id);
      const [wx, wz] = tileToWorld(next.gridPosition.x, next.gridPosition.z);
      setCameraFocus([wx, 1.0, wz]);
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, []);

  const auditEvents =
    trialEvents ??
    (auditRunId && experiment ? experiment.runEvents[auditRunId] ?? events : events);

  /**
   * Opens one experiment trial in the audit view.
   *
   * In backend mode the trial's events come from the persisted run history, so
   * the audit shows exactly that trial and nothing else.
   */
  async function inspectRun(runId: string): Promise<void> {
    setAuditRunId(runId);
    if (eventSourceKind !== 'backend') return;
    try {
      const events = await fetchRunEvents(apiUrl, runId);
      setTrialEvents(events);
    } catch {
      // Fall back to the live stream rather than showing an empty audit.
      setTrialEvents(null);
    }
    setExperimentOpen(false);
    setAuditOpen(true);
  }

  // Check for active company on mount (backend mode only)
  useEffect(() => {
    if (eventSourceKind === 'backend') {
      checkActiveCompany();
    }
  }, [eventSourceKind, checkActiveCompany]);

  // Determine if we should show onboarding
  useEffect(() => {
    if (eventSourceKind === 'backend') {
      // In backend mode, show onboarding if no active company
      if (!isCheckingActiveCompany && !activeCompany) {
        setShowOnboarding(true);
      } else {
        setShowOnboarding(false);
      }
    } else {
      // In mock mode, always show the office (demo)
      setShowOnboarding(false);
    }
  }, [eventSourceKind, activeCompany, isCheckingActiveCompany]);

  const handleOnboardingComplete = (_companyId: string) => {
    setShowOnboarding(false);
    // The company_activated event will be received via WebSocket and handled by the reducer
    // But we can also proactively check
    checkActiveCompany();
  };

  const handleOnboardingCancel = () => {
    setShowOnboarding(false);
  };

  if (showOnboarding) {
    return (
      <div className="app onboarding-mode">
        <TopBar
          onAudit={() => {}}
          onExperiment={() => {}}
          onTasks={() => {}}
          connection={connection}
          sourceKind={eventSourceKind}
        />
        <main className="stage">
          <section className="viewport onboarding-viewport">
            <div className="onboarding-container">
              <OnboardingWizard onComplete={handleOnboardingComplete} onCancel={handleOnboardingCancel} />
            </div>
          </section>
        </main>
      </div>
    );
  }

  return (
    <div className="app">
      <TopBar
        onAudit={() => {
          setAuditRunId(null);
          setAuditOpen(true);
        }}
        onExperiment={() => setExperimentOpen(true)}
        onTasks={() => setTasksOpen(true)}
        connection={connection}
        sourceKind={eventSourceKind}
      />

      <main className="stage">
        <section className="viewport">
          <Canvas shadows dpr={[1, 2]} onPointerMissed={() => selectActor(null)}>
            <color attach="background" args={['#0F2438']} />
            <Suspense fallback={null}>
              <CameraRig focusTarget={cameraFocus} onFocusArrived={() => setCameraFocus(null)} />
              <SceneLighting />
              {import.meta.env.DEV && <DebugBridge />}
              <Floor />
              <FloorLedPath />
              <FloorGrid />
              {/* Zones removed — the reference floor is intentionally bare dark
                  concrete. These floor tints were laid out against the ORIGINAL
                  actor grid and were never realigned after the Phase C 2x2+1
                  reposition, so they no longer lined up with any desk, one of
                  them sat across the cross-aisle, and it masked the cyan arm of
                  the floor LED cross. The ZONES data stays in layout.ts, so floor
                  markings can be brought back with a correct layout if wanted. */}
              {/* <Zones /> */}
              <Walls />
              <Partitions />
              <MeetingTable />
              <TrustGateRack alerting={alerting} />
              <TaskBoard3D />
              <Decor />
              <ActorLayer
                actors={actors}
                selectedId={selectedId}
                onSelect={selectActor}
              />
              <HandoffBeams messages={collaboration.messages} />
              <SpeechBubbles collaboration={collaboration} actors={actors} />
            </Suspense>
          </Canvas>

          <div className="viewport-overlay-top">
            <DemoControls
              running={workflowRunning}
              canReplay={canReplay}
              onRun={runDemoOrder}
              onReplay={replayDemo}
            />
          </div>
          <div className="viewport-overlay-bottom">
            <Legend />
          </div>
        </section>

        <div className="sidebar">
          <Inspector
          actor={selectedActor}
          task={selectedTask}
          messages={collaboration.messages}
          handoffs={collaboration.handoffs}
          mailbox={selectedActor ? collaboration.mailboxes[selectedActor.id] ?? null : null}
          decision={lastDecision}
        />
          <TrustGatePanel decision={lastDecision} />
          <EventFeed events={events} />
        </div>
      </main>

      {experimentOpen && (
        <ExperimentView
          onClose={() => setExperimentOpen(false)}
          onInspectRun={(runId) => {
            if (eventSourceKind === 'backend') {
              void inspectRun(runId);
              return;
            }
            if (!experiment) setExperiment(runComparison({ runs: 10 }));
            setTrialEvents(null);
            setAuditRunId(runId);
            setExperimentOpen(false);
            setAuditOpen(true);
          }}
        />
      )}

      {auditOpen && (
        <AuditView
          events={auditEvents}
          messages={auditRunId && experimentSourceIsMock ? [] : collaboration.messages}
          handoffs={auditRunId && experimentSourceIsMock ? [] : collaboration.handoffs}
          actors={actors}
          tasks={tasks}
          onClose={() => {
            setAuditOpen(false);
            setAuditRunId(null);
            setTrialEvents(null);
          }}
        />
      )}

      {tasksOpen && <TaskBoard onClose={() => setTasksOpen(false)} />}
    </div>
  );
}
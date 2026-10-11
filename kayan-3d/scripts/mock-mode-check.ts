/**
 * Mock mode regression check.
 *
 * The default build must still be a fully working local prototype: the mock
 * source drives the store, the store drives the existing reducer, and the same
 * UI state comes out. This runs the real scripted order on a virtual `window`
 * shim, so `MockEventSource` is exercised unchanged.
 *
 * Run: npm run check:mock
 */
import { useStore } from '../src/state/useStore';

const results: string[] = [];
let failures = 0;

function check(label: string, condition: boolean, detail = ''): void {
  if (!condition) failures += 1;
  results.push(`${condition ? 'PASS' : 'FAIL'}  ${label}${detail ? ' :: ' + detail : ''}`);
}

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

async function main(): Promise<void> {
  // MockEventSource schedules with window.setTimeout; provide a timer shim.
  (globalThis as unknown as { window: Record<string, unknown> }).window = globalThis as never;

  const store = useStore.getState();
  check('default build selects the local mock source', store.eventSourceKind === 'mock', store.eventSourceKind);
  check('no backend connection is attempted in mock mode', store.connection === 'idle', store.connection);

  store.runDemoOrder();
  check('run sets the running flag', useStore.getState().workflowRunning === true);

  // The scripted order takes ~21s of workflow time.
  const deadline = Date.now() + 40_000;
  while (Date.now() < deadline && useStore.getState().workflowRunning) {
    await sleep(250);
  }

  const state = useStore.getState();
  const events = state.events;
  check('workflow completed', state.workflowRunning === false, `events=${events.length}`);

  // events are newest-first in the store.
  const types = events.map((e) => e.type);
  const has = (t: string) => types.includes(t);

  check('events were produced', events.length > 30, `${events.length} events`);
  check('collaboration messages rebuilt', state.collaboration.messages.length > 0, `${state.collaboration.messages.length}`);
  check('handoff produced', state.collaboration.handoffs.length > 0, `${state.collaboration.handoffs.length}`);
  check('mailboxes populated', Object.values(state.collaboration.mailboxes).some((m) => m.inbox.length > 0));
  check('TrustGate denial recorded', state.lastDecision?.decision === 'deny', `${state.lastDecision?.decision}/${state.lastDecision?.policy}`);
  check('denial event present', has('policy_denied'));
  check('blocked event present', has('blocked'));
  check('recovery event present', has('task_started'));
  check('order completion present', has('task_completed'));
  check('order task created and completed', state.tasks.some((t) => t.status === 'completed'), state.tasks.map((t) => `${t.id}:${t.status}`).join(' '));
  check('actors reach a terminal state', state.actors.every((a) => a.state === 'completed'), state.actors.map((a) => `${a.id}:${a.state}`).join(' '));

  // Replay is still available from the recorded history.
  const recorded = useStore.getState().source.history();
  check('history recorded for replay', recorded.length === events.length, `${recorded.length} vs ${events.length}`);
}

main()
  .then(() => {
    console.log(results.join('\n'));
    console.log(failures === 0 ? '\nMOCK MODE REGRESSION: PASS' : `\nMOCK MODE REGRESSION: ${failures} FAILURE(S)`);
    process.exit(failures === 0 ? 0 : 1);
  })
  .catch((err) => {
    console.log(results.join('\n'));
    console.error('\nMOCK MODE ERRORED:', err);
    process.exit(1);
  });
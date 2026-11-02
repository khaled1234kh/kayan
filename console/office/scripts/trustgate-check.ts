import assert from 'node:assert/strict';
import { TrustGateEventSource, parseTrustGateSnapshot } from '../src/transport/TrustGateEventSource';
import type { WebSocketLike } from '../src/transport/types';
import type { KayanEvent } from '../src/types/events';
import type { TrustGateSnapshot } from '../src/types/trustgate';
import { initialDomainState, reduce } from '../src/state/eventReducer';

let passed = 0;
function test(name: string, fn: () => void) { fn(); passed++; console.log(`PASS ${name}`); }
class Socket implements WebSocketLike {
  onopen: ((e: unknown) => void) | null = null;
  onmessage: ((e: { data: unknown }) => void) | null = null;
  onerror: ((e: unknown) => void) | null = null;
  onclose: ((e: unknown) => void) | null = null;
  sent: string[] = [];
  send(data: string) { this.sent.push(data); }
  close() { this.onclose?.({}); }
  deliver(snapshot: TrustGateSnapshot) { this.onmessage?.({ data: JSON.stringify({ type: 'engagement_update', data: snapshot }) }); }
}
function snapshot(revision = 1): TrustGateSnapshot {
  return {
    protocol_version: 1, session_id: 'session1', revision, engagement_id: 'eng1', status: 'active', target: 'http://127.0.0.1:8888',
    agents: [{ agent_id: 'recon1', role: 'recon_agent', status: 'working', current_task: 'port_scan', task_id: 'tool1', activity: 'Executing port_scan', findings_count: 0 }],
    transcript: [{ id: 'entry1', timestamp: 100, agent_id: 'recon1', agent_role: 'recon_agent', kind: 'tool_started', content: 'Executing port_scan', task_id: 'tool1' }],
  };
}
function harness() {
  const sockets: Socket[] = [], urls: string[] = [], events: KayanEvent[] = [], statuses: boolean[] = [];
  const timers = new Map<number, () => void>(); let timer = 0;
  const source = new TrustGateEventSource({ apiUrl: 'http://127.0.0.1:8001/', maxRetries: 2,
    webSocketFactory: (url) => { urls.push(url); const socket = new Socket(); sockets.push(socket); return socket; },
    setTimeoutFn: (fn) => { timers.set(++timer, fn); return timer; }, clearTimeoutFn: (id) => { timers.delete(id); },
  });
  source.subscribe((e) => events.push(e)); source.subscribeStatus((s) => statuses.push(s)); source.connect();
  return { source, sockets, urls, events, statuses, timers, tick: () => { const item = timers.entries().next().value!; timers.delete(item[0]); item[1](); } };
}
function fold(events: KayanEvent[]) { return events.reduce(reduce, initialDomainState()); }

test('reject malformed, generic and unsupported protocol frames', () => {
  for (const raw of ['broken', null, { kind: 'command' }, { type: 'engagement_update', data: { ...snapshot(), protocol_version: 2 } },
    { type: 'engagement_update', data: { ...snapshot(), agents: [{ role: 'recon_agent' }] } }]) assert.equal(parseTrustGateSnapshot(raw), null);
});
test('connect only to console /ws and send no legacy commands', () => {
  const h = harness(); assert.equal(h.urls[0], 'ws://127.0.0.1:8001/ws');
  assert.throws(() => h.source.runOrder(), /Python orchestrator/); assert.deepEqual(h.sockets[0].sent, []); h.source.disconnect();
});
test('late snapshot recovers current task and actual transcript without fabricated messages', () => {
  const h = harness(); h.sockets[0].deliver(snapshot()); const state = fold(h.events);
  assert.equal(state.actors.find((a) => a.id === 'ai-manager')?.currentTask, 'port_scan');
  assert.equal(state.tasks[0].title, 'port_scan'); assert.equal(state.collaboration.toolTranscript?.[0].content, 'Executing port_scan');
  assert.deepEqual(state.collaboration.messages, []); h.source.disconnect();
});
test('repeated and older revisions are ignored', () => {
  const h = harness(); h.sockets[0].deliver(snapshot(2)); const n = h.events.length;
  h.sockets[0].deliver(snapshot(2)); h.sockets[0].deliver(snapshot(1)); assert.equal(h.events.length, n); h.source.disconnect();
});
test('reconnect recovers missed entries once and ignores stale socket', () => {
  const h = harness(); h.sockets[0].deliver(snapshot()); const stale = h.sockets[0].onmessage;
  h.sockets[0].close(); h.tick(); h.sockets[1].onopen?.({}); const next = snapshot(3);
  next.transcript!.push({ ...next.transcript![0], id: 'entry2', kind: 'tool_result', content: 'actual output' });
  h.sockets[1].deliver(next); stale?.({ data: JSON.stringify({ type: 'engagement_update', data: snapshot(99) }) });
  assert.equal(h.events.filter((e) => e.type === 'trustgate_activity').length, 2);
  assert.equal(fold(h.events).collaboration.toolTranscript?.length, 2); h.source.disconnect();
});
test('same revision reconnect restores workflow status', () => {
  const h = harness(); h.sockets[0].deliver(snapshot()); h.sockets[0].close(); h.tick(); h.sockets[1].deliver(snapshot());
  assert.equal(h.statuses[h.statuses.length - 1], true); h.source.disconnect();
});
test('backend restart clears stale actors and task state', () => {
  const h = harness(); h.sockets[0].deliver(snapshot()); h.sockets[0].deliver({ protocol_version: 1, session_id: 'new-process', revision: 0, status: 'waiting' });
  const state = fold(h.events); assert.equal(state.tasks.length, 0); assert.equal(state.collaboration.toolTranscript?.length, 0);
  assert(state.actors.every((a) => a.state === 'idle')); h.source.disconnect();
});
test('completed operation clears current task', () => {
  const h = harness(); h.sockets[0].deliver(snapshot()); const next = snapshot(2);
  next.agents![0] = { ...next.agents![0], status: 'completed', current_task: null, task_id: null }; next.status = 'completed';
  h.sockets[0].deliver(next); const actor = fold(h.events).actors.find((a) => a.id === 'ai-manager')!;
  assert.equal(actor.state, 'completed'); assert.equal(actor.taskId, null); assert.equal(actor.currentTask, null); h.source.disconnect();
});
test('real authorization denial updates the security panel and blocked seat', () => {
  const h = harness(); const next = snapshot(); next.agents![0].status = 'blocked';
  next.transcript!.push({ ...next.transcript![0], id: 'denied', kind: 'authorization_decision', decision: 'DENY', content: 'Denied by policy', reason: 'out of scope', tool_name: 'scan', target: '127.0.0.2', audit_entry_id: 'audit1' });
  h.sockets[0].deliver(next); const state = fold(h.events);
  assert.equal(state.security.lastDecision?.decision, 'deny'); assert.equal(state.security.lastDecision?.reason, 'out of scope');
  assert.equal(state.actors.find((a) => a.id === 'ai-manager')?.state, 'blocked'); h.source.disconnect();
});
test('unknown backend role does not occupy or change a seat', () => {
  const h = harness(); const next = snapshot(); next.agents![0].role = 'unknown'; h.sockets[0].deliver(next);
  assert(fold(h.events).actors.every((a) => a.state === 'idle')); h.source.disconnect();
});
test('all four backend roles map to distinct desks', () => {
  const h = harness(); const next = snapshot(); next.agents = ['recon_agent','webapp_agent','network_agent','reporting_agent'].map((role, i) => ({ ...next.agents![0], role, agent_id: String(i) }));
  h.sockets[0].deliver(next); assert.equal(fold(h.events).actors.filter((a) => a.state === 'working').length, 4); h.source.disconnect();
});
test('explicit disconnect cancels reconnect and notifies status', () => {
  const h = harness(); h.sockets[0].close(); assert.equal(h.timers.size, 1); h.source.disconnect();
  assert.equal(h.timers.size, 0); assert.equal(h.source.getConnectionState(), 'disconnected');
});
test('manual reconnect after the bounded retry budget recovers the saved snapshot',()=>{
  const h=harness();h.sockets[0].close();h.tick();h.sockets[1].close();h.tick();h.sockets[2].close();
  assert.equal(h.source.getConnectionState(),'disconnected');assert.equal(h.timers.size,0);
  h.source.connect();assert.equal(h.sockets.length,4);h.sockets[3].onopen?.({});h.sockets[3].deliver(snapshot());
  assert.equal(h.source.getConnectionState(),'connected');assert.equal(fold(h.events).collaboration.toolTranscript?.length,1);h.source.disconnect();
});
console.log(`${passed} TrustGate transport/reducer checks passed`);

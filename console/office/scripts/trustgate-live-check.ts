/** Read-only integration check against a running console with an observed engagement. */
import assert from 'node:assert/strict';
import { TrustGateEventSource } from '../src/transport/TrustGateEventSource';
import { initialDomainState, reduce } from '../src/state/eventReducer';
import type { TrustGateSnapshot } from '../src/types/trustgate';
import { agentDecision } from '../src/security/agentDecision';

const source = new TrustGateEventSource({ apiUrl: process.env.KAYAN_API_URL ?? 'http://127.0.0.1:8001' });
let state = initialDomainState();
let snapshot: TrustGateSnapshot | undefined;
const timeout = setTimeout(() => { console.error('No populated TrustGate snapshot received'); source.disconnect(); process.exitCode = 1; }, 10000);
source.subscribe((event) => {
  state = reduce(state, event);
  if (event.type !== 'trustgate_snapshot') return;
  snapshot = event.payload?.snapshot as TrustGateSnapshot;
  if (!snapshot.engagement_id || !snapshot.transcript?.length) return;
  queueMicrotask(() => {
    clearTimeout(timeout); source.disconnect();
    assert.equal(state.collaboration.toolTranscript?.length, snapshot!.transcript!.length);
    assert.equal(state.actors.filter((actor) => actor.state === 'completed').length,
      snapshot!.agents!.filter((agent) => agent.status === 'completed').length);
    assert.equal(state.collaboration.messages.length, 0);
    const scopedDecisions: Record<string, string | null> = {};
    for (const actor of state.actors.filter(actor => actor.backendAgentId)) {
      const own = snapshot!.transcript!.filter(entry => entry.agent_id === actor.backendAgentId &&
        entry.kind === 'authorization_decision' && ['ALLOW','DENY'].includes(entry.decision ?? ''));
      const decision = agentDecision(actor, state.collaboration.toolTranscript ?? []);
      assert.equal(decision?.action ?? null, own.at(-1)?.tool_name ?? null);
      if (decision) assert.equal(decision.subject, actor.name);
      scopedDecisions[actor.name] = decision?.action ?? null;
    }
    console.log(JSON.stringify({ engagement_id: snapshot!.engagement_id, status: snapshot!.status,
      projected_agents: snapshot!.agents!.length, transcript_entries: state.collaboration.toolTranscript?.length,
      last_decision: state.security.lastDecision?.decision, scoped_decisions: scopedDecisions, source: 'real console WebSocket' }));
  });
});
source.connect();

import type { Actor, Task } from '../types';
import type { KayanEvent } from '../types/events';
import type { SecurityDecisionView } from '../security/policyTypes';
import { SEED_ACTORS } from '../data/actors';
import { TRUSTGATE_SEATS, type TrustGateSnapshot, type TrustGateTranscriptEntry, type TrustGateFinding } from '../types/trustgate';

export interface CollaborationState {
  toolTranscript?: TrustGateTranscriptEntry[];
  findings?: TrustGateFinding[];
  liveEngagementId?: string;
  messages: never[];
  handoffs: never[];
  mailboxes: Record<string, { currentTaskId: string | null }>;
  recent: never[];
}
export interface DomainState {
  actors: Actor[];
  tasks: Task[];
  companyTasks: never[];
  security: { lastDecision: SecurityDecisionView | null };
  collaboration: CollaborationState;
}
export function initialDomainState(): DomainState {
  return { actors: SEED_ACTORS.map(actor => ({ ...actor })), tasks: [], companyTasks: [],
    security: { lastDecision: null }, collaboration: { messages: [], handoffs: [], recent: [],
      mailboxes: Object.fromEntries(SEED_ACTORS.map(actor => [actor.id, { currentTaskId: null }])) } };
}
/** Project authoritative console snapshots only; no browser authorization or simulated business workflow. */
export function reduce(state: DomainState, event: KayanEvent): DomainState {
  const { payload } = event;
  switch (event.type) {
    case 'trustgate_snapshot': {
      const snapshot = payload?.snapshot as TrustGateSnapshot;
      const base = initialDomainState();
      const transcript = snapshot.transcript ?? [];
      let lastDecision: SecurityDecisionView | null = null;
      for (const entry of transcript) {
        if (entry.kind !== 'authorization_decision' || !['ALLOW', 'DENY'].includes(entry.decision ?? '')) continue;
        const actor = base.actors.find((a) => a.id === TRUSTGATE_SEATS[entry.agent_role]);
        lastDecision = {
          decision: entry.decision === 'ALLOW' ? 'allow' : 'deny',
          policy: entry.policy_id ?? 'TrustGate authorization', subject: actor?.name ?? entry.agent_role,
          action: entry.tool_name ?? '', resource: entry.target ?? '',
          reason: entry.reason ?? '', timestamp: entry.timestamp,
        };
      }
      for (const agent of snapshot.agents ?? []) {
        const actor = base.actors.find((a) => a.id === TRUSTGATE_SEATS[agent.role]);
        if (!actor) continue;
        actor.state = agent.status;
        actor.activity = agent.activity;
        actor.currentTask = agent.current_task;
        actor.modelTier = agent.model_tier;
        actor.modelName = agent.model_name;
        actor.executionEngine = agent.execution_engine ?? snapshot.execution_engine;
        actor.backendAgentId = agent.agent_id;
        actor.engagementId = snapshot.engagement_id;
        actor.taskId = agent.current_task ? agent.task_id ?? `${snapshot.engagement_id}:${agent.agent_id}` : null;
        base.collaboration.mailboxes[actor.id].currentTaskId = actor.taskId;
        if (actor.taskId) base.tasks.push({
          id: actor.taskId, title: agent.current_task ?? '', subject: snapshot.target ?? '',
          status: agent.status === 'blocked' ? 'blocked' : 'open', participants: [actor.id], artifacts: [], cost: 0,
        });
      }
      return { ...base, security: { lastDecision }, collaboration: {
        ...base.collaboration, toolTranscript: transcript, findings: snapshot.findings ?? [], liveEngagementId: snapshot.engagement_id,
      } };
    }

    default: return state;
  }
}

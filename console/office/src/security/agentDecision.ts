import type { Actor } from '../types';
import type { TrustGateTranscriptEntry } from '../types/trustgate';
import type { SecurityDecisionView } from './policyTypes';

/** No role/name/global fallback: a selected session must show its own decision. */
export function agentDecision(actor: Actor | null, transcript: TrustGateTranscriptEntry[]): SecurityDecisionView | null {
  if (!actor?.backendAgentId || !actor.engagementId) return null;
  let latest: TrustGateTranscriptEntry | undefined;
  for (const entry of transcript) {
    if (entry.agent_id !== actor.backendAgentId ||
      (entry.engagement_id !== undefined && entry.engagement_id !== actor.engagementId) ||
      entry.kind !== 'authorization_decision' || !['ALLOW', 'DENY'].includes(entry.decision ?? '')) continue;
    if (!latest || (entry.seq !== undefined && latest.seq !== undefined ? entry.seq >= latest.seq : entry.timestamp >= latest.timestamp)) latest = entry;
  }
  return latest ? { decision: latest.decision === 'ALLOW' ? 'allow' : 'deny',
    auditEntryId: latest.audit_entry_id, policy: latest.policy_id ?? 'TrustGate authorization', subject: actor.name,
    action: latest.tool_name ?? '', resource: latest.target ?? '', reason: latest.reason ?? '', timestamp: latest.timestamp } : null;
}

/** Wire contract of the TrustGate console on :8001, independent of the old server. */
export interface TrustGateTranscriptEntry {
  [key: string]: unknown;
  seq?: number;
  engagement_id?: string;
  type?: string;
  model_tier?: 'A' | 'B' | 'C';
  id: string;
  timestamp: number;
  agent_id: string;
  agent_role: string;
  kind: string;
  content: string;
  task_id?: string | null;
  tool_name?: string;
  target?: string;
  decision?: string;
  reason?: string;
  policy_id?: string | null;
  audit_entry_id?: string;
  truncated?: boolean;
}

export interface TrustGateAgent {
  model_tier?: 'A' | 'B' | 'C';
  model_name?: string;
  execution_engine?: string;
  agent_id: string;
  role: string;
  status: 'idle' | 'working' | 'blocked' | 'completed';
  current_task: string | null;
  task_id: string | null;
  activity: string;
  findings_count: number;
}

export interface TrustGateSnapshot {
  protocol_version: 1;
  session_id: string;
  revision: number;
  engagement_id?: string;
  status: string;
  target?: string;
  execution_engine?: string;
  agents?: TrustGateAgent[];
  transcript?: TrustGateTranscriptEntry[];
  findings?: TrustGateFinding[];
  denials?: Record<string, unknown>[];
  restoration?: {records_only?:boolean;notice?:string;interrupted?:boolean};
}

export interface TrustGateFinding {
  id?: string;
  type: string;
  agent: string;
  mitre?: string;
  target?: string;
  data?: Record<string, unknown>;
}

/** Backend role to stable scene ID; no agent identity is inferred from tool text. */
export const TRUSTGATE_SEATS: Record<string, string> = {
  planner_agent: 'planner', recon_agent: 'ai-manager', webapp_agent: 'ai-sales',
  network_agent: 'ai-ops', reporting_agent: 'human',
};

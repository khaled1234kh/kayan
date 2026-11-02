/** Read-only projection of a decision already made by the Rust/Cedar service. */
export interface SecurityDecisionView {
  auditEntryId?: string; decision: 'allow' | 'deny'; policy: string; subject: string; action: string;
  resource: string; reason: string; timestamp: number;
}

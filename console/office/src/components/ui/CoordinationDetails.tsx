import { coverageRoleLabel } from './CoverageDetails';

export interface OutcomeReview {
  after_role: string;
  next_role: string;
  status: 'accepted' | 'degraded';
  priority_tools: string[];
  evidence_ids: string[];
  coverage_action: string;
  rationale: string;
}

export function parseOutcomeReview(value: unknown): OutcomeReview | null {
  if (!value || typeof value !== 'object') return null;
  const item = value as Record<string, unknown>;
  if (!['accepted', 'degraded'].includes(String(item.status))) return null;
  for (const key of ['after_role', 'next_role', 'coverage_action', 'rationale']) if (typeof item[key] !== 'string') return null;
  for (const key of ['priority_tools', 'evidence_ids']) {
    if (!Array.isArray(item[key]) || !(item[key] as unknown[]).every(v => typeof v === 'string')) return null;
  }
  return item as unknown as OutcomeReview;
}

export function CoordinationDetails({ reviews }: { reviews: OutcomeReview[] }) {
  if (!reviews.length) return null;
  return <details className="coordination-reviews"><summary>Planner outcome reviews ({reviews.length})</summary>
    <p className="muted">Model-generated operational explanations. Execution records and coverage remain authoritative.</p>
    {reviews.map((review, index) => <article key={index} className="session-entry">
      <strong>{coverageRoleLabel(review.after_role)} → {review.next_role === 'reporting_agent' ? 'Reporting' : coverageRoleLabel(review.next_role)}</strong>
      <p>{review.status === 'degraded' ? 'Review degraded · validated plan retained' : 'Review accepted'}</p>
      <p>{review.rationale}</p>
      <p>Next priorities: {review.priority_tools.join(', ') || 'Evidence reporting only'}</p>
      <p>{review.coverage_action === 'disclose_partial' ? 'Disclose incomplete coverage; keep existing limits.' : 'Continue within existing limits.'}</p>
      <small>Evidence references: {review.evidence_ids.join(', ')}</small>
    </article>)}
  </details>;
}

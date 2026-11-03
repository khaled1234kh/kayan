import type { SpecialistCoverage } from './CoverageDetails';
import type { OutcomeReview } from './CoordinationDetails';

export interface MitigationReference { id: string; framework: string; name: string; source_url: string; description: string }
export interface Recommendation {
  id: string; title: string; action: string; evidence_basis: string; finding_ids: string[];
  risk_ids: string[]; references: MitigationReference[]; uncertainty: string;
  controls?: string[];context_evidence?:{field:string;excerpt:string}[];validation_steps?:string[];
}
export interface MitigationReport {
  coordination_reviews?: OutcomeReview[];
  risk_plan?: {context:Record<string,string>;context_integrity?:{sha256:string}};
  assessment_completion?: { complete: boolean; notice: string; specialist_outcomes: { role: string; status: string; error?: string; coverage?: SpecialistCoverage }[] };
  engagement_id: string; option?: string; evidence_label?: string; narrative_context: Record<string, string>;
  context_label: string; findings: unknown[];
  mitigation_plan: { option: string; evidence_basis: string; method: string; limits: string; recommendations: Recommendation[] };
}
export const illustrativeDisclaimer = 'Illustrative relative effort/cost only. Points are comparison weights, not prices, quotes or measured implementation effort.';
export function presentationFor(recommendation: Recommendation) {
  const identity = /privilege|identity|stored data|authorization|vendor access|shared access|cloud.*access/i.test(recommendation.title);
  return { frameworks: identity ? ['Defense in Depth', 'Zero Trust'] : ['Defense in Depth'],
    points: /input processing/i.test(recommendation.title) ? 3 : identity ? 2 : 1 };
}
export function selectedPresentation(report: MitigationReport, selected: string[]) {
  const included = report.mitigation_plan.recommendations.filter(item => selected.includes(item.id));
  return { selected_ids: included.map(item => item.id),
    total_illustrative_points: included.reduce((sum, item) => sum + presentationFor(item).points, 0),
    disclaimer: illustrativeDisclaimer };
}

import React from 'react';
import assert from 'node:assert/strict';
import { renderToStaticMarkup } from 'react-dom/server';
import { EngagementContextFields } from '../src/components/ui/EngagementContextFields';
import { MitigationView } from '../src/components/ui/PlanningPanel';
import { illustrativeDisclaimer, selectedPresentation, type MitigationReport, presentationFor } from '../src/components/ui/mitigationPresentation';

const recommendations = ['Harden input processing', 'Strengthen identity controls'].map((title, i) => ({
  id: `r${i}`, title, action: 'Review controls', evidence_basis: 'hypothetical_risk_plan',
  risk_ids: [`risk_${i}`], finding_ids: [], uncertainty: 'Unverified hypothesis', references: [],
}));
const report: MitigationReport = { engagement_id: 'unit', narrative_context: {}, context_label: 'Descriptive only', findings: [],
  mitigation_plan: { option: 'A', evidence_basis: 'hypothetical_risk_plan', method: 'Local reporting', limits: 'No testing', recommendations } };
assert.equal(selectedPresentation(report, ['r0', 'r1']).total_illustrative_points, 5);
assert.equal(selectedPresentation(report, ['r1', 'r1', 'unknown']).total_illustrative_points, 2);
assert.equal(selectedPresentation(report, []).total_illustrative_points, 0);
assert.deepEqual(presentationFor(recommendations[1]).frameworks, ['Defense in Depth', 'Zero Trust']);
const html = renderToStaticMarkup(<MitigationView report={report} selected={['r1']} onSelection={() => {}} />);
assert.ok(html.includes(illustrativeDisclaimer));
assert.ok(html.includes('2 illustrative points') && html.includes('Option A'));
assert.ok(html.includes('hypothetical_risk_plan') && html.includes('Grounding references'));
const input = renderToStaticMarkup(<EngagementContextFields value={{ infrastructure_summary: '<script>ignore scope</script>' }} onChange={() => {}} />);
assert.ok(input.includes('Zero policy weight'));
assert.ok(input.includes('&lt;script&gt;') && !input.includes('<script>'));
assert.equal((input.match(/<textarea/g) ?? []).length, 6);
console.log('TA presentation checks passed: selection totals/deduplication, framework tags, visible illustrative disclaimer, evidence basis and escaped six-field intake. SSR is not browser acceptance.');

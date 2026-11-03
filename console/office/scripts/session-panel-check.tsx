/** Rendered HTML assertions, explicitly not a screenshot or WebGL visual check. */
import assert from 'node:assert/strict';
import { renderToStaticMarkup } from 'react-dom/server';
import { LiveAgentPanel, decisionTone } from '../src/components/ui/LiveAgentPanel';
import { SEED_ACTORS } from '../src/data/actors';
import type { TrustGateTranscriptEntry } from '../src/types/trustgate';
import { agentDecision } from '../src/security/agentDecision';
import { TrustGatePanel } from '../src/components/ui/Panels';

const actor = { ...SEED_ACTORS.find((a) => a.id === 'ai-sales')!, modelTier: 'A' as const,
  backendAgentId: 'webapp1', engagementId: 'eng1', currentTask: 'sql_injection_test', state: 'working' as const };
const entry: TrustGateTranscriptEntry = { id: '1', seq: 1, timestamp: 100, agent_id: 'webapp1', agent_role: 'webapp_agent',
  kind: 'authorization_decision', content: 'DENY: port_scan — forbidden', decision: 'DENY', result: { actual: '<script>never execute</script>' } };
const html = renderToStaticMarkup(<LiveAgentPanel actor={actor} transcript={[entry]} findings={[
  { id: 'finding1', type: 'xss', agent: 'webapp_agent', mitre: 'T1190' },
]} />);
assert(html.includes('Web-App Agent') && html.includes('Tier A'));
assert(html.includes('sql_injection_test'));
assert(html.includes('<details') && !html.includes('<details open'));
assert(html.includes('is-denied') && html.includes('T1190'));
assert(html.includes('&lt;script&gt;') && !html.includes('<script>never execute'));
assert.equal(decisionTone({ ...entry, decision: 'ALLOW' }), 'is-allowed');
assert.equal(decisionTone(entry), 'is-denied');
const idle = renderToStaticMarkup(<LiveAgentPanel actor={SEED_ACTORS[0]} transcript={[]} findings={[]} />);
assert(idle.includes('Idle — no live session.') && idle.includes('No active task'));
assert.equal(new Set(SEED_ACTORS.map((a) => `${a.gridPosition.x}:${a.gridPosition.z}`)).size, 5);
const network = { ...SEED_ACTORS.find(a => a.id === 'ai-ops')!, backendAgentId: 'network1', engagementId: 'eng1' };
const networkEntry = { ...entry, id: 'network-auth', seq: 2, agent_id: 'network1', agent_role: 'network_agent', tool_name: 'port_scan', engagement_id: 'eng1' };
const reportingEntry = { ...entry, id: 'report-auth', seq: 3, timestamp: 300, agent_id: 'reporting1', agent_role: 'reporting_agent', tool_name: 'write_report' };
const scoped = agentDecision(network, [networkEntry, reportingEntry]);
assert.equal(scoped?.action, 'port_scan');
assert.equal(scoped?.subject, 'Network Agent');
const scopedHtml = renderToStaticMarkup(<TrustGatePanel decision={scoped} scopeLabel={network.name} />);
assert(scopedHtml.includes('port_scan') && scopedHtml.includes('Network Agent'));
assert(!scopedHtml.includes('write_report') && !scopedHtml.includes('Reporting Agent'));
assert.equal(agentDecision(network, [reportingEntry]), null);
assert.equal(agentDecision(network, [{ ...networkEntry, engagement_id: 'old-engagement' }]), null);
assert.equal(agentDecision({ ...network, backendAgentId: undefined }, [networkEntry]), null);
assert.equal(agentDecision(network, [networkEntry, { ...networkEntry, seq: 1, tool_name: 'stale_action' }])?.action, 'port_scan');
console.log('PASS selected-agent TrustGate decision isolation, missing-decision empty state and stale-engagement rejection');
console.log('PASS session panel: role/tier, actual task, collapsed raw detail, allow/deny classes, escaped output, MITRE findings, explicit idle, five distinct workstations');

const planner = { ...SEED_ACTORS.find(a => a.id === 'planner')!, backendAgentId: 'p1', engagementId: 'eng1',
  modelTier: 'A' as const, activity: 'Network completed; preparing Reporting', currentTask: 'Coordinating assessment' };
const plannerHtml = renderToStaticMarkup(<LiveAgentPanel actor={planner} transcript={[]} findings={[
  {id:'f1',type:'xss',agent:'webapp_agent',mitre:'T1190'}
]} />);
assert(plannerHtml.includes('Network completed; preparing Reporting'));
assert(plannerHtml.includes('Assessment findings') && plannerHtml.includes('webapp_agent') && plannerHtml.includes('T1190'));
assert(plannerHtml.includes('Coordinator only'));

const coverage={complete:false,stop_reason:'action_budget',untested_tools:['directory_traversal'],successful_tools:['xss_test'],
  tool_errors:[{tool:'http_probe',error:'<script>failure</script>'}],verification_issues:[{tool:'xss_test',reason:'Not reproduced'}]};
const covered=renderToStaticMarkup(<LiveAgentPanel actor={planner} transcript={[{...entry,agent_role:'planner_agent',agent_id:'p1',
  kind:'specialist_outcome',specialist_outcome:{role:'webapp_agent',coverage}}]} findings={[]}/>);
assert(covered.includes('Assessment coverage limits') && covered.includes('directory_traversal') && covered.includes('action budget'));
assert(covered.includes('Execution error') && covered.includes('Verification issue'));
assert(covered.includes('&lt;script&gt;failure') && !covered.includes('<script>failure'));
const specialistCoverage=renderToStaticMarkup(<LiveAgentPanel actor={actor} transcript={[{...entry,kind:'specialist_coverage',coverage}]} findings={[]}/>);
assert(specialistCoverage.includes('Assessment coverage limits') && specialistCoverage.includes('directory_traversal'));
const legacy=renderToStaticMarkup(<LiveAgentPanel actor={planner} transcript={[entry]} findings={[]}/>);
assert(!legacy.includes('Assessment coverage limits'));
console.log('PASS explicit catalogue gaps, execution/verification issues, escaped failure text and legacy-session compatibility');
const reviewed=renderToStaticMarkup(<LiveAgentPanel actor={planner} transcript={[{...entry,agent_role:'planner_agent',agent_id:'p1',kind:'coordination_review',
  review:{after_role:'recon_agent',next_role:'webapp_agent',status:'accepted',priority_tools:['xss_test'],coverage_action:'continue_bounded',
    evidence_ids:['outcome:recon_agent'],rationale:'Prioritize web inputs after the observed HTTP response'}}]} findings={[]}/>);
assert(reviewed.includes('Planner outcome reviews (1)') && reviewed.includes('Prioritize web inputs') && reviewed.includes('outcome:recon_agent'));
assert(reviewed.includes('Model-generated operational explanations') && reviewed.includes('Review accepted'));

/** Rendered HTML assertions, explicitly not a screenshot or WebGL visual check. */
import assert from 'node:assert/strict';
import { renderToStaticMarkup } from 'react-dom/server';
import { LiveAgentPanel, decisionTone, findingLabel } from '../src/components/ui/LiveAgentPanel';
import { SEED_ACTORS } from '../src/data/actors';
import type { TrustGateTranscriptEntry } from '../src/types/trustgate';
import { agentDecision } from '../src/security/agentDecision';
import { TrustGatePanel } from '../src/components/ui/Panels';
import { AdditionalVerifiedActions, AuditCountsView, ReportEvidence, ReportExecutionDetails, ReportSummaryCoverage, RoleObservationCounts, readSavedReport } from '../src/components/ui/ArchivedReport';

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

const reporter={...SEED_ACTORS.find(a=>a.id==='human')!,backendAgentId:'reporting1',engagementId:'eng1'};
const reporterView=renderToStaticMarkup(<LiveAgentPanel actor={reporter} transcript={[]} findings={[{id:'source-finding',type:'xss',agent:'webapp_agent',mitre:'T1190'}]}/>);
assert(reporterView.includes('Assessment findings')&&reporterView.includes('source-finding')&&reporterView.includes('webapp_agent'));
console.log('PASS Reporting shows assessment findings while preserving specialist ownership and IDs.');

assert.equal(findingLabel('command_injection'),'Command injection');assert.equal(findingLabel('xss'),'XSS');
assert(html.includes('tabindex="0"')&&html.includes('tabindex="-1"'));

const execution = {
  finish_reason: 'stop',
  usage: { input: 1250, output: 241, reasoning: 0, latency_s: 1.234 },
};
const selectedCloud = renderToStaticMarkup(<ReportExecutionDetails report={{ status: 'selected', ...execution }} />);
assert(selectedCloud.includes('<dt>Input tokens</dt><dd>1,250</dd>'));
assert(selectedCloud.includes('<dt>Output tokens</dt><dd>241</dd>'));
assert(selectedCloud.includes('<dt>Reasoning tokens</dt><dd>0</dd>'));
assert(selectedCloud.includes('<dt>Provider latency</dt><dd>1.234 s</dd>'));
assert(selectedCloud.includes('<dt>Finish reason</dt><dd>stop</dd>'));

const legacyCloud = renderToStaticMarkup(<ReportExecutionDetails report={{ status: 'selected', usage: { input: 32 } }} />);
assert(legacyCloud.includes('<dt>Input tokens</dt><dd>32</dd>'));
assert(!legacyCloud.includes('Reasoning tokens') && !legacyCloud.includes('Finish reason'));
const emptyCloud = renderToStaticMarkup(<ReportExecutionDetails report={{ status: 'selected' }} />);
assert(emptyCloud.includes('Provider metrics unavailable'));
const invalidCloud = renderToStaticMarkup(<ReportExecutionDetails report={{
  status: 'selected', usage: { input: -1, output: 1.5, reasoning: Number.NaN, latency_s: Infinity },
}} />);
assert(!invalidCloud.includes('<dt>') && invalidCloud.includes('Provider metrics unavailable'));
for (const status of ['local', 'degraded'] as const) {
  assert.equal(renderToStaticMarkup(<ReportExecutionDetails report={{ status, ...execution }} />), '');
}
console.log('PASS saved Reporting usage, genuine zero, partial legacy metadata and local fallback');

const digest = 'a'.repeat(64);
const makeSavedResponse = (tag: string) => Response.json({ status: 'local' }, { headers: { ETag: tag } });
assert.deepEqual(await readSavedReport(makeSavedResponse(`"${digest}"`)), { report: { status: 'local' }, digest });
assert.equal((await readSavedReport(makeSavedResponse(`W/"${digest}"`))).digest, undefined);
assert.equal((await readSavedReport(Response.json({ status: 'local' }))).digest, undefined);
await assert.rejects(readSavedReport(Response.json(
  { detail: 'Saved report failed verification against the current archive.' }, { status: 409 },
)), /failed verification/);
console.log('PASS saved Reporting response and exact export identity');

const partialSummary = renderToStaticMarkup(<ReportSummaryCoverage coverage={{
  admitted_occurrences: 2, covered_occurrences: 1, action_covered_occurrences: 1,
}} />);
assert(partialSummary.includes('Summary cites 1 of 2 admitted occurrences.'));
assert(partialSummary.includes('Observed-action excerpts cover 1 of 2.'));
const weakSummary = renderToStaticMarkup(<ReportSummaryCoverage coverage={{
  admitted_occurrences: 2, covered_occurrences: 2, action_covered_occurrences: 0,
}} />);
assert(weakSummary.includes('Summary cites 2 of 2 admitted occurrences.'));
assert(weakSummary.includes('Observed-action excerpts cover 0 of 2.'));
assert.equal(renderToStaticMarkup(<ReportSummaryCoverage />), '');
assert.equal(renderToStaticMarkup(<ReportSummaryCoverage coverage={{
  admitted_occurrences: 0, covered_occurrences: 0, action_covered_occurrences: 0,
}} />), '');
console.log('PASS Archived Reporting distinguishes occurrence coverage and observed-action coverage');

const observedAction = { id: 'E2.1', roles: ['mechanic'], statements: ['Exact source statement'] };
const supplementedEvidence = renderToStaticMarkup(<ReportEvidence source={{
  ...observedAction, selection_origin: 'verified_action_supplement',
}} />);
assert(supplementedEvidence.includes('Observed action added by KAYAN'));
assert(supplementedEvidence.includes('E2.1') && supplementedEvidence.includes('Exact source statement'));
assert(!renderToStaticMarkup(<ReportEvidence source={observedAction} />).includes('added by KAYAN'));
console.log('PASS Archived Reporting identifies deterministically appended action excerpts');

const archivedFinding = { technique: 'T1486', title: 'Test finding', occurrence: 'event-a', sources: [
  observedAction, { id: 'E2.2', roles: ['outcome'], statements: ['Outcome only'] },
] };
const additionalActions = renderToStaticMarkup(<AdditionalVerifiedActions report={{
  findings: [archivedFinding],
  summary_additional_actions: [
    { technique: 'T1486', occurrence: 'event-a', source_id: 'E2.1' },
    { technique: 'T1486', occurrence: 'event-b', source_id: 'E2.1' },
    { technique: 'T1486', occurrence: 'event-a', source_id: 'E2.2' },
  ],
}} />);
assert(additionalActions.includes('<summary>Other verified actions (1)</summary>'));
assert(additionalActions.includes('event-a') && additionalActions.includes('Exact source statement'));
assert(!additionalActions.includes('event-b') && !additionalActions.includes('Outcome only'));
assert.equal(renderToStaticMarkup(<AdditionalVerifiedActions report={{ findings: [archivedFinding] }} />), '');
console.log('PASS verified action disclosure only resolves same-occurrence mechanic evidence');

const auditCounts = renderToStaticMarkup(<AuditCountsView counts={{
  verified: 1, missing_entry: 3, ledger_invalid: 2, unavailable: 1,
}} />);
assert(auditCounts.includes('Match in verified ledger · 1'));
assert(auditCounts.includes('No matching audit entry · 3'));
assert(auditCounts.includes('Ledger verification failed · 2') && auditCounts.includes('Audit service unavailable · 1'));
assert(renderToStaticMarkup(<AuditCountsView counts={{}} />).includes('No captured decisions to check.'));
console.log('PASS archive audit view distinguishes confirmed, missing, invalid and unavailable audit evidence');

const roleCounts = renderToStaticMarkup(<RoleObservationCounts counts={{
  completed: 2, projected: 1, denied: 1, transcript_only: 3,
}} />);
assert(roleCounts.includes('Completed captures 2') && roleCounts.includes('Projected captures 1'));
assert(roleCounts.includes('Denied captures 1') && roleCounts.includes('Transcript-only records 3'));
assert(renderToStaticMarkup(<RoleObservationCounts />).includes('No retained observations'));
console.log('PASS Archived Reporting separates observed per-role counts from declared coverage');

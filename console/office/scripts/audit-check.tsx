import assert from 'node:assert/strict';
import { renderToStaticMarkup } from 'react-dom/server';
import { AuditEntries,TranscriptAudit,filterAuditEntries } from '../src/components/ui/TranscriptAudit';
const html = renderToStaticMarkup(<AuditEntries entries={[{id:'actual1',timestamp:100,agent_id:'web1',agent_role:'webapp_agent',
  kind:'authorization_decision',decision:'DENY',audit_entry_id:'audit1',content:'DENY: <script>injected</script>'}]} />);
assert(html.includes('webapp_agent') && html.includes('audit1') && html.includes('is-denied'));
assert(html.includes('&lt;script&gt;') && !html.includes('<script>injected'));
assert(html.includes('<details') && !html.includes('<details open'));
console.log('PASS actual transcript role/audit-ID rendering, denial color, escaped untrusted content and collapsed raw entries. SSR, not pixel acceptance.');

const records=[{id:'deny',timestamp:1,agent_id:'web1',agent_role:'webapp_agent',kind:'authorization_decision',decision:'DENY',audit_entry_id:'audit-denied',content:'Unsafe request'},
{id:'allow',timestamp:2,agent_id:'network1',agent_role:'network_agent',kind:'authorization_decision',decision:'ALLOW',audit_entry_id:'audit-allowed',content:'Allowed scan'},
{id:'tool',timestamp:3,agent_id:'web1',agent_role:'webapp_agent',kind:'tool_result',tool_name:'http_probe',content:'Observed result'}];
const original=JSON.stringify(records);
assert.deepEqual(filterAuditEntries(records,'all','deny','').map(e=>e.id),['deny']);
assert.deepEqual(filterAuditEntries(records,'webapp_agent','all','http_probe').map(e=>e.id),['tool']);
assert.deepEqual(filterAuditEntries(records,'all','all','AUDIT-ALLOWED').map(e=>e.id),['allow']);
assert.equal(filterAuditEntries(records,'network_agent','deny','').length,0);
assert.equal(JSON.stringify(records),original);
const empty=renderToStaticMarkup(<TranscriptAudit transcript={[]} onClose={()=>{}}/>);
assert(empty.includes('No session records yet')&&empty.includes('disabled=""')&&empty.includes('complete transcript'));
console.log('PASS combined role/decision/search filtering without source mutation and explicit empty/export state.');

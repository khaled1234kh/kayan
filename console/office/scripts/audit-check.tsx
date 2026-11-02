import assert from 'node:assert/strict';
import { renderToStaticMarkup } from 'react-dom/server';
import { AuditEntries } from '../src/components/ui/TranscriptAudit';
const html = renderToStaticMarkup(<AuditEntries entries={[{id:'actual1',timestamp:100,agent_id:'web1',agent_role:'webapp_agent',
  kind:'authorization_decision',decision:'DENY',audit_entry_id:'audit1',content:'DENY: <script>injected</script>'}]} />);
assert(html.includes('webapp_agent') && html.includes('audit1') && html.includes('is-denied'));
assert(html.includes('&lt;script&gt;') && !html.includes('<script>injected'));
assert(html.includes('<details') && !html.includes('<details open'));
console.log('PASS actual transcript role/audit-ID rendering, denial color, escaped untrusted content and collapsed raw entries. SSR, not pixel acceptance.');

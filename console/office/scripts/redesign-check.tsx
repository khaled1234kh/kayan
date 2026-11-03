import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {renderToStaticMarkup} from 'react-dom/server';
import {AssessmentSetup,assessmentCanStart} from '../src/components/ui/OperatorControls';
import {OrganizationProfile} from '../src/components/ui/OrganizationProfile';
import {TopBar} from '../src/components/ui/Panels';
import {SEED_ACTORS} from '../src/data/actors';
import {EngagementOverview,engagementLabel} from '../src/components/ui/EngagementOverview';
import {LiveAgentPanel} from '../src/components/ui/LiveAgentPanel';
import {PlanningPanel,riskDisplay,MitigationView,planningFailure} from '../src/components/ui/PlanningPanel';
import {illustrativeDisclaimer,type MitigationReport} from '../src/components/ui/mitigationPresentation';
assert(renderToStaticMarkup(<TopBar onAudit={()=>{}} onReconnect={()=>{}} connection="disconnected"/>).includes('Reconnect'));
assert(!renderToStaticMarkup(<TopBar onAudit={()=>{}} connection="connected"/>).includes('>Reconnect<'));
const actors=SEED_ACTORS.map(a=>({...a,backendAgentId:a.id,state:'completed' as const}));
assert.equal(engagementLabel(SEED_ACTORS,false),'No assessment loaded');
assert.equal(engagementLabel(actors,false),'Saved completed assessment');
assert.equal(engagementLabel(actors.map((a,i)=>i===1?{...a,state:'blocked' as const}:a),false),'Partial / blocked assessment');
assert.equal(engagementLabel(actors,true),'Assessment in progress');
assert.equal(engagementLabel(actors,false,[{id:'partial',timestamp:1,agent_id:'p',agent_role:'planner_agent',kind:'agent_completed',content:'Partial assessment',
  assessment_completion:{complete:false}}]),'Assessment finished · incomplete coverage');
const overview=renderToStaticMarkup(<EngagementOverview actors={actors} running={false} onSelect={()=>{}} gate="unavailable"/>);
const unknown=renderToStaticMarkup(<EngagementOverview actors={actors} running={false} onSelect={()=>{}} gate="unknown"/>);
assert(unknown.includes('Gate status unknown')&&!unknown.includes('Gate unavailable:'));
assert(overview.includes('Gate unavailable: recorded evidence mode')&&overview.includes('System boundaries'));
assert(overview.includes('disabled=""') && overview.includes('New assessment'));
assert.equal((overview.match(/class="stage-dot"/g)||[]).length,5);
const panel=renderToStaticMarkup(<LiveAgentPanel actor={actors[0]} transcript={[]} findings={[]}/>);
assert.equal((panel.match(/role="tab"/g)||[]).length,4);
assert.equal((panel.match(/role="tabpanel"/g)||[]).length,4);
assert.equal((panel.match(/hidden=""/g)||[]).length,3);
assert(planningFailure(new TypeError('Failed to fetch')).includes('Your inputs are preserved'));
assert.equal(planningFailure(new Error('A completed assessment is required')),'A completed assessment is required');
const offlinePanel=renderToStaticMarkup(<LiveAgentPanel actor={actors[0]} transcript={[]} findings={[]} gateAvailable={false}/>);
assert(offlinePanel.includes('Messages require live authorization'));
const planning=renderToStaticMarkup(<PlanningPanel onClose={()=>{}}/>);
assert(planning.includes('Planning steps')&&planning.includes('Use sample')&&planning.includes('Generate Risk Plan'));
assert(!planning.includes('Descending TF-IDF'));
assert.equal(riskDisplay({id:'x',name:'Customer Relationship Management Software'}),'Possible exposure of customer information');
assert.equal(riskDisplay({id:'x',name:'Databases'}),'Possible exposure of stored data');
const report:MitigationReport={engagement_id:'unit',narrative_context:{},context_label:'zero policy weight',findings:[],mitigation_plan:{option:'A',evidence_basis:'hypothetical',method:'No testing',limits:'No verified findings',recommendations:[{id:'r1',title:'General controls',action:'Review',evidence_basis:'hypothetical',finding_ids:[],risk_ids:['r1'],references:[],uncertainty:'Unverified'}]}};
const view=renderToStaticMarkup(<MitigationView report={report} selected={['r1']} onSelection={()=>{}}/>);
assert(view.includes('1 illustrative point</span>')&&!view.includes('1 illustrative points'));
assert(view.includes(illustrativeDisclaimer)&&view.includes('Hypothetical, no testing'));
function luminance(hex:string){const v=hex.replace('#','').match(/../g)!.map(h=>parseInt(h,16)/255).map(n=>n<=.04045?n/12.92:((n+.055)/1.055)**2.4);return .2126*v[0]+.7152*v[1]+.0722*v[2];}
const css=readFileSync(new URL('../src/design-system.css',import.meta.url),'utf8');
const token=(name:string)=>{const match=css.match(new RegExp(`--${name}:\\s*(#[A-Fa-f0-9]{6})`));assert(match,`missing ${name}`);return match[1];};
let contrastChecks=0;
for(const text of ['text-1','text-2','text-3'])for(const bg of ['bg-0','bg-1','bg-2']){
 const a=luminance(token(text)),b=luminance(token(bg));assert((Math.max(a,b)+.05)/(Math.min(a,b)+.05)>=4.5,`${text} on ${bg}`);contrastChecks++;
}
assert((luminance(token('accent'))+.05)/(luminance(token('accent-ink'))+.05)>=4.5);
console.log(`Redesign checks passed: real-stage labels, five stages, fail-closed Gate wording, four isolated tabs, planning stepper, singular effort, evidence labels; ${contrastChecks+1} token contrast pairs >=4.5:1. SSR is not visual acceptance.`);

// Setup UI must retain the existing authority/scope boundary and reject invalid intake locally.
assert(assessmentCanStart('Operator',true,false,false,true,{}));
for(const args of [
  [' ',true,false,false,true,{}],['Operator',false,false,false,true,{}],
  ['Operator',true,true,false,true,{}],['Operator',true,false,true,true,{}],
  ['Operator',true,false,false,false,{}],['Operator',true,false,false,true,{data_storage:'x'.repeat(12001)}],
] as const)assert(!assessmentCanStart(...args));
const setup=renderToStaticMarkup(<AssessmentSetup operator="Operator" onOperator={()=>{}} context={{data_storage:'  Exact <company> context\n'+ 'x'.repeat(3000)}} onContext={()=>{}} authorized={false} onAuthorize={()=>{}} running={false} sending={false} gateAvailable={true} notice="" onClose={()=>{}} onSubmit={()=>{}}/>);
assert(setup.includes('<dialog')&&setup.includes('aria-labelledby="assessment-title"'));
assert(setup.includes('127.0.0.1:8888')&&setup.includes('no external targets'));
assert(setup.includes('Start assessment')&&setup.includes('Cancel')&&setup.includes('disabled=""'));
assert(setup.includes('cannot grant permission')&&setup.includes('&lt;company&gt;')&&!setup.includes('maxlength="120"'));
const empty=renderToStaticMarkup(<LiveAgentPanel actor={null} transcript={[]} findings={[]} onClose={()=>{}}/>);
assert(empty.includes('Meet your assessment team')&&empty.includes('Close agent session'));
assert(panel.includes('Following latest')&&panel.includes('tabindex="0"'));
const profileTabs=renderToStaticMarkup(<OrganizationProfile value={{company_size:'Company'}} onFieldChange={()=>{}}/>);
assert(!profileTabs.includes('profile-number')&&profileTabs.includes('aria-current="true"'));
console.log('Cohesion regression checks passed: setup scope/authorization/readiness/context limits; accessible modal; preserved escaped long context; empty session; explicit transcript following; unnumbered profile sections. Rendered acceptance remains separate.');

const perfSource=readFileSync(new URL('../src/devtools/PerformancePanel.tsx',import.meta.url),'utf8');
assert(perfSource.includes('zIndex: 50'), 'Opt-in profiler controls must stay above projected scene labels (z-index <= 12)');

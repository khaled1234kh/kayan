import {useState} from 'react';
import {contextFields,contextLength,type ContextField,type EngagementContext} from './EngagementContextFields';

export const profileSections=[
  {name:'Organization',description:'Who operates the business',fields:['company_size','departments']},
  {name:'Technical environment',description:'Systems and trust boundaries',fields:['infrastructure_summary','network_architecture']},
  {name:'Data & customers',description:'Information and interactions',fields:['data_storage','customer_touchpoints']},
] as const;
const hints:Record<ContextField,{helper:string;example:string}>={
  company_size:{helper:'Approximate employees, sites and operating model.',example:'A fictional retailer with 120 employees and two warehouses.'},
  departments:{helper:'Teams that own the systems or use sensitive information.',example:'Development, customer support, finance and warehouse operations.'},
  infrastructure_summary:{helper:'Applications, services and deployment model. Include what you actually know.',example:'Public web application and REST APIs; private SQL database; cloud application tier.'},
  network_architecture:{helper:'How offices, cloud systems and third parties connect.',example:'Segmented office and server networks. Logistics vendors use VPN access; reviews are infrequent.'},
  data_storage:{helper:'Data types, storage locations and known recovery or access concerns.',example:'Customer records in SQL; images and backups in object storage. Restore testing is undocumented.'},
  customer_touchpoints:{helper:'How customers or partners interact with the organization.',example:'Account login, order tracking, refunds and courier API integrations.'},
};

export function ContextSummary({context,title='Organization context'}:{context:EngagementContext;title?:string}) {
  return <details className="context-summary"><summary>{title} · {contextFields.filter(([key])=>context[key]?.trim()).length}/6 fields supplied</summary>
    <dl>{contextFields.filter(([key])=>context[key]?.trim()).map(([key,label])=><div key={key}><dt>{label}</dt><dd>{context[key]}</dd></div>)}</dl>
  </details>;
}

export function OrganizationProfile({value,onFieldChange,disabled=false}:{value:EngagementContext;onFieldChange:(key:ContextField,text:string)=>void;disabled?:boolean}) {
  const [section,setSection]=useState(0);
  const active=profileSections[section];
  return <section className="organization-profile" aria-label="Organization profile editor">
    <nav className="profile-navigation" aria-label="Organization profile sections">{profileSections.map((item,index)=>{
      const supplied=item.fields.filter(key=>value[key]?.trim()).length;
      return <button type="button" key={item.name} aria-current={section===index?'step':undefined} disabled={disabled} onClick={()=>setSection(index)}>
        <span className="profile-number">{index+1}</span><span><strong>{item.name}</strong><small>{supplied}/2 fields supplied</small></span></button>;
    })}</nav>
    <div className="profile-editor"><header><h3>{active.name}</h3><p>Optional facts and known gaps. Leave unknown details out.</p></header>
      <div className="profile-field-grid">{active.fields.map(key=>{
        const field=contextFields.find(([name])=>name===key)!;
        const length=contextLength(value[key]??'');
        return <label className="profile-field" key={key}><span>{field[1]}</span><small>{hints[key].helper}</small>
          <textarea aria-label={field[1]} rows={key==='company_size'?3:5} value={value[key]??''} placeholder={hints[key].example}
            disabled={disabled} aria-invalid={length>field[2]} onChange={event=>onFieldChange(key,event.target.value)}/>
          <small className={length>field[2]?'field-error':''}>{length.toLocaleString()} / {field[2].toLocaleString()} characters</small>
          {length>field[2]&&<span role="alert" className="field-error">Too long to submit. Text is retained; shorten this field to continue.</span>}
        </label>;
      })}</div>
      <div className="profile-section-actions"><button type="button" className="btn" disabled={section===0||disabled} onClick={()=>setSection(i=>i-1)}>Previous section</button>
        {section<2?<button type="button" className="btn" disabled={disabled} onClick={()=>setSection(i=>i+1)}>Next section</button>:<span className="muted">Ready to review the supplied context below.</span>}</div>
    </div>
  </section>;
}

export const planningSamples:{name:string;summary:string;context:EngagementContext}[]=[
  {name:'Fictional retailer',summary:'Customer APIs, private SQL, vendor VPN and recovery questions.',context:{
    company_size:'HarborCart is a fictional online retailer with 120 employees and two warehouses.',departments:'Development, customer support, finance and warehouse operations.',
    infrastructure_summary:'A public e-commerce web application and customer REST APIs handle account login, order tracking and refunds against a private SQL database.',
    network_architecture:'Third-party logistics vendors use VPN access to warehouse networks. Vendor access reviews are infrequent.',
    data_storage:'Customer addresses and order histories are stored in SQL. Images and backups use cloud object storage. Backup restoration tests are not documented.',
    customer_touchpoints:'Customer accounts, order tracking, password reset and courier REST API integrations.'}},
  {name:'Fictional clinic',summary:'Internal patient records, shared logins and recovery review.',context:{company_size:'Meadow Clinic is a fictional practice with 35 employees.',departments:'Reception, nursing and clinicians.',
    infrastructure_summary:'An internal patient-record application uses a local database. Some reception staff share logins.',network_architecture:'A private clinic LAN has no public web application, no REST API and no vendor VPN.',
    data_storage:'Patient records and appointments are stored on a local server. Backups exist, but restore testing is undocumented.',customer_touchpoints:'Appointments are arranged by phone and at reception.'}},
];

const draftKey='kayan.planning.profile.v2';
export function readProfileDraft():{context:EngagementContext;sample:boolean} {
  try {
    const saved=JSON.parse(sessionStorage.getItem(draftKey)??'{}');
    const context:EngagementContext={};
    for(const [key] of contextFields)if(typeof saved.context?.[key]==='string')context[key]=saved.context[key];
    return {context,sample:saved.sample===true};
  } catch {return {context:{},sample:false};}
}
export function writeProfileDraft(context:EngagementContext,sample:boolean) {
  try {sessionStorage.setItem(draftKey,JSON.stringify({context,sample}));return true;}catch{return false;}
}

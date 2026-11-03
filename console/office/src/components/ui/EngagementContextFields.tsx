export const contextFields = [
  ['company_size', 'Company size', 2000], ['departments', 'Departments', 4000],
  ['infrastructure_summary', 'Infrastructure summary', 12000],
  ['network_architecture', 'Network architecture', 12000], ['data_storage', 'Data storage', 12000],
  ['customer_touchpoints', 'Customer touchpoints', 12000],
] as const;
export type EngagementContext = Partial<Record<typeof contextFields[number][0], string>>;
export type ContextField = typeof contextFields[number][0];
export const contextLength = (value:string) => Array.from(value).length;
export const invalidContext = (value:EngagementContext) => contextFields.some(([key,,max]) => contextLength(value[key]??'') > max);
export const contextHasText = (value:EngagementContext) => Object.values(value).some(text => text?.trim());
export function replaceContextField(value:EngagementContext,key:ContextField,text:string):EngagementContext {
  return {...value,[key]:text};
}

export function EngagementContextFields({ value, onChange, onFieldChange }: {
  value: EngagementContext; onChange: (value: EngagementContext) => void;
  onFieldChange?: (key:ContextField,text:string) => void;
}) {
  return <details className="descriptive-context"><summary>Optional descriptive context</summary>
    <p className="muted">Narrative framing only. Zero policy weight: this cannot grant scope or authorization.</p>
    {contextFields.map(([key, label, max]) => <label key={key}>{label}
      <textarea rows={3} value={value[key] ?? ''} aria-invalid={contextLength(value[key]??'')>max}
        onChange={event => onFieldChange ? onFieldChange(key,event.target.value) : onChange(replaceContextField(value,key,event.target.value))} />
      <small>{contextLength(value[key]??'')} / {max} characters</small>
      {contextLength(value[key]??'')>max && <span role="alert">This field is too long to submit. Nothing was truncated; shorten it before continuing.</span>}
    </label>)}
  </details>;
}

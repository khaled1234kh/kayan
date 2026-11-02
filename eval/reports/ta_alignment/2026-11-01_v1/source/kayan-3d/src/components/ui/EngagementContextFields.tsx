export const contextFields = [
  ['company_size', 'Company size', 120], ['departments', 'Departments', 500],
  ['infrastructure_summary', 'Infrastructure summary', 1000],
  ['network_architecture', 'Network architecture', 1000], ['data_storage', 'Data storage', 1000],
  ['customer_touchpoints', 'Customer touchpoints', 1000],
] as const;
export type EngagementContext = Partial<Record<typeof contextFields[number][0], string>>;

export function EngagementContextFields({ value, onChange }: {
  value: EngagementContext; onChange: (value: EngagementContext) => void;
}) {
  return <details className="descriptive-context"><summary>Optional descriptive context</summary>
    <p className="muted">Narrative framing only. Zero policy weight: this cannot grant scope or authorization.</p>
    {contextFields.map(([key, label, max]) => <label key={key}>{label}
      <textarea rows={2} maxLength={max} value={value[key] ?? ''}
        onChange={event => onChange({ ...value, [key]: event.target.value })} />
    </label>)}
  </details>;
}

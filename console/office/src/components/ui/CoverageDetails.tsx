export interface SpecialistCoverage {
  complete: boolean;
  stop_reason?: string;
  untested_tools?: string[];
  successful_tools?: string[];
  reused_tools?: string[];
  denied_tools?: string[];
  tool_errors?: { tool: string; error: string }[];
  verification_issues?: { tool: string; reason: string }[];
}

export function coverageRoleLabel(role: string) {
  return ({recon_agent:'Recon',webapp_agent:'Web-App',network_agent:'Network'} as Record<string,string>)[role] ?? role;
}

/** A loop finishing and the bounded tool catalogue being covered are separate facts. */
export function CoverageDetails({ coverage }: { coverage: SpecialistCoverage }) {
  return <div className="coverage-details">
    <p><strong>Catalogue coverage: {coverage.complete ? 'complete' : 'incomplete'}</strong>
      {coverage.stop_reason && <> · Stop: {coverage.stop_reason.replace(/_/g, ' ')}</>}</p>
    {!!coverage.untested_tools?.length && <p>Untested tools: {coverage.untested_tools.join(', ')}</p>}
    {!!coverage.denied_tools?.length && <p>Denied tools: {coverage.denied_tools.join(', ')}</p>}
    {!!coverage.reused_tools?.length && <p>Reused observations: {coverage.reused_tools.join(', ')}. Source attribution is retained in the raw record; no second execution.</p>}
    {!!coverage.tool_errors?.length && <ul>{coverage.tool_errors.map((issue, index) =>
      <li key={index}>Execution error · {issue.tool}: {issue.error}</li>)}</ul>}
    {!!coverage.verification_issues?.length && <ul>{coverage.verification_issues.map((issue, index) =>
      <li key={index}>Verification issue · {issue.tool}: {issue.reason}</li>)}</ul>}
    <small>Registered lab-tool catalogue only. A completed loop does not establish target safety.</small>
  </div>;
}

export function parseCoverage(value: unknown): SpecialistCoverage | null {
  if (!value || typeof value !== 'object') return null;
  const item = value as Record<string, unknown>;
  if (typeof item.complete !== 'boolean') return null;
  if (item.stop_reason !== undefined && typeof item.stop_reason !== 'string') return null;
  for (const key of ['untested_tools', 'successful_tools', 'denied_tools', 'reused_tools']) {
    if (item[key] !== undefined && (!Array.isArray(item[key]) || !(item[key] as unknown[]).every(v => typeof v === 'string'))) return null;
  }
  for (const [key, message] of [['tool_errors', 'error'], ['verification_issues', 'reason']]) {
    if (item[key] !== undefined && (!Array.isArray(item[key]) || !(item[key] as unknown[]).every(v =>
      !!v && typeof v === 'object' && typeof (v as Record<string, unknown>).tool === 'string' &&
      typeof (v as Record<string, unknown>)[message] === 'string'))) return null;
  }
  return item as unknown as SpecialistCoverage;
}

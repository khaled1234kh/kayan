import { useEffect, useState } from 'react';
import { apiUrl } from '../../transport';
import { EvidenceReview } from './EvidenceReview';

type Mode = 'local' | 'ollama' | 'sovereigneg';
type Assessment = { title: string; assessment_id: string };
type Archive = Assessment & {
  source_sha256: string;
  observations_by_role?: Record<string, ObservationCounts>;
  local_ranking_enabled?: boolean;
  local_ranking_supported?: boolean;
  cloud_available: boolean;
  cloud_selection_supported?: boolean;
  source_status?: string;
  custody_test_only?: boolean;
  admission_status?: 'evaluated' | 'pending';
  review_status?: 'verified' | 'submitted' | 'awaiting';
  verification: 'fixture_custody' | 'independent_custody' | 'missing_custody' | 'invalid_custody';
  coverage: {
    recorded_tools?: number;
    captured_tools?: number;
    invalid_sources?: number;
    failed_tools?: number;
    truncated_tools?: number;
    specialists?: { role: string; complete: boolean; status: string; stop_reason?: string }[];
  };
};

const verificationLabel: Record<Archive['verification'], string> = {
  fixture_custody: 'Verified using pinned synthetic custody',
  independent_custody: 'Independent custody verified',
  missing_custody: 'Independent custody missing',
  invalid_custody: 'Independent custody failed verification',
};

const sourceLabel: Record<string, string> = {
  source_captured: 'Captured at tool execution',
  mixed_source: 'Execution artifacts and lower-assurance transcript records',
  transcript_only: 'Historical transcript only · lower assurance',
  invalid_source: 'Source artifact missing or invalid',
  no_evidence: 'No tool records available',
};

const specialistName: Record<string, string> = {
  recon_agent: 'Recon', webapp_agent: 'Web-App', network_agent: 'Network',
};
const observationLabels = {
  completed: 'Completed captures',
  projected: 'Projected captures',
  empty: 'Captures without retained output',
  failed: 'Failed captures',
  denied: 'Denied captures',
  not_dispatched: 'Undispatched captures',
  authorization_unverified: 'Captures with unverified authorization',
  transcript_only: 'Transcript-only records',
} as const;
type ObservationCounts = Partial<Record<keyof typeof observationLabels, number>>;
type Source = { id: string; roles: string[]; statements: string[] };
type SummarySource = Source & {
  technique?: string;
  occurrence?: string;
  selection_origin?: 'verified_action_supplement';
};
type SummaryCoverage = {
  admitted_occurrences: number;
  covered_occurrences: number;
  action_covered_occurrences: number;
};
type ActionReference = { technique: string; occurrence: string; source_id: string };
type FindingProof = { event_revision: number; assertions: { role: string; source_ids: string[] }[] };
type Report = {
  status: 'local' | 'selected' | 'degraded';
  provider: string | null;
  model: string | null;
  attempted_model?: string;
  notice?: string;
  finish_reason?: string;
  usage?: { input?: number; output?: number; reasoning?: number; latency_s?: number };
  findings: { technique: string; title: string; occurrence: string; sources: Source[]; proof?: FindingProof }[];
  withheld: { technique: string; reasons: string[]; occurrence?: string; event_revision?: number }[];
  summary: SummarySource[];
  summary_coverage?: SummaryCoverage;
  summary_additional_actions?: ActionReference[];
  recommendations: { id: string; text: string }[];
  limitation: string;
};

const endpoint = `${apiUrl.replace(/\/$/, '')}/reporting/archive`;
const metricNumber = new Intl.NumberFormat('en', { maximumFractionDigits: 3 });

const auditStatusLabels = {
  verified: 'Match in verified ledger',
  mismatch: 'Decision details differ',
  missing_entry: 'No matching audit entry',
  ledger_invalid: 'Ledger verification failed',
  unavailable: 'Audit service unavailable',
  missing_reference: 'Missing audit reference',
  reused_reference: 'Reused audit reference',
  invalid_source: 'Invalid capture',
} as const;
type AuditCounts = Partial<Record<keyof typeof auditStatusLabels, number>>;

export function AuditCountsView({ counts }: { counts: AuditCounts }) {
  const rows = Object.entries(auditStatusLabels).flatMap(([key, label]) => {
    const count = counts[key as keyof AuditCounts];
    return count ? [{ key, label, count }] : [];
  });
  return <div role="status">
    {rows.length ? <ul aria-label="Audit decision reconciliation">
      {rows.map(({ key, label, count }) => <li key={key}>{label} · {count}</li>)}
    </ul> : <p>No captured decisions to check.</p>}
  </div>;
}

export function RoleObservationCounts({ counts }: { counts?: ObservationCounts }) {
  const labels = Object.entries(observationLabels).flatMap(([key, label]) => {
    const count = counts?.[key as keyof ObservationCounts];
    return count ? [`${label} ${count}`] : [];
  });
  return <div className="muted">{labels.length ? labels.join(' · ') : 'No retained observations'}</div>;
}

function ArchiveAuditCheck({ assessmentId, sourceSha }: { assessmentId: string; sourceSha: string }) {
  const [counts, setCounts] = useState<AuditCounts>();
  const [checking, setChecking] = useState(false);
  const [error, setError] = useState('');

  async function check() {
    setChecking(true);
    setCounts(undefined);
    setError('');
    try {
      const response = await fetch(`${endpoint}/audit?assessment_id=${encodeURIComponent(assessmentId)}`, { cache: 'no-store' });
      if (!response.ok) throw new Error('Audit check unavailable. Try again.');
      const result: { assessment_id: string; source_sha256: string; counts: AuditCounts } = await response.json();
      if (result.assessment_id !== assessmentId || result.source_sha256 !== sourceSha) {
        throw new Error('Evidence changed. Reopen this archive before checking again.');
      }
      setCounts(result.counts);
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : 'Audit check unavailable. Try again.');
    } finally {
      setChecking(false);
    }
  }

  return <>
    <button className="btn" type="button" disabled={checking} onClick={() => void check()}>
      {checking ? 'Checking audit references…' : 'Check TrustGate audit'}
    </button>
    {error && <p role="alert">{error}</p>}
    {counts && <AuditCountsView counts={counts} />}
  </>;
}

export async function readSavedReport(response: Response) {
  if (!response.ok) {
    const failure = await response.json().catch(() => undefined);
    throw new Error(typeof failure?.detail === 'string' ? failure.detail : 'Could not load the saved report.');
  }
  const digest = /^"([a-f0-9]{64})"$/.exec(response.headers.get('ETag') ?? '')?.[1];
  return { report: await response.json() as Report, digest };
}

export function ReportExecutionDetails({ report }: {
  report: Pick<Report, 'status' | 'usage' | 'finish_reason'>;
}) {
  if (report.status !== 'selected') return null;

  const { input, output, reasoning, latency_s: latency } = report.usage ?? {};
  const fields: [string, string][] = [];
  const tokenCounts = [
    ['Input tokens', input],
    ['Output tokens', output],
    ['Reasoning tokens', reasoning],
  ] as const;
  for (const [label, count] of tokenCounts) {
    if (typeof count === 'number' && Number.isSafeInteger(count) && count >= 0) {
      fields.push([label, metricNumber.format(count)]);
    }
  }
  if (typeof latency === 'number' && Number.isFinite(latency) && latency >= 0) {
    fields.push(['Provider latency', `${metricNumber.format(latency)} s`]);
  }
  if (report.finish_reason === 'stop') fields.push(['Finish reason', report.finish_reason]);
  if (fields.length === 0) return <p className="muted">Provider metrics unavailable for this saved report.</p>;

  return <dl className="archived-report-metrics" aria-label="Saved provider metrics">
    {fields.map(([label, value]) => <div key={label}><dt>{label}</dt><dd>{value}</dd></div>)}
  </dl>;
}

export function ReportEvidence({ source }: { source: SummarySource }) {
  return <div className="archived-evidence">
    <strong>{source.id}</strong> <span className="muted">{source.roles.join(' · ')}</span>
    {source.selection_origin === 'verified_action_supplement' &&
      <p className="muted">Observed action added by KAYAN</p>}
    {source.statements.map(statement => <p key={statement}>{statement}</p>)}
  </div>;
}

export function ReportSummaryCoverage({ coverage }: { coverage?: SummaryCoverage }) {
  if (!coverage || coverage.admitted_occurrences === 0) return null;
  const { admitted_occurrences: total, covered_occurrences: cited, action_covered_occurrences: actions } = coverage;
  return <p className="muted">
    Summary cites {cited} of {total} admitted occurrences. Observed-action excerpts cover {actions} of {total}.
  </p>;
}

export function AdditionalVerifiedActions({ report }: {
  report: Pick<Report, 'findings' | 'summary_additional_actions'>;
}) {
  if (!report.summary_additional_actions?.length) return null;
  const findings = new Map(report.findings.map(finding => [
    JSON.stringify([finding.technique, finding.occurrence]), finding,
  ]));
  const actions = report.summary_additional_actions.flatMap(ref => {
    const finding = findings.get(JSON.stringify([ref.technique, ref.occurrence]));
    const source = finding?.sources.find(item => item.id === ref.source_id && item.roles.includes('mechanic'));
    return source ? [{ ref, source }] : [];
  });
  if (!actions.length) return null;
  return <details className="session-finding">
    <summary>Other verified actions ({actions.length})</summary>
    {actions.map(({ ref, source }) => <div key={JSON.stringify([ref.technique, ref.occurrence, ref.source_id])}>
      <p className="muted">{ref.technique} · {ref.occurrence}</p>
      <ReportEvidence source={source} />
    </div>)}
  </details>;
}

const proofRoles: Record<string, string> = {
  mechanic: 'Action', outcome: 'Outcome', actor: 'Attribution', authorization: 'Authorization',
  process_session: 'Process and session link',
};

export function ReviewedFindingProof({ proof }: { proof?: FindingProof }) {
  if (!proof?.assertions.length) return null;
  return <section aria-label="Reviewed proof">
    <p className="muted">Reviewed proof · event revision {proof.event_revision}</p>
    <ul>
      {proof.assertions.map(({ role, source_ids: [primary, ...additional] }) =>
        <li key={JSON.stringify([role, primary, additional])}>
          {proofRoles[role] ?? role} · {primary}
          {additional.length > 0 && <span> with {additional.join(', ')}</span>}
        </li>)}
    </ul>
  </section>;
}

export function ArchivedReport() {
  const [open, setOpen] = useState(false);
  const [assessments, setAssessments] = useState<Assessment[]>();
  const [selected, setSelected] = useState('');
  const [error, setError] = useState('');
  const [pending, setPending] = useState(false);

  useEffect(() => {
    if (!open) return;
    const controller = new AbortController();
    setError('');
    fetch(endpoint.replace(/archive$/, 'assessments'), { signal: controller.signal }).then(async response => {
      if (!response.ok) throw new Error('Completed assessments are unavailable.');
      const list: Assessment[] = await response.json();
      if (controller.signal.aborted) return;
      setAssessments(list);
      setSelected(current => list.some(item => item.assessment_id === current) ? current : list[0]?.assessment_id ?? '');
    }).catch(() => {
      if (!controller.signal.aborted) setError('Could not load completed assessments.');
    });
    return () => controller.abort();
  }, [open]);

  return <details className="archived-report role-boundary" onToggle={event => setOpen(event.currentTarget.open)}>
    <summary>Archived Reporting</summary>
    <div className="archived-report-body">
      {error ? <p role="alert">{error}</p> : !assessments ? <p role="status">Loading completed assessments…</p>
        : assessments.length === 0 ? <p>No completed synthetic assessments are available.</p> : <>
          <label htmlFor="report-assessment">Completed assessment</label>
          <select id="report-assessment" value={selected} disabled={pending} onChange={event => setSelected(event.target.value)}>
            {assessments.map(item => <option key={item.assessment_id} value={item.assessment_id}>{item.title}</option>)}
          </select>
          {selected && <AssessmentReport key={selected} assessmentId={selected} open={open} onPending={setPending} />}
        </>}
    </div>
  </details>;
}

function AssessmentReport({ assessmentId, open, onPending }: {
  assessmentId: string; open: boolean; onPending: (value: boolean) => void;
}) {
  const selection = `assessment_id=${encodeURIComponent(assessmentId)}`;
  const [archive, setArchive] = useState<Archive>();
  const [refresh, setRefresh] = useState(0);
  const [mode, setMode] = useState<Mode>('local');
  const [saved, setSaved] = useState<Awaited<ReturnType<typeof readSavedReport>>>();
  const [pending, setPending] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [error, setError] = useState('');
  const [loadError, setLoadError] = useState('');
  const resultUrl = `${endpoint}/result?${selection}&mode=${mode}`;
  const report = saved?.report;
  const busy = pending || exporting;

  useEffect(() => {
    if (!open) return;
    const controller = new AbortController();
    fetch(`${endpoint}?${selection}`, { signal: controller.signal }).then(async response => {
      if (!response.ok) throw new Error('Saved synthetic assessment is unavailable.');
      const loaded: Archive = await response.json();
      if (!controller.signal.aborted) setArchive(loaded);
    }).catch(() => {
      if (!controller.signal.aborted) setLoadError('Could not open the archived assessment.');
    });
    return () => controller.abort();
  }, [open, selection, refresh]);

  useEffect(() => {
    if (!open || busy) return;
    const controller = new AbortController();
    fetch(resultUrl, { signal: controller.signal }).then(async response => {
      const loaded = response.status === 404 ? undefined : await readSavedReport(response);
      if (!controller.signal.aborted) setSaved(loaded);
    }).catch(failure => {
      if (!controller.signal.aborted) {
        setSaved(undefined);
        setError(failure instanceof Error ? failure.message : 'Could not load the saved report.');
      }
    });
    return () => controller.abort();
  }, [open, busy, resultUrl, refresh]);

  async function run() {
    setPending(true);
    onPending(true);
    setError('');
    try {
      const response = await fetch(`${endpoint}/run`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ mode, assessment_id: assessmentId }),
      });
      if (!response.ok) {
        const failure = await response.json();
        throw new Error(typeof failure.detail === 'string' ? failure.detail : 'Reporting failed.');
      }
      setSaved(await readSavedReport(response));
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : 'Reporting failed.');
    } finally {
      setPending(false);
      onPending(false);
      if (mode === 'sovereigneg') {
        try {
          const response = await fetch(`${endpoint}?${selection}`);
          if (response.ok) setArchive(await response.json());
        } catch {
          setArchive(current => current && { ...current, cloud_available: false });
        }
      }
    }
  }

  async function exportReport() {
    if (!saved?.digest || busy) return;
    setExporting(true);
    onPending(true);
    setError('');
    try {
      const response = await fetch(`${resultUrl}&download=true&expected_sha256=${saved.digest}`);
      if (response.status === 409 || response.status === 404) {
        setSaved(undefined);
        setArchive(undefined);
        setLoadError('');
        setRefresh(count => count + 1);
        setError('Saved report changed. Review the current report before exporting.');
        return;
      }
      if (!response.ok || response.headers.get('ETag') !== `"${saved.digest}"`) {
        throw new Error('Could not export the saved report.');
      }
      const url = URL.createObjectURL(await response.blob());
      const link = document.createElement('a');
      link.href = url;
      link.download = `${assessmentId}-${mode}.json`;
      link.click();
      window.setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch {
      setError('Could not export the saved report.');
    } finally {
      setExporting(false);
      onPending(false);
    }
  }

  return <>
      {loadError && !archive ? <p role="alert">{loadError}</p> : !archive ? <p role="status">Opening archived assessment…</p> : <>
        <p role="status"><strong>{verificationLabel[archive.verification]}</strong></p>
        {archive.custody_test_only && <p><strong>Test-only custody and review</strong></p>}
        {archive.source_status && sourceLabel[archive.source_status] && <p className="muted">{sourceLabel[archive.source_status]}</p>}
        <details className="coverage-warning">
          <summary>Evidence coverage · {archive.coverage.recorded_tools ?? 0} records</summary>
          {archive.coverage.failed_tools !== undefined &&
            <p>{archive.coverage.failed_tools} failed · {archive.coverage.truncated_tools} truncated</p>}
          <ul>{archive.coverage.specialists?.map(item => <li key={item.role}>
            {specialistName[item.role]} · {item.complete ? 'catalogue reported complete' : item.status === 'unavailable' ? 'coverage not recorded' : 'catalogue reported incomplete'}
            {item.stop_reason && <span> · {item.stop_reason.replace(/_/g, ' ')}</span>}
            {archive.observations_by_role && <RoleObservationCounts counts={archive.observations_by_role[item.role]} />}
          </li>)}</ul>
          {Boolean(archive.coverage.captured_tools || archive.coverage.invalid_sources) &&
            <ArchiveAuditCheck key={archive.source_sha256} assessmentId={assessmentId} sourceSha={archive.source_sha256} />}
        </details>
        {archive.verification !== 'fixture_custody' && <>
          <ol aria-label="Evidence review progress">
            <li>{archive.coverage.captured_tools ? 'Captured' : 'Capture pending'}</li>
            <li>{archive.review_status === 'awaiting' ? 'Pending review' : 'Reviewed'}</li>
            <li>{archive.verification === 'independent_custody' ? 'Custody verified' : 'Custody pending'}</li>
            <li>{archive.admission_status === 'evaluated' ? 'Admission evaluated' : 'Admission pending'}</li>
          </ol>
          <EvidenceReview assessmentId={assessmentId} reviewStatus={archive.review_status} onChange={() => setRefresh(count => count + 1)} />
        </>}
        <label htmlFor="archived-report-mode">Reporting mode</label>
        <select id="archived-report-mode" value={mode} disabled={busy} onChange={event => {
          setMode(event.target.value as Mode);
          setSaved(undefined);
          setError('');
        }}>
          <option value="local">Local evidence report</option>
          <option value="ollama">Local Qwen · rank verified excerpts</option>
          <option value="sovereigneg">SovereignEG · Qwen 27B</option>
        </select>
        {mode === 'sovereigneg' && <p className="muted">{archive.cloud_available
          ? 'One approved request. TrustGate checks this archive before sending admitted evidence.'
          : archive.cloud_selection_supported === false
            ? 'Cloud selection is unavailable for this archive. A local report is available.'
            : 'Cloud execution needs an unused approval for this archive. Saved reports remain available.'}</p>}
        {mode === 'ollama' && <p className="muted">{!archive.local_ranking_enabled
          ? 'Local model ranking is disabled. The local evidence report is available.'
          : !archive.local_ranking_supported
            ? 'This archive has no eligible excerpt selection within the local input limit.'
            : 'Local Qwen can rank admitted excerpts after TrustGate authorizes inference.'}</p>}
        <button className="btn" type="button" disabled={busy || (mode === 'sovereigneg' && !archive.cloud_available)
          || (mode === 'ollama' && (!archive.local_ranking_enabled || !archive.local_ranking_supported))} onClick={() => void run()}>
          {pending ? 'Preparing report…' : 'Run Reporting'}
        </button>
        {error && <p role="alert">{error}</p>}
        {!report && !pending && !error && <p className="muted">No report loaded for this mode.</p>}
        {report && <section aria-label="Saved evidence report">
          <p className="muted" role="status">{report.status === 'selected' ? `${report.provider === 'sovereigneg'
            ? 'SovereignEG' : report.provider === 'ollama' ? 'Local Ollama' : report.provider} · ${report.model}`
            : report.status === 'degraded' ? report.attempted_model
              ? `Local fallback · attempted ${report.attempted_model}` : 'Local evidence fallback'
              : 'Local deterministic evidence report'}</p>
          {report.notice && <p role="status">{report.notice}</p>}
          <ReportExecutionDetails report={report} />
          <h4>Executive summary</h4>
          <ReportSummaryCoverage coverage={report.summary_coverage} />
          <AdditionalVerifiedActions report={report} />
          {report.summary.length ? report.summary.map(source =>
            <div key={`${source.technique}/${source.occurrence}/${source.id}`}>
              {source.occurrence && <p className="muted">{source.occurrence}</p>}
              <ReportEvidence source={source} />
            </div>) : <p>No supported findings.</p>}
          <h4>Supported findings ({report.findings.length})</h4>
          {report.findings.map(finding => <details key={`${finding.technique}/${finding.occurrence}`} className="session-finding">
            <summary>{finding.technique}{finding.title !== finding.technique && ` · ${finding.title}`}</summary>
            <p className="muted">{finding.occurrence}</p>
            <ReviewedFindingProof proof={finding.proof} />
            {finding.sources.map(source => <ReportEvidence key={source.id} source={source} />)}
          </details>)}
          {report.recommendations.length > 0 && <><h4>Defensive recommendations</h4>
            <ul>{report.recommendations.map(action => <li key={action.id}>{action.text}</li>)}</ul></>}
          <h4>Withheld claims ({report.withheld.length})</h4>
          {report.withheld.length ? <ul>{report.withheld.map(claim =>
            <li key={`${claim.technique}/${claim.occurrence}/${claim.event_revision}`}>{claim.technique}
              {claim.occurrence && ` · ${claim.occurrence}`} · {claim.reasons.map(reason => reason.replace(/_/g, ' ')).join(', ')}</li>)}</ul>
            : <p>No withheld claims in this archive.</p>}
          <p className="muted">{report.limitation}</p>
          {saved?.digest ? <button className="btn" type="button" disabled={busy} onClick={() => void exportReport()}>
            {exporting ? 'Exporting report…' : 'Export report JSON'}
          </button> : <p className="muted">Verified JSON export is unavailable for this saved response.</p>}
        </section>}
      </>}
  </>;
}


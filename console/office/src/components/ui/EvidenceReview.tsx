import { useState, type FormEvent } from 'react';
import { apiUrl } from '../../transport';

type Entry = { source_id: string; artifact_sha256: string; tool: string; audit_entry_id?: string; status: string; outcome: unknown };
type Review = { reviewer: string; source_sha256: string; records: Entry[]; candidates: string[]; review_head: string | null; mechanics: Record<string, string> };
const url = `${apiUrl.replace(/\/$/, '')}/reporting/review`;

export function EvidenceReview({ assessmentId, reviewStatus, onChange }: {
  assessmentId: string; onChange: () => void; reviewStatus?: 'verified' | 'submitted' | 'awaiting';
}) {
  const [token, setToken] = useState('');
  const [review, setReview] = useState<Review>();
  const [source, setSource] = useState('');
  const [technique, setTechnique] = useState('');
  const [role, setRole] = useState('mechanic');
  const [disposition, setDisposition] = useState('unresolved');
  const [value, setValue] = useState('');
  const [receiptFile, setReceiptFile] = useState<File>();
  const [message, setMessage] = useState('');
  const [busy, setBusy] = useState(false);

  const values = role === 'mechanic' ? [review?.mechanics?.[technique]].filter(Boolean) as string[]
    : ({ actor: ['adversary', 'benign'], authorization: ['authorized', 'unauthorized'],
        outcome: ['completed', 'failed'], process_session: ['linked', 'unlinked'] }[role] ?? []);

  async function exchange(importing: boolean) {
    setBusy(true);
    setMessage('');
    try {
      const response = await fetch(`${url.replace(/review$/, 'custody')}/${importing ? 'receipt' : 'package'}?assessment_id=${encodeURIComponent(assessmentId)}`, {
        method: importing ? 'POST' : 'GET',
        headers: { Authorization: `Bearer ${token}`, ...(importing ? { 'Content-Type': 'application/json' } : {}) },
        body: importing ? await receiptFile?.text() : undefined,
      });
      if (!response.ok) {
        const error = await response.json();
        throw new Error(typeof error.detail === 'string' ? error.detail : 'Custody exchange failed.');
      }
      if (importing) {
        const result = await response.json();
        setMessage(`Custody receipt accepted. SHA-256 ${result.receipt_sha256}`);
        onChange();
      } else {
        const file = URL.createObjectURL(await response.blob());
        const link = document.createElement('a');
        link.href = file;
        link.download = `review-${assessmentId}.json`;
        link.click();
        URL.revokeObjectURL(file);
        setMessage('Reviewable evidence package exported.');
      }
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'Custody exchange failed.');
    } finally {
      setBusy(false);
    }
  }

  async function request(submit: boolean) {
    setMessage('');
    setBusy(true);
    try {
      const response = await fetch(`${url}?assessment_id=${encodeURIComponent(assessmentId)}`, {
        method: submit ? 'POST' : 'GET',
        headers: { Authorization: `Bearer ${token}`, ...(submit ? { 'Content-Type': 'application/json' } : {}) },
        body: submit ? JSON.stringify({ assessment_id: assessmentId, source_sha256: review?.source_sha256,
          previous_review_sha256: review?.review_head,
          assertions: [{ source_id: source, technique, role, disposition, value: value || null }] }) : undefined,
      });
      const data = await response.json();
      if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'Could not open or save review.');
      if (submit) {
        setReview(current => current && { ...current, review_head: data.review_sha256 });
        onChange();
        setMessage(`Review submitted for independent admission. Receipt ${data.review_sha256}`);
      } else {
        setReview(data);
        setSource(data.records[0]?.source_id ?? '');
        setTechnique(data.candidates.find((value: string) => value !== 'Unmapped') ?? '');
      }
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'Review unavailable.');
    } finally {
      setBusy(false);
    }
  }

  return <details className="role-boundary"><summary>Independent evidence review</summary>
    <div className="archived-report-body">
      {reviewStatus && <p className="muted">{reviewStatus === 'verified' ? 'Independent review verified'
        : reviewStatus === 'submitted' ? 'Review submitted · awaiting independent verification' : 'Awaiting independent review'}</p>}
      <form onSubmit={(event: FormEvent) => { event.preventDefault(); setReview(undefined); void request(false); }}>
        <label htmlFor="review-token">Assigned reviewer or custodian token</label>
        <input id="review-token" type="password" autoComplete="off" value={token} required disabled={busy}
          onChange={event => { setToken(event.target.value); setReview(undefined); }} />
        <button className="btn" type="submit" disabled={busy}>Open evidence</button>
      </form>
      <button className="btn" type="button" disabled={busy || !token} onClick={() => void exchange(false)}>Export evidence package</button>
      <label htmlFor="custody-receipt">Signed custody receipt</label>
      <input id="custody-receipt" type="file" accept="application/json,.json" onChange={e => setReceiptFile(e.target.files?.[0])} />
      <button className="btn" type="button" disabled={busy || !token || !receiptFile} onClick={() => void exchange(true)}>Import signed receipt</button>
      {review && <>
        <p>Signed in as {review.reviewer}</p>
        {review.records.map(entry => <details className="session-finding" key={entry.source_id}>
          <summary>{entry.tool} · {entry.status}</summary>
          <p>Source {entry.source_id} · SHA-256 {entry.artifact_sha256}</p>
          <p>TrustGate audit {entry.audit_entry_id || 'unavailable'}</p>
          <pre style={{ whiteSpace: 'pre-wrap' }}>{JSON.stringify(entry.outcome, null, 2)}</pre>
        </details>)}
        <label htmlFor="review-source">Source record</label>
        <select id="review-source" value={source} onChange={event => setSource(event.target.value)}>
          {review.records.map(entry => <option value={entry.source_id} key={entry.source_id}>{entry.tool} · {entry.source_id.slice(-8)}</option>)}
        </select>
        <label htmlFor="review-technique">Candidate technique</label>
        <select id="review-technique" value={technique} onChange={event => { setTechnique(event.target.value); setValue(''); }}>
          <option value="">Choose a technique</option>
          {review.candidates.filter(value => value !== 'Unmapped').map(value => <option key={value}>{value}</option>)}
        </select>
        <label htmlFor="review-role">Evidence role</label>
        <select id="review-role" value={role} onChange={event => { setRole(event.target.value); setValue(''); }}>
          {['actor', 'authorization', 'mechanic', 'outcome', 'process_session'].map(value => <option key={value}>{value}</option>)}
        </select>
        <label htmlFor="review-value">Reviewed value</label>
        <select id="review-value" value={value} onChange={event => setValue(event.target.value)}>
          <option value="">Unspecified</option>
          {values.map(option => <option key={option}>{option}</option>)}
        </select>
        <label htmlFor="review-disposition">Disposition</label>
        <select id="review-disposition" value={disposition} onChange={event => setDisposition(event.target.value)}>
          {['unresolved', 'supported', 'contradicted'].map(value => <option key={value}>{value}</option>)}
        </select>
        <button className="btn" type="button" disabled={busy || !source || !technique || (disposition === 'supported' && !value)} onClick={() => void request(true)}>Submit assertion</button>
      </>}
      {message && <p role="status">{message}</p>}
    </div>
  </details>;
}


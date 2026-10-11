import { useState } from 'react';
import type { ActivationOut } from '../../api/onboarding';
import type { OnboardingState } from './types';
import { onboardingApi } from '../../api/onboarding';

interface Step5ActivationProps {
  state: OnboardingState;
  onNext: () => Promise<void>;
  onBack: () => void;
  companyId: string;
  onActivated: (activation: ActivationOut) => void;
}

export function Step5Activation({
  state,
  onNext,
  onBack,
  companyId,
  onActivated,
}: Step5ActivationProps) {
  const { activation, isLoading, isSubmitting } = state;
  const [isActivating, setIsActivating] = useState(false);
  const [activationResult, setActivationResult] = useState<ActivationOut | null>(null);
  const [activationError, setActivationError] = useState<string | null>(null);

  const handleActivate = async () => {
    setIsActivating(true);
    setActivationError(null);
    try {
      const result = await onboardingApi.activateCompany(companyId);
      setActivationResult(result);
      onActivated(result);
      await onNext();
    } catch (error) {
      setActivationError(error instanceof Error ? error.message : 'Activation failed');
    } finally {
      setIsActivating(false);
    }
  };

  const validateStep = (): boolean => {
    if (!activation) return false;
    if (activation.company.status !== 'draft') return false;
    if (activation.workforce.length === 0) return false;
    if (activation.contracts.length === 0) return false;
    return true;
  };

  return (
    <div className="onboarding-step">
      <div className="step-header">
        <h2>Step 5 of 5 \u2014 Activation</h2>
        <p className="step-description">
          Review the complete company configuration. Activation makes the company live:
          contracts become immutable, the company occupies the single active slot, and
          the 3D office will render your configured roster instead of the demo team.
        </p>
      </div>

      {activationError && (
        <div className="alert alert-error" role="alert">
          <strong>Activation Failed:</strong> {activationError}
        </div>
      )}

      {activationResult && (
        <div className="alert alert-success" role="alert">
          <strong>Company Activated Successfully!</strong>
          <p>Your company is now live. The office will render your configured team.</p>
        </div>
      )}

      {activation && (
        <div className="activation-review">
          <div className="review-section">
            <h3>Company</h3>
            <dl className="review-grid">
              <dt>Name</dt>
              <dd>{activation.company.name}</dd>
              <dt>Template</dt>
              <dd>{activation.company.templateKey}</dd>
              <dt>Industry</dt>
              <dd>{activation.company.industry || '\u2014'}</dd>
              <dt>Status</dt>
              <dd><span className={`status-badge ${activation.company.status}`}>{activation.company.status}</span></dd>
              <dt>Currency</dt>
              <dd>{activation.company.currency}</dd>
              <dt>Monthly Budget</dt>
              <dd>{activation.company.currency} {activation.company.monthlyBudget || '\u2014'}</dd>
              <dt>Revision</dt>
              <dd>{activation.company.revision}</dd>
            </dl>
          </div>

          <div className="review-section">
            <h3>Workforce ({activation.workforce.length} employees)</h3>
            <table className="review-table">
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Name</th>
                  <th>Kind</th>
                  <th>Role</th>
                  <th>Status</th>
                  <th>Reports To</th>
                </tr>
              </thead>
              <tbody>
                {activation.workforce.map((emp) => (
                  <tr key={emp.id}>
                    <td className="mono">{emp.id}</td>
                    <td>{emp.displayName}</td>
                    <td><span className={`kind-badge ${emp.kind}`}>{emp.kind}</span></td>
                    <td>{emp.roleKey}</td>
                    <td><span className={`status-badge ${emp.status}`}>{emp.status}</span></td>
                    <td className="mono">{emp.reportsToId || '\u2014'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="review-section">
            <h3>Contracts ({activation.contracts.length})</h3>
            <table className="review-table">
              <thead>
                <tr>
                  <th>Employee</th>
                  <th>Role</th>
                  <th>Version</th>
                  <th>Status</th>
                  <th>Hash</th>
                </tr>
              </thead>
              <tbody>
                {activation.contracts.map((contract) => (
                  <tr key={contract.id}>
                    <td className="mono">{contract.employeeId}</td>
                    <td>{contract.role}</td>
                    <td>v{contract.versionNumber}</td>
                    <td><span className={`status-badge ${contract.status}`}>{contract.status}</span></td>
                    <td className="mono hash">{contract.contentHash.slice(0, 16)}\u2026</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="review-section">
            <h3>Budget Summary</h3>
            <dl className="review-grid">
              <dt>Currency</dt>
              <dd>{activation.budget.currency}</dd>
              <dt>Monthly Limit</dt>
              <dd>{activation.budget.currency} {activation.budget.monthlyLimit}</dd>
              <dt>Actual Spend</dt>
              <dd>{activation.budget.currency} {activation.budget.actualSpend}</dd>
              <dt>Outstanding Reservations</dt>
              <dd>{activation.budget.currency} {activation.budget.outstandingReservations}</dd>
              <dt>Available</dt>
              <dd>{activation.budget.currency} {activation.budget.available}</dd>
              <dt>Period</dt>
              <dd>{new Date(activation.budget.periodStart).toLocaleDateString()} \u2013 {new Date(activation.budget.periodEnd).toLocaleDateString()}</dd>
              <dt>Account Version</dt>
              <dd>{activation.budget.accountVersion}</dd>
            </dl>

            {activation.budget.employeeAllocations.length > 0 && (
              <div>
                <h4>Employee Allocations</h4>
                <table className="review-table">
                  <thead>
                    <tr>
                      <th>Employee</th>
                      <th>Role</th>
                      <th>Contract</th>
                      <th>Monthly Limit</th>
                      <th>Monthly Spend</th>
                      <th>Available</th>
                      <th>Per-Task Limit</th>
                    </tr>
                  </thead>
                  <tbody>
                    {activation.budget.employeeAllocations.map((alloc) => (
                      <tr key={alloc.employeeId}>
                        <td className="mono">{alloc.employeeId}</td>
                        <td>{alloc.displayName}</td>
                        <td>{alloc.roleKey}</td>
                        <td>{alloc.currency} {alloc.monthlyLimit}</td>
                        <td>{alloc.currency} {alloc.monthlySpend}</td>
                        <td>{alloc.currency} {alloc.monthlyAvailable}</td>
                        <td>{alloc.currency} {alloc.perTaskLimit}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      )}

      <div className="activation-checklist">
        <h3>Pre-Activation Checklist</h3>
        <ul>
          <li className={activation?.company.status === 'draft' ? 'pass' : 'fail'}>
            Company is in draft status
          </li>
          <li className={activation && activation.workforce.length > 0 ? 'pass' : 'fail'}>
            Workforce configured ({activation?.workforce.length || 0} employees)
          </li>
          <li className={activation && activation.contracts.length > 0 ? 'pass' : 'fail'}>
            Contracts generated ({activation?.contracts.length || 0} contracts)
          </li>
          <li className={activation && activation.budget.monthlyLimit && parseFloat(activation.budget.monthlyLimit) > 0 ? 'pass' : 'fail'}>
            Budget ceiling set ({activation?.budget.currency} {activation?.budget.monthlyLimit || '\u2014'})
          </li>
          <li className="warning">
            \u26a0 Activation is irreversible \u2014 contracts become immutable
          </li>
          <li className="warning">
            \u26a0 Only one company can be active at a time
          </li>
        </ul>
      </div>

      <div className="step-actions">
        <button type="button" className="btn btn-secondary" onClick={onBack} disabled={isLoading || isSubmitting || isActivating}>
          \u2190 Back
        </button>
        {activationResult ? (
          <button type="button" className="btn btn-primary" onClick={() => onNext()} disabled={isActivating}>
            Complete Setup
          </button>
        ) : (
          <button
            type="button"
            className="btn btn-primary btn-activate"
            onClick={handleActivate}
            disabled={isLoading || isSubmitting || isActivating || !validateStep()}
          >
            {isActivating ? 'Activating\u2026' : 'Activate Company'}
          </button>
        )}
      </div>
    </div>
  );
}
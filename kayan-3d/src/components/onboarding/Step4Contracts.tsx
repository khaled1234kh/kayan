import { useState, useEffect } from 'react';
import type { ContractSummaryOut, ContractOut } from '../../api/onboarding';
import type { OnboardingState, WorkforceFormData } from './types';
import { onboardingApi } from '../../api/onboarding';

interface Step4ContractsProps {
  state: OnboardingState;
  onNext: () => Promise<void>;
  onBack: () => void;
  companyId: string;
  workforceForm: WorkforceFormData;
  onContractsGenerated: (contracts: ContractSummaryOut[]) => void;
}

export function Step4Contracts({
  state,
  onNext,
  onBack,
  companyId,
  workforceForm,
  onContractsGenerated,
}: Step4ContractsProps) {
  const { contractReview, isLoading, isSubmitting } = state;
  const [isGenerating, setIsGenerating] = useState(false);
  const [expandedContract, setExpandedContract] = useState<string | null>(null);
  const [allocations, setAllocations] = useState<Map<string, { budgetPerMonth: string; budgetPerTask: string }>>(
    new Map()
  );

  useEffect(() => {
    if (!contractReview && !isGenerating && companyId) {
      generateContracts();
    }
  }, [companyId, contractReview, isGenerating]);

  const generateContracts = async () => {
    setIsGenerating(true);
    try {
      // Build allocations from workforce
      const employees = workforceForm.mode === 'recommended'
        ? [] // Will be populated from recommendation
        : workforceForm.manualEmployees;

      // For now, we'll use equal allocation per employee
      // In a real implementation, this would be more sophisticated
      const allocationList = employees.map((emp, index) => ({
        employeeId: emp.id || `emp_${index}`,
        budgetPerMonth: '0',
        budgetPerTask: '0',
      }));

      // The actual allocation values need to come from the UI
      // For now, generate with placeholder allocations that will be validated by backend
      const contracts = await onboardingApi.generateContracts(companyId, {
        allocations: allocationList.map((a) => ({
          employeeId: a.employeeId,
          budgetPerMonth: a.budgetPerMonth || '1000',
          budgetPerTask: a.budgetPerTask || '100',
        })),
        replaceExisting: true,
      });

      onContractsGenerated(contracts);

      // Fetch full contract details
      const details = new Map<string, ContractOut>();
      for (const contract of contracts) {
        try {
          const detail = await onboardingApi.getContract(contract.id);
          details.set(contract.id, detail);
        } catch (e) {
          console.warn('Failed to fetch contract detail:', contract.id);
        }
      }

      // Update state with contract details (handled by parent)
    } catch (error) {
      console.error('Failed to generate contracts:', error);
    } finally {
      setIsGenerating(false);
    }
  };

  const handleAllocationChange = (employeeId: string, field: 'budgetPerMonth' | 'budgetPerTask', value: string) => {
    setAllocations((prev) => {
      const next = new Map(prev);
      const current = next.get(employeeId) || { budgetPerMonth: '0', budgetPerTask: '0' };
      next.set(employeeId, { ...current, [field]: value });
      return next;
    });
  };

  const validateStep = (): boolean => {
    if (!contractReview || contractReview.contracts.length === 0) {
      return false;
    }

    // Check that all contracts have allocations
    const newErrors: Record<string, string> = {};
    contractReview.contracts.forEach((contract) => {
      const alloc = contractReview?.allocations?.get(contract.employeeId);
      if (!alloc || parseFloat(alloc.budgetPerMonth) <= 0 || parseFloat(alloc.budgetPerTask) <= 0) {
        newErrors[`allocation_${contract.employeeId}`] = `Employee ${contract.employeeId}: Both monthly and per-task budgets must be positive`;
      }
    });

    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (validateStep()) {
      await onNext();
    }
  };

  if (isGenerating) {
    return (
      <div className="onboarding-step">
        <div className="step-header">
          <h2>Step 4 of 5 — Contract Review</h2>
        </div>
        <div className="loading-contracts">
          <div className="spinner" />
          <p>Generating contracts for all employees…</p>
        </div>
      </div>
    );
  }

  if (!contractReview || contractReview.contracts.length === 0) {
    return (
      <div className="onboarding-step">
        <div className="step-header">
          <h2>Step 4 of 5 — Contract Review</h2>
        </div>
        <p className="muted">No contracts generated yet. Please go back and complete the workforce step.</p>
        <div className="step-actions">
          <button type="button" className="btn btn-secondary" onClick={onBack} disabled={isLoading}>
            ← Back to Workforce
          </button>
        </div>
      </div>
    );
  }

  return (
    <form className="onboarding-step" onSubmit={handleSubmit}>
      <div className="step-header">
        <h2>Step 4 of 5 — Contract Review</h2>
        <p className="step-description">
          Review the generated contracts for each employee. Each contract defines the seat's
          authority, budgets, and permissions. Allocate monthly and per-task budgets below,
          then continue to activation.
        </p>
      </div>

      <div className="contracts-overview">
        <h3>Generated Contracts ({contractReview.contracts.length})</h3>
        <table className="contracts-table">
          <thead>
            <tr>
              <th>Employee</th>
              <th>Role</th>
              <th>Version</th>
              <th>Status</th>
              <th>Monthly Budget</th>
              <th>Per-Task Budget</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {contractReview.contracts.map((contract) => {
              const alloc = allocations.get(contract.employeeId) || { budgetPerMonth: '0', budgetPerTask: '0' };
              return (
                <tr key={contract.id} className={expandedContract === contract.id ? 'expanded' : ''}>
                  <td>{contract.employeeId}</td>
                  <td>{contract.role}</td>
                  <td>v{contract.versionNumber}</td>
                  <td><span className={`status-badge ${contract.status}`}>{contract.status}</span></td>
                  <td>
                    <input
                      type="text"
                      value={alloc.budgetPerMonth}
                      onChange={(e) => handleAllocationChange(contract.employeeId, 'budgetPerMonth', e.target.value)}
                      className="budget-input"
                      inputMode="decimal"
                    />
                  </td>
                  <td>
                    <input
                      type="text"
                      value={alloc.budgetPerTask}
                      onChange={(e) => handleAllocationChange(contract.employeeId, 'budgetPerTask', e.target.value)}
                      className="budget-input"
                      inputMode="decimal"
                    />
                  </td>
                  <td>
                    <button
                      type="button"
                      className="btn btn-sm"
                      onClick={() => setExpandedContract(expandedContract === contract.id ? null : contract.id)}
                    >
                      {expandedContract === contract.id ? 'Hide' : 'Details'}
                    </button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {expandedContract && contractReview.contractDetails.has(expandedContract) && (
        <div className="contract-detail-panel">
          <div className="detail-header">
            <h3>Contract Details — {expandedContract}</h3>
            <button type="button" className="btn-icon" onClick={() => setExpandedContract(null)}>×</button>
          </div>
          <ContractDetailView contract={contractReview.contractDetails.get(expandedContract)!} />
        </div>
      )}

      <div className="contract-validation">
        <h3>Validation</h3>
        <ul className="validation-checklist">
          <li className={contractReview.contracts.length > 0 ? 'pass' : 'fail'}>
            ✓ {contractReview.contracts.length} contract(s) generated
          </li>
          <li className={validateStep() ? 'pass' : 'fail'}>
            ✓ All budgets allocated (monthly &amp; per-task &gt; 0)
          </li>
          <li className="pass">
            ✓ Contracts are draft — editable before activation
          </li>
          <li className="pass">
            ✓ Hash integrity will be verified at activation
          </li>
        </ul>
      </div>

      <div className="step-actions">
        <button type="button" className="btn btn-secondary" onClick={onBack} disabled={isLoading || isSubmitting}>
          ← Back
        </button>
        <button type="submit" className="btn btn-primary" disabled={isLoading || isSubmitting || !validateStep()}>
          {isSubmitting ? 'Preparing activation…' : 'Continue to Activation'}
        </button>
      </div>
    </form>
  );
}

function ContractDetailView({ contract }: { contract: ContractOut }) {
  return (
    <div className="contract-detail">
      <div className="detail-grid">
        <div className="detail-section">
          <h4>Identity & Status</h4>
          <dl>
            <dt>Contract ID</dt>
            <dd className="mono">{contract.id}</dd>
            <dt>Employee ID</dt>
            <dd className="mono">{contract.employeeId}</dd>
            <dt>Version</dt>
            <dd>v{contract.versionNumber} (role config v{contract.roleConfigVersion})</dd>
            <dt>Status</dt>
            <dd><span className={`status-badge ${contract.status}`}>{contract.status}</span></dd>
            <dt>Source</dt>
            <dd>{contract.source}</dd>
            <dt>Content Hash</dt>
            <dd className="mono hash">{contract.contentHash}</dd>
          </dl>
        </div>

        <div className="detail-section">
          <h4>Role & Objective</h4>
          <dl>
            <dt>Role</dt>
            <dd>{contract.role}</dd>
            <dt>Objective</dt>
            <dd>{contract.objective || '—'}</dd>
            <dt>Responsibilities</dt>
            <dd>
              <ul>
                {contract.responsibilities.map((r, i) => <li key={i}>{r}</li>)}
              </ul>
            </dd>
          </dl>
        </div>

        <div className="detail-section">
          <h4>Permissions</h4>
          <dl>
            <dt>Data Scope</dt>
            <dd>
              <pre>{JSON.stringify(contract.dataScope, null, 2)}</pre>
            </dd>
            <dt>Tool Scope</dt>
            <dd>
              <pre>{JSON.stringify(contract.toolScope, null, 2)}</pre>
            </dd>
            <dt>Restrictions</dt>
            <dd>
              <ul>
                {contract.restrictions.map((r, i) => <li key={i}>{r}</li>)}
              </ul>
            </dd>
            <dt>Task Scope</dt>
            <dd>
              <ul>
                {contract.taskScope.map((t, i) => <li key={i}>{t}</li>)}
              </ul>
            </dd>
          </dl>
        </div>

        <div className="detail-section">
          <h4>Communication & Approval</h4>
          <dl>
            <dt>Communication Policy</dt>
            <dd>
              <pre>{JSON.stringify(contract.communicationPolicy, null, 2)}</pre>
            </dd>
            <dt>Approval Rules</dt>
            <dd>
              <pre>{JSON.stringify(contract.approvalRules, null, 2)}</pre>
            </dd>
            <dt>Requires Human Escalation</dt>
            <dd>{contract.requiresHumanEscalation ? 'Yes' : 'No'}</dd>
          </dl>
        </div>

        <div className="detail-section">
          <h4>Budgets</h4>
          <dl>
            <dt>Monthly Budget</dt>
            <dd>{contract.budgetPerMonth}</dd>
            <dt>Per-Task Budget</dt>
            <dd>{contract.budgetPerTask}</dd>
            <dt>Reports To</dt>
            <dd>{contract.reportsToEmployeeId || '—'}</dd>
          </dl>
        </div>

        <div className="detail-section">
          <h4>Timestamps</h4>
          <dl>
            <dt>Created</dt>
            <dd>{new Date(contract.createdAt).toLocaleString()}</dd>
            <dt>Effective</dt>
            <dd>{contract.effectiveAt ? new Date(contract.effectiveAt).toLocaleString() : '—'}</dd>
            <dt>Activated</dt>
            <dd>{contract.activatedAt ? new Date(contract.activatedAt).toLocaleString() : '—'}</dd>
            <dt>Superseded</dt>
            <dd>{contract.supersededAt ? new Date(contract.supersededAt).toLocaleString() : '—'}</dd>
            <dt>Supersedes</dt>
            <dd>{contract.supersedesId || '—'}</dd>
          </dl>
        </div>
      </div>
    </div>
  );
}
import { useState, useEffect } from 'react';
import type { RecommendationOut } from '../../api/onboarding';
import type { WorkforceFormData, ManualEmployee, OnboardingState } from './types';
import { onboardingApi } from '../../api/onboarding';

interface Step3WorkforceProps {
  state: OnboardingState;
  onFormChange: (form: Partial<WorkforceFormData>) => void;
  onNext: () => Promise<void>;
  onBack: () => void;
  companyId: string;
  companyTemplateKey: string;
  onRecommendationGenerated: (rec: RecommendationOut) => void;
  onWorkforceSubmitted: (workforce: WorkforceFormData) => void;
}

export function Step3Workforce({
  state,
  onFormChange,
  onNext,
  onBack,
  companyId,
  companyTemplateKey,
  onRecommendationGenerated,
  onWorkforceSubmitted,
}: Step3WorkforceProps) {
  const { workforceForm, availableRoles, recommendation, errors, isLoading, isSubmitting } = state;
  const [isGeneratingRecommendation, setIsGeneratingRecommendation] = useState(false);

  useEffect(() => {
    if (workforceForm.mode === 'recommended' && !recommendation && !isGeneratingRecommendation) {
      generateRecommendation();
    }
  }, [workforceForm.mode, recommendation, isGeneratingRecommendation]);

  const generateRecommendation = async () => {
    setIsGeneratingRecommendation(true);
    onFormChange({ mode: 'recommended' });
    try {
      const rec = await onboardingApi.createRecommendation({
        companyId,
        preferences: {
          desiredEmployeeCount: undefined,
          includeHumanEmployee: true,
          includeHR: true,
          notes: 'Initial onboarding recommendation',
        },
      });
      onRecommendationGenerated(rec);
    } catch (error) {
      onFormChange({ mode: 'manual' });
      console.error('Failed to generate recommendation:', error);
    } finally {
      setIsGeneratingRecommendation(false);
    }
  };

  const addManualEmployee = () => {
    const newEmployee: ManualEmployee = {
      displayName: '',
      kind: 'human',
      roleKey: '',
      responsibilities: [],
    };
    onFormChange({
      manualEmployees: [...workforceForm.manualEmployees, newEmployee],
    });
  };

  const updateManualEmployee = (index: number, updates: Partial<ManualEmployee>) => {
    const updated = [...workforceForm.manualEmployees];
    updated[index] = { ...updated[index], ...updates };
    onFormChange({ manualEmployees: updated });
  };

  const removeManualEmployee = (index: number) => {
    const updated = workforceForm.manualEmployees.filter((_, i) => i !== index);
    onFormChange({ manualEmployees: updated });
  };

  const handleModeChange = (mode: 'manual' | 'recommended') => {
    onFormChange({ mode });
    if (mode === 'recommended' && !recommendation) {
      generateRecommendation();
    }
  };

  const acceptRecommendation = () => {
    if (recommendation) {
      const employees: ManualEmployee[] = recommendation.proposal.employees.map((emp) => ({
        displayName: emp.displayName,
        kind: emp.kind,
        roleKey: emp.roleKey,
        objective: emp.objective || undefined,
        responsibilities: emp.responsibilities,
        reportsToId: emp.reportsToKey || undefined,
      }));
      onFormChange({
        mode: 'manual',
        manualEmployees: employees,
      });
      onWorkforceSubmitted({ mode: 'manual', manualEmployees: employees });
    }
  };

  const validateStep = (): boolean => {
    const newErrors: Record<string, string> = {};

    if (workforceForm.mode === 'manual') {
      if (workforceForm.manualEmployees.length === 0) {
        newErrors.workforce = 'At least one employee is required';
      } else {
        workforceForm.manualEmployees.forEach((emp, index) => {
          if (!emp.displayName.trim()) {
            newErrors[`employee_${index}_name`] = `Employee ${index + 1}: Display name is required`;
          }
          if (!emp.roleKey) {
            newErrors[`employee_${index}_role`] = `Employee ${index + 1}: Role is required`;
          }
          const role = availableRoles.find((r) => r.key === emp.roleKey);
          if (role && role.kind !== emp.kind) {
            newErrors[`employee_${index}_kind`] = `Employee ${index + 1}: Kind must match role (${role.kind})`;
          }
        });
      }
    } else if (workforceForm.mode === 'recommended' && !recommendation) {
      newErrors.workforce = 'Generating recommendation… please wait';
    }

    Object.keys(newErrors).forEach((key) => {
      const field = key as keyof WorkforceFormData;
      onFormChange({ [field]: newErrors[key] } as Partial<WorkforceFormData>);
    });

    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (validateStep()) {
      onWorkforceSubmitted(workforceForm);
      await onNext();
    }
  };

  const templateRoles = availableRoles.filter((r) => r.templateKeys.includes(companyTemplateKey));

  return (
    <form className="onboarding-step" onSubmit={handleSubmit}>
      <div className="step-header">
        <h2>Step 3 of 5 — Workforce</h2>
        <p className="step-description">
          Configure your team. Choose <strong>AI-recommended</strong> for a tailored roster based on
          your budget and template, or <strong>Manual</strong> to build it yourself.
        </p>
      </div>

      <div className="mode-selector">
        <label className={`mode-option ${workforceForm.mode === 'recommended' ? 'active' : ''}`}>
          <input
            type="radio"
            name="workforceMode"
            value="recommended"
            checked={workforceForm.mode === 'recommended'}
            onChange={() => handleModeChange('recommended')}
            disabled={isLoading || isSubmitting}
          />
          <div className="mode-content">
            <span className="mode-icon">🤖</span>
            <div>
              <strong>AI-Recommended Setup</strong>
              <span>Backend generates a tailored workforce from your template and budget</span>
            </div>
          </div>
        </label>
        <label className={`mode-option ${workforceForm.mode === 'manual' ? 'active' : ''}`}>
          <input
            type="radio"
            name="workforceMode"
            value="manual"
            checked={workforceForm.mode === 'manual'}
            onChange={() => handleModeChange('manual')}
            disabled={isLoading || isSubmitting}
          />
          <div className="mode-content">
            <span className="mode-icon">✏️</span>
            <div>
              <strong>Manual Configuration</strong>
              <span>Build your team role by role with full control</span>
            </div>
          </div>
        </label>
      </div>

      {workforceForm.mode === 'recommended' && (
        <div className="recommendation-section">
          {isGeneratingRecommendation ? (
            <div className="loading-recommendation">
              <div className="spinner" />
              <p>Generating tailored workforce recommendation…</p>
            </div>
          ) : recommendation ? (
            <div className="recommendation-card">
              <div className="recommendation-header">
                <h3>Recommended Workforce ({recommendation.proposal.employees.length} seats)</h3>
                <span className={`source-badge ${recommendation.proposal.source}`}>
                  {recommendation.proposal.source === 'template' ? 'Template-based' : 'Model-generated'}
                </span>
              </div>

              {recommendation.proposal.warnings.length > 0 && (
                <div className="recommendation-warnings">
                  {recommendation.proposal.warnings.map((w, i) => (
                    <div key={i} className="warning">{w}</div>
                  ))}
                </div>
              )}

              <div className="recommendation-budget">
                <dl>
                  <dt>Company Ceiling</dt>
                  <dd>{recommendation.proposal.budget.currency} {recommendation.proposal.budget.companyMonthlyCeiling}</dd>
                  <dt>Allocated</dt>
                  <dd>{recommendation.proposal.budget.currency} {recommendation.proposal.budget.totalSuggestedMonthly}</dd>
                  <dt>Unallocated</dt>
                  <dd>{recommendation.proposal.budget.currency} {recommendation.proposal.budget.unallocatedMonthly}</dd>
                </dl>
              </div>

              <div className="recommendation-employees">
                {recommendation.proposal.employees.map((emp) => (
                  <div key={emp.key} className="recommended-employee">
                    <div className="emp-main">
                      <span className="emp-name">{emp.displayName}</span>
                      <span className="emp-role">{emp.roleKey} ({emp.kind})</span>
                    </div>
                    <div className="emp-details">
                      <span>Monthly: {recommendation.proposal.budget.currency} {emp.suggestedMonthlyBudget}</span>
                      <span>Per-task: {recommendation.proposal.budget.currency} {emp.suggestedPerTaskBudget}</span>
                      {emp.reportsToKey && <span>Reports to: {emp.reportsToKey}</span>}
                    </div>
                    <details className="emp-rationale">
                      <summary>Rationale</summary>
                      <p>{emp.rationale}</p>
                    </details>
                  </div>
                ))}
              </div>

              <div className="recommendation-actions">
                <button
                  type="button"
                  className="btn btn-primary"
                  onClick={acceptRecommendation}
                  disabled={isSubmitting}
                >
                  Accept & Customize
                </button>
                <button
                  type="button"
                  className="btn btn-secondary"
                  onClick={() => handleModeChange('manual')}
                  disabled={isSubmitting}
                >
                  Configure Manually Instead
                </button>
              </div>
            </div>
          ) : (
            <p className="muted">No recommendation available. Switch to manual mode or try again.</p>
          )}
        </div>
      )}

      {workforceForm.mode === 'manual' && (
        <div className="manual-workforce-section">
          <div className="section-header">
            <h3>Team Members ({workforceForm.manualEmployees.length})</h3>
            <button type="button" className="btn btn-secondary btn-sm" onClick={addManualEmployee} disabled={isSubmitting}>
              + Add Employee
            </button>
          </div>

          {workforceForm.manualEmployees.length === 0 ? (
            <p className="muted">No employees added yet. Click "Add Employee" to start building your team.</p>
          ) : (
            <div className="employees-list">
              {workforceForm.manualEmployees.map((emp, index) => (
                <div key={index} className="employee-card">
                  <div className="employee-header">
                    <span className="employee-number">#{index + 1}</span>
                    <button
                      type="button"
                      className="btn-icon btn-danger"
                      onClick={() => removeManualEmployee(index)}
                      disabled={isSubmitting}
                      aria-label={`Remove employee ${index + 1}`}
                    >
                      ×
                    </button>
                  </div>

                  <div className="form-grid">
                    <div className="form-field">
                      <label htmlFor={`emp-${index}-name`}>Display Name *</label>
                      <input
                        id={`emp-${index}-name`}
                        type="text"
                        value={emp.displayName}
                        onChange={(e) => updateManualEmployee(index, { displayName: e.target.value })}
                        placeholder="e.g., Sarah Ahmed"
                        maxLength={160}
                        disabled={isSubmitting}
                        className={errors[`employee_${index}_name`] ? 'has-error' : ''}
                      />
                      {errors[`employee_${index}_name`] && (
                        <span className="field-error">{errors[`employee_${index}_name`]}</span>
                      )}
                    </div>

                    <div className="form-field">
                      <label htmlFor={`emp-${index}-kind`}>Kind *</label>
                      <select
                        id={`emp-${index}-kind`}
                        value={emp.kind}
                        onChange={(e) => updateManualEmployee(index, { kind: e.target.value as 'human' | 'ai' })}
                        disabled={isSubmitting}
                        className={errors[`employee_${index}_kind`] ? 'has-error' : ''}
                      >
                        <option value="human">Human</option>
                        <option value="ai">AI Agent</option>
                      </select>
                      {errors[`employee_${index}_kind`] && (
                        <span className="field-error">{errors[`employee_${index}_kind`]}</span>
                      )}
                    </div>

                    <div className="form-field">
                      <label htmlFor={`emp-${index}-role`}>Role *</label>
                      <select
                        id={`emp-${index}-role`}
                        value={emp.roleKey}
                        onChange={(e) => updateManualEmployee(index, { roleKey: e.target.value })}
                        disabled={isSubmitting}
                        className={errors[`employee_${index}_role`] ? 'has-error' : ''}
                      >
                        <option value="">Select a role…</option>
                        {templateRoles.map((role) => (
                          <option key={role.key} value={role.key}>
                            {role.label} ({role.key})
                          </option>
                        ))}
                      </select>
                      {errors[`employee_${index}_role`] && (
                        <span className="field-error">{errors[`employee_${index}_role`]}</span>
                      )}
                    </div>

                    <div className="form-field">
                      <label htmlFor={`emp-${index}-customRole`}>Custom Role</label>
                      <input
                        id={`emp-${index}-customRole`}
                        type="text"
                        value={emp.customRole || ''}
                        onChange={(e) => updateManualEmployee(index, { customRole: e.target.value })}
                        placeholder="Custom role name (if not using template role)"
                        maxLength={160}
                        disabled={isSubmitting}
                      />
                    </div>

                    <div className="form-field full-width">
                      <label htmlFor={`emp-${index}-objective`}>Objective</label>
                      <textarea
                        id={`emp-${index}-objective`}
                        value={emp.objective || ''}
                        onChange={(e) => updateManualEmployee(index, { objective: e.target.value })}
                        placeholder="What this seat is responsible for achieving"
                        maxLength={2000}
                        rows={2}
                        disabled={isSubmitting}
                      />
                    </div>

                    <div className="form-field full-width">
                      <label>Responsibilities</label>
                      <div className="responsibilities-input">
                        {emp.responsibilities.map((resp, respIndex) => (
                          <div key={respIndex} className="responsibility-row">
                            <input
                              type="text"
                              value={resp}
                              onChange={(e) => {
                                const updated = [...emp.responsibilities];
                                updated[respIndex] = e.target.value;
                                updateManualEmployee(index, { responsibilities: updated });
                              }}
                              placeholder="e.g., Manage customer relationships"
                              maxLength={200}
                              disabled={isSubmitting}
                            />
                            <button
                              type="button"
                              className="btn-icon btn-sm"
                              onClick={() => {
                                const updated = emp.responsibilities.filter((_, i) => i !== respIndex);
                                updateManualEmployee(index, { responsibilities: updated });
                              }}
                              disabled={isSubmitting}
                              aria-label="Remove responsibility"
                            >
                              ×
                            </button>
                          </div>
                        ))}
                        <button
                          type="button"
                          className="btn btn-secondary btn-sm"
                          onClick={() => updateManualEmployee(index, {
                            responsibilities: [...emp.responsibilities, '']
                          })}
                          disabled={isSubmitting}
                        >
                          + Add Responsibility
                        </button>
                      </div>
                    </div>

                    <div className="form-field">
                      <label htmlFor={`emp-${index}-reportsTo`}>Reports To (Employee ID)</label>
                      <input
                        id={`emp-${index}-reportsTo`}
                        type="text"
                        value={emp.reportsToId || ''}
                        onChange={(e) => updateManualEmployee(index, { reportsToId: e.target.value })}
                        placeholder="emp_… (leave blank for top-level)"
                        maxLength={64}
                        disabled={isSubmitting}
                      />
                      <p className="field-hint">
                        Enter the employee ID this seat reports to. Cycles and cross-company
                        references are rejected by the backend.
                      </p>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      <div className="step-actions">
        <button type="button" className="btn btn-secondary" onClick={onBack} disabled={isLoading || isSubmitting}>
          ← Back
        </button>
        <button type="submit" className="btn btn-primary" disabled={isLoading || isSubmitting}>
          {isSubmitting ? 'Submitting workforce…' : 'Continue to Contracts'}
        </button>
      </div>
    </form>
  );
}
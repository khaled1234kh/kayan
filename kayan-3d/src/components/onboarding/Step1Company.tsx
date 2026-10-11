import { useEffect } from 'react';
import type { CompanyFormData, OnboardingState } from './types';
import { onboardingApi } from '../../api/onboarding';

interface Step1CompanyProps {
  state: OnboardingState;
  onFormChange: (form: Partial<CompanyFormData>) => void;
  onNext: () => Promise<void>;
  onLoadTemplates: () => Promise<void>;
}

export function Step1Company({ state, onFormChange, onNext, onLoadTemplates }: Step1CompanyProps) {
  const { companyForm, availableTemplates, availableRoles, errors, isLoading } = state;

  useEffect(() => {
    onLoadTemplates();
  }, [onLoadTemplates]);

  useEffect(() => {
    if (companyForm.templateKey) {
      onboardingApi.listRoles(companyForm.templateKey);
    }
  }, [companyForm.templateKey]);

  const handleTemplateChange = (templateKey: string) => {
    onFormChange({ templateKey });
    onboardingApi.listRoles(templateKey);
  };

  const validateStep = (): boolean => {
    const newErrors: Record<string, string> = {};

    if (!companyForm.templateKey) {
      newErrors.templateKey = 'Please select an industry template';
    }
    if (!companyForm.name.trim()) {
      newErrors.name = 'Company name is required';
    }
    if (companyForm.name.length > 160) {
      newErrors.name = 'Company name must be 160 characters or fewer';
    }

    // Target coherence validation (matching backend)
    const hasMetric = companyForm.targetMetric.trim().length > 0;
    const hasValue = companyForm.targetValue.trim().length > 0;
    if (hasMetric && !hasValue) {
      newErrors.targetValue = 'Target value is required when target metric is set';
    }
    if (hasValue && !hasMetric) {
      newErrors.targetMetric = 'Target metric is required when target value is set';
    }
    if (hasValue && parseFloat(companyForm.targetValue) <= 0) {
      newErrors.targetValue = 'Target value must be greater than zero';
    }

    Object.keys(newErrors).forEach((key) => onFormChange({ [key]: newErrors[key] } as Partial<CompanyFormData>));

    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (validateStep()) {
      await onNext();
    }
  };

  return (
    <form className="onboarding-step" onSubmit={handleSubmit}>
      <div className="step-header">
        <h2>Step 1 of 5 — Company</h2>
        <p className="step-description">
          Define your company's identity and industry template. The template determines
          which roles and workflows are available for your workforce.
        </p>
      </div>

      <div className="form-grid">
        <div className="form-field">
          <label htmlFor="templateKey">Industry Template *</label>
          <select
            id="templateKey"
            value={companyForm.templateKey}
            onChange={(e) => handleTemplateChange(e.target.value)}
            disabled={isLoading}
            className={errors.templateKey ? 'has-error' : ''}
          >
            <option value="">Select a template…</option>
            {availableTemplates.map((template) => (
              <option key={template.key} value={template.key}>
                {template.label} — {template.summary}
              </option>
            ))}
          </select>
          {errors.templateKey && <span className="field-error">{errors.templateKey}</span>}
          <p className="field-hint">
            Choose the template that best matches your business. This determines
            available roles and default workflows.
          </p>
        </div>

        <div className="form-field">
          <label htmlFor="name">Company Name *</label>
          <input
            id="name"
            type="text"
            value={companyForm.name}
            onChange={(e) => onFormChange({ name: e.target.value })}
            placeholder="Acme Textiles Ltd."
            maxLength={160}
            disabled={isLoading}
            className={errors.name ? 'has-error' : ''}
          />
          {errors.name && <span className="field-error">{errors.name}</span>}
        </div>

        <div className="form-field">
          <label htmlFor="industry">Industry</label>
          <input
            id="industry"
            type="text"
            value={companyForm.industry}
            onChange={(e) => onFormChange({ industry: e.target.value })}
            placeholder="e.g., Clothing Manufacturing"
            maxLength={120}
            disabled={isLoading}
          />
          <p className="field-hint">Optional. Used for reporting and benchmarking.</p>
        </div>
      </div>

      <fieldset className="form-section">
        <legend>Company Target (Optional)</legend>
        <p className="section-description">
          Define a measurable objective for your company. All fields must be filled together
          or left empty — a metric without a value (or vice versa) is not accepted.
        </p>

        <div className="form-grid">
          <div className="form-field">
            <label htmlFor="targetDescription">Target Description</label>
            <textarea
              id="targetDescription"
              value={companyForm.targetDescription}
              onChange={(e) => onFormChange({ targetDescription: e.target.value })}
              placeholder="e.g., Achieve 10,000 units sold per quarter"
              maxLength={2000}
              rows={2}
              disabled={isLoading}
            />
          </div>

          <div className="form-field">
            <label htmlFor="targetMetric">Metric *</label>
            <input
              id="targetMetric"
              type="text"
              value={companyForm.targetMetric}
              onChange={(e) => onFormChange({ targetMetric: e.target.value })}
              placeholder="e.g., Units sold"
              maxLength={64}
              disabled={isLoading}
              className={errors.targetMetric ? 'has-error' : ''}
            />
            {errors.targetMetric && <span className="field-error">{errors.targetMetric}</span>}
          </div>

          <div className="form-field">
            <label htmlFor="targetValue">Value *</label>
            <input
              id="targetValue"
              type="number"
              step="0.01"
              min="0.01"
              value={companyForm.targetValue}
              onChange={(e) => onFormChange({ targetValue: e.target.value })}
              placeholder="10000"
              disabled={isLoading}
              className={errors.targetValue ? 'has-error' : ''}
            />
            {errors.targetValue && <span className="field-error">{errors.targetValue}</span>}
          </div>

          <div className="form-field">
            <label htmlFor="targetUnit">Unit</label>
            <input
              id="targetUnit"
              type="text"
              value={companyForm.targetUnit}
              onChange={(e) => onFormChange({ targetUnit: e.target.value })}
              placeholder="e.g., units"
              maxLength={32}
              disabled={isLoading}
            />
          </div>

          <div className="form-field">
            <label htmlFor="targetPeriod">Period *</label>
            <select
              id="targetPeriod"
              value={companyForm.targetPeriod}
              onChange={(e) => onFormChange({ targetPeriod: e.target.value as CompanyFormData['targetPeriod'] })}
              disabled={isLoading}
            >
              <option value="total">Total (cumulative)</option>
              <option value="month">Month</option>
              <option value="quarter">Quarter</option>
              <option value="year">Year</option>
            </select>
          </div>
        </div>
      </fieldset>

      <div className="template-roles-preview">
        <h3>Roles Available in This Template</h3>
        {companyForm.templateKey && availableRoles.length > 0 ? (
          <div className="roles-grid">
            {availableRoles
              .filter((r) => r.templateKeys.includes(companyForm.templateKey))
              .map((role) => (
                <div key={role.key} className="role-card">
                  <div className="role-header">
                    <span className="role-badge">{role.key}</span>
                    <span className="role-kind">{role.kind}</span>
                  </div>
                  <h4>{role.label}</h4>
                  <p>{role.summary || 'No description'}</p>
                  <div className="role-meta">
                    <span>Responsibilities: {role.responsibilities.length}</span>
                    <span>Task categories: {role.taskCategories.length}</span>
                  </div>
                </div>
              ))}
          </div>
        ) : companyForm.templateKey ? (
          <p className="muted">No roles found for this template.</p>
        ) : (
          <p className="muted">Select a template to see available roles.</p>
        )}
      </div>

      <div className="step-actions">
        <button type="submit" className="btn btn-primary" disabled={isLoading}>
          {isLoading ? 'Creating company…' : 'Continue to Budget'}
        </button>
      </div>
    </form>
  );
}
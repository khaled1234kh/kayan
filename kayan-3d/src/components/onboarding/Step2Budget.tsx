import type { BudgetFormData, OnboardingState } from './types';

interface Step2BudgetProps {
  state: OnboardingState;
  onFormChange: (form: Partial<BudgetFormData>) => void;
  onNext: () => Promise<void>;
  onBack: () => void;
}

export function Step2Budget({ state, onFormChange, onNext, onBack }: Step2BudgetProps) {
  const { budgetForm, errors, isLoading, isSubmitting } = state;

  const validateStep = (): boolean => {
    const newErrors: Record<string, string> = {};

    const budgetValue = parseFloat(budgetForm.monthlyBudget);
    if (!budgetForm.monthlyBudget.trim()) {
      newErrors.monthlyBudget = 'Monthly budget is required';
    } else if (isNaN(budgetValue) || budgetValue <= 0) {
      newErrors.monthlyBudget = 'Monthly budget must be a positive number';
    } else if (budgetValue > 999999999999.999999) {
      newErrors.monthlyBudget = 'Budget exceeds maximum precision (18 digits, 6 decimal places)';
    } else {
      // Check decimal places
      const decimalPart = budgetForm.monthlyBudget.split('.')[1];
      if (decimalPart && decimalPart.length > 6) {
        newErrors.monthlyBudget = 'Budget cannot have more than 6 decimal places';
      }
    }

    Object.keys(newErrors).forEach((key) => onFormChange({ [key]: newErrors[key] } as Partial<BudgetFormData>));

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
        <h2>Step 2 of 5 — Budget</h2>
        <p className="step-description">
          Set your company's monthly budget ceiling. This is a hard limit — no spending can exceed
          this amount in any given month. All amounts are stored with exact decimal precision.
        </p>
      </div>

      <div className="form-grid">
        <div className="form-field">
          <label htmlFor="monthlyBudget">Monthly Budget *</label>
          <div className="budget-input-wrapper">
            <span className="currency-prefix">{budgetForm.currency === 'EGP' ? 'EGP' : '$'}</span>
            <input
              id="monthlyBudget"
              type="text"
              value={budgetForm.monthlyBudget}
              onChange={(e) => onFormChange({ monthlyBudget: e.target.value })}
              placeholder="e.g., 50000.00"
              maxLength={24}
              disabled={isLoading || isSubmitting}
              className={errors.monthlyBudget ? 'has-error' : ''}
              inputMode="decimal"
            />
          </div>
          {errors.monthlyBudget && <span className="field-error">{errors.monthlyBudget}</span>}
          <p className="field-hint">
            The maximum your company can spend per month. Must be a positive decimal with
            up to 6 decimal places (e.g., 50000.00). This ceiling is enforced server-side.
          </p>
        </div>

        <div className="form-field">
          <label htmlFor="currency">Currency *</label>
          <select
            id="currency"
            value={budgetForm.currency}
            onChange={(e) => onFormChange({ currency: e.target.value as BudgetFormData['currency'] })}
            disabled={isLoading || isSubmitting}
          >
            <option value="EGP">EGP — Egyptian Pound</option>
            <option value="USD">USD — US Dollar</option>
          </select>
          <p className="field-hint">
            Currency cannot be changed after company creation. All contracts and budgets
            use this currency.
          </p>
        </div>
      </div>

      <div className="budget-preview">
        <h3>Budget Summary</h3>
        <dl className="summary-list">
          <dt>Monthly Ceiling</dt>
          <dd>
            {budgetForm.currency === 'EGP' ? 'EGP' : '$'}{budgetForm.monthlyBudget || '—'}
          </dd>
          <dt>Currency</dt>
          <dd>{budgetForm.currency}</dd>
          <dt>Enforcement</dt>
          <dd>Server-side hard limit — no exceptions</dd>
        </dl>
      </div>

      <div className="step-actions">
        <button type="button" className="btn btn-secondary" onClick={onBack} disabled={isLoading || isSubmitting}>
          ← Back
        </button>
        <button type="submit" className="btn btn-primary" disabled={isLoading || isSubmitting}>
          {isSubmitting ? 'Creating budget…' : 'Continue to Workforce'}
        </button>
      </div>
    </form>
  );
}
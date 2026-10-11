import { useState, useCallback, useEffect } from 'react';
import { Step1Company } from './Step1Company';
import { Step2Budget } from './Step2Budget';
import { Step3Workforce } from './Step3Workforce';
import { Step4Contracts } from './Step4Contracts';
import { Step5Activation } from './Step5Activation';
import type {
  OnboardingState,
  CompanyFormData,
  BudgetFormData,
  WorkforceFormData,
  RecommendationOut,
  ContractSummaryOut,
  ContractOut,
} from './types';
import { onboardingApi } from '../../api/onboarding';
import { initialOnboardingState } from './types';

interface OnboardingWizardProps {
  onComplete: (companyId: string) => void;
  onCancel: () => void;
}

export function OnboardingWizard({ onComplete, onCancel }: OnboardingWizardProps) {
  const [state, setState] = useState<OnboardingState>(initialOnboardingState);

  const updateCompanyForm = useCallback((updates: Partial<CompanyFormData>) => {
    setState((prev) => ({
      ...prev,
      companyForm: { ...prev.companyForm, ...updates },
      errors: { ...prev.errors, ...Object.fromEntries(Object.keys(updates).map((k) => [k, ''])) },
    }));
  }, []);

  const updateBudgetForm = useCallback((updates: Partial<BudgetFormData>) => {
    setState((prev) => ({
      ...prev,
      budgetForm: { ...prev.budgetForm, ...updates },
      errors: { ...prev.errors, ...Object.fromEntries(Object.keys(updates).map((k) => [k, ''])) },
    }));
  }, []);

  const updateWorkforceForm = useCallback((updates: Partial<WorkforceFormData>) => {
    setState((prev) => ({
      ...prev,
      workforceForm: { ...prev.workforceForm, ...updates },
      errors: { ...prev.errors, ...Object.fromEntries(Object.keys(updates).map((k) => [k, ''])) },
    }));
  }, []);

  const loadTemplates = useCallback(async () => {
    setState((prev) => ({ ...prev, isLoading: true }));
    try {
      const templates = await onboardingApi.listTemplates();
      setState((prev) => ({ ...prev, availableTemplates: templates, isLoading: false }));
    } catch (error) {
      setState((prev) => ({ ...prev, isLoading: false, errors: { ...prev.errors, templates: 'Failed to load templates' } }));
    }
  }, []);

  const loadRolesForTemplate = useCallback(async (templateKey: string) => {
    try {
      const roles = await onboardingApi.listRoles(templateKey);
      setState((prev) => ({ ...prev, availableRoles: roles }));
    } catch (error) {
      console.error('Failed to load roles:', error);
    }
  }, []);

  const handleStep1Next = useCallback(async () => {
    setState((prev) => ({ ...prev, isSubmitting: true }));
    try {
      const company = await onboardingApi.createCompany({
        name: state.companyForm.name,
        templateKey: state.companyForm.templateKey,
        monthlyBudget: state.budgetForm.monthlyBudget,
        currency: state.budgetForm.currency,
        industry: state.companyForm.industry || undefined,
        targetDescription: state.companyForm.targetDescription || undefined,
        targetMetric: state.companyForm.targetMetric || undefined,
        targetValue: state.companyForm.targetValue || undefined,
        targetUnit: state.companyForm.targetUnit || undefined,
        targetPeriod: state.companyForm.targetPeriod,
      });
      setState((prev) => ({
        ...prev,
        companyId: company.id,
        currentStep: 2,
        isSubmitting: false,
      }));
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Failed to create company';
      setState((prev) => ({
        ...prev,
        isSubmitting: false,
        errors: { ...prev.errors, submit: message },
      }));
    }
  }, [state.companyForm, state.budgetForm]);

  const handleStep2Next = useCallback(async () => {
    if (!state.companyId) return;
    setState((prev) => ({ ...prev, isSubmitting: true }));
    try {
      await onboardingApi.updateCompany(state.companyId, {
        monthlyBudget: state.budgetForm.monthlyBudget,
        currency: state.budgetForm.currency,
      });
      setState((prev) => ({ ...prev, currentStep: 3, isSubmitting: false }));
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Failed to update budget';
      setState((prev) => ({
        ...prev,
        isSubmitting: false,
        errors: { ...prev.errors, submit: message },
      }));
    }
  }, [state.companyId, state.budgetForm]);

  const handleRecommendationGenerated = useCallback((rec: RecommendationOut) => {
    setState((prev) => ({ ...prev, recommendation: rec }));
  }, []);

  const handleWorkforceSubmitted = useCallback((workforce: WorkforceFormData) => {
    // Store the workforce for later use
    setState((prev) => ({ ...prev, workforceForm: workforce }));
  }, []);

  const handleStep3Next = useCallback(async () => {
    if (!state.companyId) return;
    setState((prev) => ({ ...prev, isSubmitting: true }));
    try {
      if (state.workforceForm.mode === 'manual') {
        await onboardingApi.replaceWorkforce(state.companyId, {
          employees: state.workforceForm.manualEmployees.map((emp) => ({
            displayName: emp.displayName,
            kind: emp.kind,
            roleKey: emp.roleKey,
            customRole: emp.customRole,
            objective: emp.objective,
            responsibilities: emp.responsibilities,
            reportsToId: emp.reportsToId,
          })),
        });
      } else if (state.recommendation) {
        const employees = state.recommendation.proposal.employees.map((emp) => ({
          displayName: emp.displayName,
          kind: emp.kind,
          roleKey: emp.roleKey,
          objective: emp.objective || undefined,
          responsibilities: emp.responsibilities,
          reportsToId: emp.reportsToKey || undefined,
        }));
        await onboardingApi.replaceWorkforce(state.companyId, { employees });
      }
      setState((prev) => ({ ...prev, currentStep: 4, isSubmitting: false }));
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Failed to configure workforce';
      setState((prev) => ({
        ...prev,
        isSubmitting: false,
        errors: { ...prev.errors, submit: message },
      }));
    }
  }, [state.companyId, state.workforceForm, state.recommendation]);

  const handleContractsGenerated = useCallback((contracts: ContractSummaryOut[]) => {
    const details = new Map<string, ContractOut>();
    const allocations = new Map<string, { budgetPerMonth: string; budgetPerTask: string }>();

    contracts.forEach((contract) => {
      allocations.set(contract.employeeId, { budgetPerMonth: '1000', budgetPerTask: '100' });
    });

    setState((prev) => ({
      ...prev,
      contractReview: {
        contracts,
        contractDetails: details,
        allocations,
      },
    }));

    // Fetch full contract details
    contracts.forEach(async (contract) => {
      try {
        const detail = await onboardingApi.getContract(contract.id);
        setState((prev) => {
          const newDetails = new Map(prev.contractReview?.contractDetails || []);
          newDetails.set(contract.id, detail);
          return {
            ...prev,
            contractReview: {
              ...prev.contractReview!,
              contractDetails: newDetails,
            },
          };
        });
      } catch (e) {
        console.warn('Failed to fetch contract detail:', contract.id);
      }
    });
  }, []);

  const handleStep4Next = useCallback(async () => {
    if (!state.companyId || !state.contractReview) return;
    setState((prev) => ({ ...prev, isSubmitting: true }));

    // Regenerate contracts with actual allocations
    try {
      const allocations = Array.from(state.contractReview.allocations.entries()).map(([employeeId, alloc]) => ({
        employeeId,
        budgetPerMonth: alloc.budgetPerMonth,
        budgetPerTask: alloc.budgetPerTask,
      }));

      const contracts = await onboardingApi.generateContracts(state.companyId, {
        allocations,
        replaceExisting: true,
      });

      const details = new Map<string, ContractOut>();
      for (const contract of contracts) {
        try {
          const detail = await onboardingApi.getContract(contract.id);
          details.set(contract.id, detail);
        } catch (e) {
          console.warn('Failed to fetch contract detail:', contract.id);
        }
      }

      setState((prev) => ({
        ...prev,
        contractReview: {
          ...prev.contractReview!,
          contracts,
          contractDetails: details,
        },
        isSubmitting: false,
      }));
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Failed to regenerate contracts';
      setState((prev) => ({
        ...prev,
        isSubmitting: false,
        errors: { ...prev.errors, submit: message },
      }));
    }
  }, [state.companyId, state.contractReview]);

  const loadActivationData = useCallback(async () => {
    if (!state.companyId) return;
    setState((prev) => ({ ...prev, isLoading: true }));
    try {
      const [company, workforce, contracts, budget] = await Promise.all([
        onboardingApi.getCompany(state.companyId),
        onboardingApi.getWorkforce(state.companyId),
        onboardingApi.listContracts(state.companyId),
        onboardingApi.getBudget(state.companyId),
      ]);
      setState((prev) => ({
        ...prev,
        activation: {
          company,
          workforce: workforce.employees,
          contracts,
          budget,
        },
        isLoading: false,
      }));
    } catch (error) {
      console.error('Failed to load activation data:', error);
      setState((prev) => ({ ...prev, isLoading: false }));
    }
  }, [state.companyId]);

  const handleActivated = useCallback(() => {
    setState((prev) => ({
      ...prev,
      activation: {
        ...prev.activation!,
        company: { ...prev.activation!.company, status: 'active' },
      },
    }));
  }, []);

  const handleStep5Next = useCallback(async () => {
    if (state.activation) {
      onComplete(state.companyId!);
    }
  }, [state.activation, state.companyId, onComplete]);

  const handleBack = useCallback(() => {
    setState((prev) => {
      const nextStep = Math.max(1, prev.currentStep - 1) as OnboardingState['currentStep'];
      return { ...prev, currentStep: nextStep };
    });
  }, []);

  const handleCancel = useCallback(() => {
    onCancel();
  }, [onCancel]);

  // Load roles when template changes
  useEffect(() => {
    if (state.companyForm.templateKey) {
      loadRolesForTemplate(state.companyForm.templateKey);
    }
  }, [state.companyForm.templateKey, loadRolesForTemplate]);

  // Load activation data when reaching step 5
  useEffect(() => {
    if (state.currentStep === 5 && state.companyId && !state.activation) {
      loadActivationData();
    }
  }, [state.currentStep, state.companyId, state.activation, loadActivationData]);

  const renderStep = () => {
    switch (state.currentStep) {
      case 1:
        return (
          <Step1Company
            state={state}
            onFormChange={updateCompanyForm}
            onNext={handleStep1Next}
            onLoadTemplates={loadTemplates}
          />
        );
      case 2:
        return (
          <Step2Budget
            state={state}
            onFormChange={updateBudgetForm}
            onNext={handleStep2Next}
            onBack={handleBack}
          />
        );
      case 3:
        return (
          <Step3Workforce
            state={state}
            onFormChange={updateWorkforceForm}
            onNext={handleStep3Next}
            onBack={handleBack}
            companyId={state.companyId!}
            companyTemplateKey={state.companyForm.templateKey}
            onRecommendationGenerated={handleRecommendationGenerated}
            onWorkforceSubmitted={handleWorkforceSubmitted}
          />
        );
      case 4:
        return (
          <Step4Contracts
            state={state}
            onNext={handleStep4Next}
            onBack={handleBack}
            companyId={state.companyId!}
            workforceForm={state.workforceForm}
            onContractsGenerated={handleContractsGenerated}
          />
        );
      case 5:
        return (
          <Step5Activation
            state={state}
            onNext={handleStep5Next}
            onBack={handleBack}
            companyId={state.companyId!}
            onActivated={handleActivated}
          />
        );
    }
  };

  return (
    <div className="onboarding-wizard">
      <div className="wizard-progress">
        <ol className="progress-steps">
          {([1, 2, 3, 4, 5] as const).map((step) => (
            <li key={step} className={state.currentStep === step ? 'active' : state.currentStep > step ? 'completed' : ''}>
              <span className="step-number">{step}</span>
              <span className="step-label">
                {step === 1 && 'Company'}
                {step === 2 && 'Budget'}
                {step === 3 && 'Workforce'}
                {step === 4 && 'Contracts'}
                {step === 5 && 'Activation'}
              </span>
            </li>
          ))}
        </ol>
      </div>

      <div className="wizard-content">
        {renderStep()}
      </div>

      <div className="wizard-footer">
        <button type="button" className="btn btn-ghost" onClick={handleCancel}>
          Cancel
        </button>
      </div>
    </div>
  );
}
import type { TemplateOut, RoleOut, RecommendationOut, ContractSummaryOut, ContractOut, CompanyOut, EmployeeOut, BudgetSummaryOut, ActivationOut } from '../../api/onboarding';

export type { TemplateOut, RoleOut, RecommendationOut, ContractSummaryOut, ContractOut, CompanyOut, EmployeeOut, BudgetSummaryOut, ActivationOut };

export type OnboardingStep = 1 | 2 | 3 | 4 | 5;

export interface CompanyFormData {
  templateKey: string;
  name: string;
  industry: string;
  targetDescription: string;
  targetMetric: string;
  targetValue: string;
  targetUnit: string;
  targetPeriod: 'total' | 'month' | 'quarter' | 'year';
}

export interface BudgetFormData {
  monthlyBudget: string;
  currency: 'EGP' | 'USD';
}

export type WorkforceMode = 'manual' | 'recommended';

export interface ManualEmployee {
  id?: string;
  displayName: string;
  kind: 'human' | 'ai';
  roleKey: string;
  customRole?: string;
  objective?: string;
  responsibilities: string[];
  reportsToId?: string;
}

export interface WorkforceFormData {
  mode: WorkforceMode;
  manualEmployees: ManualEmployee[];
  recommendationId?: string;
}

export interface ContractReviewData {
  contracts: ContractSummaryOut[];
  contractDetails: Map<string, ContractOut>;
  allocations: Map<string, { budgetPerMonth: string; budgetPerTask: string }>;
}

export interface ActivationData {
  company: CompanyOut;
  workforce: EmployeeOut[];
  contracts: ContractSummaryOut[];
  budget: BudgetSummaryOut;
}

export interface OnboardingState {
  currentStep: OnboardingStep;
  companyId: string | null;
  companyForm: CompanyFormData;
  budgetForm: BudgetFormData;
  workforceForm: WorkforceFormData;
  availableTemplates: TemplateOut[];
  availableRoles: RoleOut[];
  recommendation: RecommendationOut | null;
  contractReview: ContractReviewData | null;
  activation: ActivationData | null;
  errors: Record<string, string>;
  isLoading: boolean;
  isSubmitting: boolean;
}

export const initialCompanyForm: CompanyFormData = {
  templateKey: '',
  name: '',
  industry: '',
  targetDescription: '',
  targetMetric: '',
  targetValue: '',
  targetUnit: '',
  targetPeriod: 'month',
};

export const initialBudgetForm: BudgetFormData = {
  monthlyBudget: '',
  currency: 'EGP',
};

export const initialWorkforceForm: WorkforceFormData = {
  mode: 'recommended',
  manualEmployees: [],
};

export const initialOnboardingState: OnboardingState = {
  currentStep: 1,
  companyId: null,
  companyForm: initialCompanyForm,
  budgetForm: initialBudgetForm,
  workforceForm: initialWorkforceForm,
  availableTemplates: [],
  availableRoles: [],
  recommendation: null,
  contractReview: null,
  activation: null,
  errors: {},
  isLoading: false,
  isSubmitting: false,
};
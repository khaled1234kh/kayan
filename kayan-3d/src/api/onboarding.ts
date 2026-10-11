import { apiUrl } from '../transport';

export interface CompanyCreate {
  name: string;
  templateKey: string;
  monthlyBudget: string;
  currency: 'EGP' | 'USD';
  industry?: string;
  targetDescription?: string;
  targetMetric?: string;
  targetValue?: string;
  targetUnit?: string;
  targetPeriod?: 'total' | 'month' | 'quarter' | 'year';
}

export interface CompanyOut {
  id: string;
  name: string;
  industry: string | null;
  templateKey: string;
  status: string;
  currency: string;
  revision: number;
  monthlyBudget: string | null;
  budgetPeriodStart: string | null;
  budgetPeriodEnd: string | null;
  targetDescription: string | null;
  targetMetric: string | null;
  targetValue: string | null;
  targetUnit: string | null;
  targetPeriod: string | null;
  createdAt: string;
  updatedAt: string;
}

export interface CompanyUpdate {
  name?: string;
  industry?: string;
  templateKey?: string;
  monthlyBudget?: string;
  currency?: string;
  targetDescription?: string;
  targetMetric?: string;
  targetValue?: string;
  targetUnit?: string;
  targetPeriod?: 'total' | 'month' | 'quarter' | 'year';
}

export interface EmployeeIn {
  displayName: string;
  kind: 'human' | 'ai';
  roleKey: string;
  customRole?: string;
  objective?: string;
  responsibilities?: string[];
  reportsToId?: string;
  id?: string;
  status?: 'draft';
  companyId?: string;
}

export interface WorkforceReplace {
  employees: EmployeeIn[];
}

export interface EmployeeOut {
  id: string;
  companyId: string;
  displayName: string;
  kind: string;
  roleKey: string;
  customRole: string | null;
  objective: string | null;
  responsibilities: string[];
  reportsToId: string | null;
  status: string;
}

export interface WorkforceOut {
  companyId: string;
  revision: number;
  employeeCount: number;
  employees: EmployeeOut[];
}

export interface TemplateOut {
  key: string;
  label: string;
  summary: string;
  industries: string[];
  roleKeys: string[];
  taskCategories: string[];
}

export interface RoleOut {
  key: string;
  label: string;
  kind: string;
  summary: string | null;
  responsibilities: string[];
  taskCategories: string[];
  defaultDataScope: Record<string, unknown>[];
  defaultToolScope: Record<string, unknown>[];
  defaultRestrictions: string[];
  templateKeys: string[];
  configVersion: number;
}

export interface RecommendationPreferences {
  desiredEmployeeCount?: number;
  includeHumanEmployee?: boolean;
  includeHR?: boolean;
  notes?: string;
}

export interface RecommendationRequest {
  companyId: string;
  preferences: RecommendationPreferences;
}

export interface ProposalKey {
  key: string;
}

export interface ProposedEmployee {
  key: string;
  displayName: string;
  kind: 'human' | 'ai';
  roleKey: string;
  roleConfigVersion: number;
  objective: string | null;
  responsibilities: string[];
  dataScope: Array<{ resource: string; operations: string[] }>;
  toolScope: Array<{ tool: string; actions: string[] }>;
  restrictions: string[];
  communication: {
    allow: string[];
    broadcast: boolean;
    maxRounds: number;
  };
  reportsToKey: string | null;
  suggestedMonthlyBudget: string;
  suggestedPerTaskBudget: string;
  rationale: string;
}

export interface BudgetSummary {
  companyMonthlyCeiling: string;
  currency: string;
  totalSuggestedMonthly: string;
  unallocatedMonthly: string;
}

export interface RecommendationProposal {
  companyId: string;
  source: 'template' | 'model';
  providerName: string | null;
  modelName: string | null;
  roleCatalogVersion: number;
  employees: ProposedEmployee[];
  budget: BudgetSummary;
  warnings: string[];
}

export interface RecommendationOut {
  id: string;
  companyId: string;
  status: string;
  createdAt: string;
  preferences: Record<string, unknown>;
  proposal: RecommendationProposal;
}

export interface EmployeeAllocation {
  employeeId: string;
  budgetPerMonth: string;
  budgetPerTask: string;
}

export interface ContractGenerateRequest {
  allocations: EmployeeAllocation[];
  replaceExisting?: boolean;
}

export interface ContractSummaryOut {
  id: string;
  employeeId: string;
  versionNumber: number;
  status: string;
  role: string;
  roleConfigVersion: number;
  contentHash: string;
  supersedesId: string | null;
  activatedAt: string | null;
  createdAt: string;
}

export interface ContractOut {
  id: string;
  companyId: string;
  employeeId: string;
  versionNumber: number;
  status: string;
  role: string;
  roleConfigVersion: number;
  objective: string | null;
  responsibilities: string[];
  dataScope: Record<string, unknown>[];
  toolScope: Record<string, unknown>[];
  restrictions: string[];
  taskScope: string[];
  communicationPolicy: Record<string, unknown>;
  approvalRules: Record<string, unknown>[];
  budgetPerTask: string;
  budgetPerMonth: string;
  reportsToEmployeeId: string | null;
  requiresHumanEscalation: boolean;
  contentHash: string;
  source: string;
  supersedesId: string | null;
  effectiveAt: string | null;
  activatedAt: string | null;
  supersededAt: string | null;
  createdAt: string;
}

export interface ContractGenerationOut {
  companyId: string;
  contractIds: string[];
  employeeCount: number;
  replacedContractIds: string[];
  totalMonthlyAllocation: string;
  currency: string;
  warnings: string[];
}

export interface ActivationOut {
  companyId: string;
  status: string;
  revision: number;
  employeeCount: number;
  contractIds: string[];
  activatedAt: string;
  supersededContractIds: string[];
}

export interface BudgetSummaryOut {
  companyId: string;
  currency: string;
  accountId: string;
  periodStart: string;
  periodEnd: string;
  monthlyLimit: string;
  actualSpend: string;
  outstandingReservations: string;
  available: string;
  accountVersion: number;
  employeeAllocations: Array<{
    employeeId: string;
    displayName: string;
    roleKey: string;
    contractId: string;
    contractVersion: number;
    monthlyLimit: string;
    monthlySpend: string;
    monthlyOutstanding: string;
    monthlyAvailable: string;
    perTaskLimit: string;
    currency: string;
  }>;
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch(`${apiUrl}${path}`, {
    headers: {
      'Content-Type': 'application/json',
      ...options.headers,
    },
    ...options,
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return response.json();
}

export const onboardingApi = {
  async listTemplates(): Promise<TemplateOut[]> {
    return request<TemplateOut[]>('/api/setup/templates');
  },

  async listRoles(templateKey?: string): Promise<RoleOut[]> {
    const params = templateKey ? `?template_key=${encodeURIComponent(templateKey)}` : '';
    return request<RoleOut[]>(`/api/setup/roles${params}`);
  },

  async createCompany(payload: CompanyCreate): Promise<CompanyOut> {
    return request<CompanyOut>('/api/companies', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },

  async getCompany(id: string): Promise<CompanyOut> {
    return request<CompanyOut>(`/api/companies/${id}`);
  },

  async updateCompany(id: string, payload: CompanyUpdate): Promise<CompanyOut> {
    return request<CompanyOut>(`/api/companies/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(payload),
    });
  },

  async replaceWorkforce(companyId: string, payload: WorkforceReplace): Promise<WorkforceOut> {
    return request<WorkforceOut>(`/api/companies/${companyId}/workforce`, {
      method: 'PUT',
      body: JSON.stringify(payload),
    });
  },

  async getWorkforce(companyId: string): Promise<WorkforceOut> {
    return request<WorkforceOut>(`/api/companies/${companyId}/employees`);
  },

  async createRecommendation(payload: RecommendationRequest): Promise<RecommendationOut> {
    return request<RecommendationOut>('/api/setup/recommendations', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },

  async getRecommendation(id: string): Promise<RecommendationOut> {
    return request<RecommendationOut>(`/api/setup/recommendations/${id}`);
  },

  async generateContracts(companyId: string, payload: ContractGenerateRequest): Promise<ContractSummaryOut[]> {
    return request<ContractSummaryOut[]>(`/api/companies/${companyId}/contracts/generate`, {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },

  async listContracts(companyId: string): Promise<ContractSummaryOut[]> {
    return request<ContractSummaryOut[]>(`/api/companies/${companyId}/contracts`);
  },

  async getContract(id: string): Promise<ContractOut> {
    return request<ContractOut>(`/api/contracts/${id}`);
  },

  async activateCompany(companyId: string): Promise<ActivationOut> {
    return request<ActivationOut>(`/api/companies/${companyId}/activate`, {
      method: 'POST',
    });
  },

  async getBudget(companyId: string): Promise<BudgetSummaryOut> {
    return request<BudgetSummaryOut>(`/api/companies/${companyId}/budget`);
  },
};
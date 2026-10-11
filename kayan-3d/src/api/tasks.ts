import { apiUrl } from '../transport';

/**
 * Company task board API client.
 *
 * Thin fetch wrappers over the existing backend endpoints — no new API is
 * defined here. Task CRUD lives in `server/app/api/tasks.py` (+ the company
 * create/list routes in `companies.py`); budget and ledger reads live in
 * `server/app/api/budget.py`. Responses arrive camelCased (see
 * `server/app/schemas/common.py`).
 *
 * Paths carry the `/api` prefix the backend mounts its routers under (the same
 * convention as `experiments/backendExperiment.ts`).
 */

export interface CompanyTaskOut {
  id: string;
  companyId: string;
  employeeId: string;
  title: string;
  category: string;
  status: string;
  description: string | null;
  createdAt: string;
}

export interface CompanyTaskCreate {
  title: string;
  category: string;
  employeeId: string;
  description?: string;
}

export interface CompanyTaskUpdate {
  title?: string;
  category?: string;
  status?: string;
  description?: string;
}

export interface EmployeeBudgetAllocation {
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
}

export interface CompanyBudgetSummary {
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
  employeeAllocations: EmployeeBudgetAllocation[];
}

export interface LedgerEntryOut {
  id: string;
  companyId: string;
  accountId: string | null;
  reservationId: string | null;
  employeeId: string | null;
  taskId: string | null;
  runId: string | null;
  category: string;
  amount: string;
  currency: string;
  idempotencyKey: string;
  billableOperationId: string | null;
  note: string | null;
  createdAt: string;
}

export interface LedgerPageOut {
  companyId: string;
  entries: LedgerEntryOut[];
  limit: number;
  offset: number;
  returned: number;
  hasMore: boolean;
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

  return response.json() as Promise<T>;
}

export const tasksApi = {
  /** Every task belonging to the company, ordered by creation. */
  async listCompanyTasks(companyId: string): Promise<CompanyTaskOut[]> {
    return request<CompanyTaskOut[]>(`/api/companies/${companyId}/tasks`);
  },

  /** Create a task assigned to one of the company's employees (201). */
  async createCompanyTask(companyId: string, payload: CompanyTaskCreate): Promise<CompanyTaskOut> {
    return request<CompanyTaskOut>(`/api/companies/${companyId}/tasks`, {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },

  /** Partial update of a company task. A PATCH that changes nothing emits no event. */
  async updateCompanyTask(taskId: string, payload: CompanyTaskUpdate): Promise<CompanyTaskOut> {
    return request<CompanyTaskOut>(`/api/tasks/${taskId}`, {
      method: 'PATCH',
      body: JSON.stringify(payload),
    });
  },

  /** Company budget summary, including per-employee allocations. */
  async getBudget(companyId: string): Promise<CompanyBudgetSummary> {
    return request<CompanyBudgetSummary>(`/api/companies/${companyId}/budget`);
  },

  /** Ledger entries for one task, newest first. */
  async getTaskLedger(companyId: string, taskId: string): Promise<LedgerPageOut> {
    return request<LedgerPageOut>(
      `/api/companies/${companyId}/budget/ledger?task_id=${encodeURIComponent(taskId)}&limit=50`,
    );
  },
};

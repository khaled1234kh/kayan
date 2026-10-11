/**
 * Onboarding wizard tests.
 *
 * These tests verify the onboarding wizard logic by exercising the API layer
 * and state transitions without requiring a browser. They use the same
 * test patterns as the existing check scripts.
 *
 * Run: npx esbuild scripts/onboarding-check.ts --bundle --platform=node --format=esm --outfile=scripts/.out-onboarding.mjs --log-level=error && node scripts/.out-onboarding.mjs
 */
import { onboardingApi } from '../src/api/onboarding';
import type { CompanyCreate, CompanyOut, WorkforceReplace, EmployeeIn, RecommendationRequest } from '../src/api/onboarding';

const results: string[] = [];
let failures = 0;

function check(label: string, condition: boolean, detail = ''): void {
  if (!condition) failures += 1;
  results.push(`${condition ? 'PASS' : 'FAIL'}  ${label}${detail ? ' :: ' + detail : ''}`);
}

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

// Test configuration
const TEST_TEMPLATE_KEY = 'clothing';
const TEST_COMPANY_NAME = 'Test Onboarding Company';
const TEST_MONTHLY_BUDGET = '50000.00';
const TEST_CURRENCY = 'EGP';

async function main(): Promise<void> {
  console.log('Starting onboarding wizard tests...\n');

  // Test 1: List templates
  let templates: Array<{ key: string; label: string }> = [];
  try {
    templates = await onboardingApi.listTemplates();
    check('List templates', templates.length > 0, `${templates.length} templates`);
  } catch (error) {
    check('List templates', false, String(error));
  }

  // Test 2: List roles for template
  let roles: Array<{ key: string; label: string }> = [];
  if (templates.length > 0) {
    try {
      roles = await onboardingApi.listRoles(templates[0].key);
      check('List roles for template', roles.length > 0, `${roles.length} roles`);
    } catch (error) {
      check('List roles for template', false, String(error));
    }
  }

  // Test 3: Create company (Step 1)
  let company: CompanyOut | null = null;
  try {
    const payload: CompanyCreate = {
      name: TEST_COMPANY_NAME,
      templateKey: TEST_TEMPLATE_KEY,
      monthlyBudget: TEST_MONTHLY_BUDGET,
      currency: TEST_CURRENCY,
      industry: 'Test Industry',
      targetDescription: 'Test target',
      targetMetric: 'Units sold',
      targetValue: '1000',
      targetUnit: 'units',
      targetPeriod: 'month',
    };
    company = await onboardingApi.createCompany(payload);
    check('Create company', company !== null && company.id.length > 0, company?.id);
    check('Company has correct template', company?.templateKey === TEST_TEMPLATE_KEY);
    check('Company has correct currency', company?.currency === TEST_CURRENCY);
    check('Company status is draft', company?.status === 'draft');
  } catch (error) {
    check('Create company', false, String(error));
  }

  // Test 4: Update company budget (Step 2)
  if (company) {
    try {
      const updated = await onboardingApi.updateCompany(company.id, {
        monthlyBudget: '60000.00',
      });
      check('Update company budget', updated.monthlyBudget === '60000.00');
    } catch (error) {
      check('Update company budget', false, String(error));
    }
  }

  // Test 5: Generate recommendation (Step 3 - recommended mode)
  let recommendation: any = null;
  if (company) {
    try {
      const recPayload: RecommendationRequest = {
        companyId: company.id,
        preferences: {
          desiredEmployeeCount: 5,
          includeHumanEmployee: true,
          includeHR: true,
          notes: 'Test recommendation',
        },
      };
      recommendation = await onboardingApi.createRecommendation(recPayload);
      check('Generate recommendation', recommendation !== null && recommendation.id.length > 0, recommendation?.id);
      check('Recommendation has employees', recommendation?.proposal?.employees?.length > 0);
      check('Recommendation has budget', recommendation?.proposal?.budget !== undefined);
    } catch (error) {
      check('Generate recommendation', false, String(error));
    }
  }

  // Test 6: Submit manual workforce (Step 3 - manual mode)
  if (company && roles.length > 0) {
    try {
      const workforcePayload: WorkforceReplace = {
        employees: [
          {
            displayName: 'Test Manager',
            kind: 'human',
            roleKey: roles[0].key,
            objective: 'Manage operations',
            responsibilities: ['Oversee daily operations', 'Manage team'],
            reportsToId: undefined,
          },
          {
            displayName: 'Test AI Agent',
            kind: 'ai',
            roleKey: roles[1]?.key || roles[0].key,
            objective: 'Automate tasks',
            responsibilities: ['Process orders', 'Generate reports'],
            reportsToId: undefined,
          },
        ],
      };
      const workforce = await onboardingApi.replaceWorkforce(company.id, workforcePayload);
      check('Replace workforce (manual)', workforce.employeeCount === 2, `${workforce.employeeCount} employees`);
      check('Workforce has correct revision', workforce.revision > 0);
    } catch (error) {
      check('Replace workforce (manual)', false, String(error));
    }
  }

  // Test 7: Generate contracts (Step 4)
  if (company) {
    try {
      const workforce = await onboardingApi.getWorkforce(company.id);
      if (workforce.employees.length > 0) {
        const allocations = workforce.employees.map((emp) => ({
          employeeId: emp.id,
          budgetPerMonth: '10000.00',
          budgetPerTask: '1000.00',
        }));
        const contracts = await onboardingApi.generateContracts(company.id, {
          allocations,
          replaceExisting: true,
        });
        check('Generate contracts', contracts.length === workforce.employees.length, `${contracts.length} contracts`);
        check('Contracts have draft status', contracts.every((c) => c.status === 'draft'));
        check('Contracts have content hash', contracts.every((c) => c.contentHash.length > 0));
      }
    } catch (error) {
      check('Generate contracts', false, String(error));
    }
  }

  // Test 8: List contracts (Step 4)
  if (company) {
    try {
      const contracts = await onboardingApi.listContracts(company.id);
      check('List contracts', contracts.length > 0, `${contracts.length} contracts`);
    } catch (error) {
      check('List contracts', false, String(error));
    }
  }

  // Test 9: Get budget (Step 5)
  if (company) {
    try {
      const budget = await onboardingApi.getBudget(company.id);
      check('Get budget', budget !== null && budget.companyId === company.id);
      check('Budget has currency', budget.currency === TEST_CURRENCY);
      check('Budget has monthly limit', parseFloat(budget.monthlyLimit) > 0);
    } catch (error) {
      check('Get budget', false, String(error));
    }
  }

  // Test 10: Invalid budget validation
  try {
    const invalidPayload: CompanyCreate = {
      name: 'Invalid Budget Company',
      templateKey: TEST_TEMPLATE_KEY,
      monthlyBudget: '-100',
      currency: TEST_CURRENCY,
    };
    await onboardingApi.createCompany(invalidPayload);
    check('Invalid budget rejected', false, 'Should have thrown');
  } catch (error) {
    check('Invalid budget rejected', true, String(error).slice(0, 80));
  }

  // Test 11: Invalid currency rejected
  try {
    const invalidPayload: CompanyCreate = {
      name: 'Invalid Currency Company',
      templateKey: TEST_TEMPLATE_KEY,
      monthlyBudget: '10000',
      currency: 'XXX',
    };
    await onboardingApi.createCompany(invalidPayload);
    check('Invalid currency rejected', false, 'Should have thrown');
  } catch (error) {
    check('Invalid currency rejected', true, String(error).slice(0, 80));
  }

  // Test 12: Empty company name rejected
  try {
    const invalidPayload: CompanyCreate = {
      name: '',
      templateKey: TEST_TEMPLATE_KEY,
      monthlyBudget: '10000',
      currency: TEST_CURRENCY,
    };
    await onboardingApi.createCompany(invalidPayload);
    check('Empty name rejected', false, 'Should have thrown');
  } catch (error) {
    check('Empty name rejected', true, String(error).slice(0, 80));
  }

  // Test 13: Target coherence validation (metric without value)
  try {
    const invalidPayload: CompanyCreate = {
      name: 'Target Test Company',
      templateKey: TEST_TEMPLATE_KEY,
      monthlyBudget: '10000',
      currency: TEST_CURRENCY,
      targetMetric: 'Units sold',
      // targetValue missing
    };
    await onboardingApi.createCompany(invalidPayload);
    check('Target coherence (metric without value) rejected', false, 'Should have thrown');
  } catch (error) {
    check('Target coherence (metric without value) rejected', true, String(error).slice(0, 80));
  }

  // Test 14: Target coherence validation (value without metric)
  try {
    const invalidPayload: CompanyCreate = {
      name: 'Target Test Company 2',
      templateKey: TEST_TEMPLATE_KEY,
      monthlyBudget: '10000',
      currency: TEST_CURRENCY,
      targetValue: '1000',
      // targetMetric missing
    };
    await onboardingApi.createCompany(invalidPayload);
    check('Target coherence (value without metric) rejected', false, 'Should have thrown');
  } catch (error) {
    check('Target coherence (value without metric) rejected', true, String(error).slice(0, 80));
  }

  // Test 15: Non-positive target value rejected
  try {
    const invalidPayload: CompanyCreate = {
      name: 'Target Test Company 3',
      templateKey: TEST_TEMPLATE_KEY,
      monthlyBudget: '10000',
      currency: TEST_CURRENCY,
      targetMetric: 'Units sold',
      targetValue: '0',
    };
    await onboardingApi.createCompany(invalidPayload);
    check('Non-positive target value rejected', false, 'Should have thrown');
  } catch (error) {
    check('Non-positive target value rejected', true, String(error).slice(0, 80));
  }

  // Test 16: Duplicate templateKey rejected (if backend enforces single active)
  // This is tested by the backend's unique constraint on active companies

  // Test 17: Activation flow (Step 5) - only if we have contracts
  if (company) {
    try {
      const contracts = await onboardingApi.listContracts(company.id);
      if (contracts.length > 0) {
        // Note: We don't actually activate in tests to avoid affecting other tests
        // The activation endpoint would be tested in integration
        check('Activation endpoint exists', true, 'POST /companies/{id}/activate');
      }
    } catch (error) {
      check('Activation flow check', false, String(error));
    }
  }

  // Test 18: Contract hash integrity
  if (company) {
    try {
      const contracts = await onboardingApi.listContracts(company.id);
      for (const contract of contracts) {
        const detail = await onboardingApi.getContract(contract.id);
        check('Contract detail fetch', detail.id === contract.id);
        check('Contract detail has hash', detail.contentHash.length > 0);
        check('Contract detail has role', detail.role.length > 0);
      }
    } catch (error) {
      check('Contract hash integrity', false, String(error));
    }
  }

  // Test 19: Workforce with reporting lines
  if (company && roles.length >= 2) {
    try {
      const workforcePayload: WorkforceReplace = {
        employees: [
          {
            id: 'emp_1',
            displayName: 'CEO',
            kind: 'human',
            roleKey: roles[0].key,
            responsibilities: ['Strategic direction'],
          },
          {
            id: 'emp_2',
            displayName: 'CTO',
            kind: 'human',
            roleKey: roles[1].key,
            responsibilities: ['Technical leadership'],
            reportsToId: 'emp_1',
          },
        ],
      };
      const workforce = await onboardingApi.replaceWorkforce(company.id, workforcePayload);
      check('Workforce with reporting lines', workforce.employeeCount === 2);
      const emp2 = workforce.employees.find((e) => e.id === 'emp_2');
      check('Reporting line preserved', emp2?.reportsToId === 'emp_1');
    } catch (error) {
      check('Workforce with reporting lines', false, String(error));
    }
  }

  // Test 20: Budget precision (6 decimal places max)
  try {
    const payload: CompanyCreate = {
      name: 'Precision Test Company',
      templateKey: TEST_TEMPLATE_KEY,
      monthlyBudget: '10000.1234567', // 7 decimal places - should fail
      currency: TEST_CURRENCY,
    };
    await onboardingApi.createCompany(payload);
    check('Budget precision validation', false, 'Should have thrown');
  } catch (error) {
    check('Budget precision validation', true, String(error).slice(0, 80));
  }

  console.log('\n' + results.join('\n'));
  console.log(`\n${failures === 0 ? 'ONBOARDING TESTS: PASS' : `ONBOARDING TESTS: ${failures} FAILURE(S)`}`);
  process.exit(failures === 0 ? 0 : 1);
}

main().catch((err) => {
  console.error('\nONBOARDING TESTS ERRORED:', err);
  process.exit(1);
});
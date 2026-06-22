/**
 * The ONE place the app talks to the backend.
 *
 * Cross-cutting rule (from the build brief): never scatter raw fetch/axios calls
 * across pages. Every component goes through the `api` facade below, which wraps
 * the auto-generated client in src/lib/api. That keeps two things in exactly one
 * spot:
 *   1. the base URL  (set once on the generated client's global OpenAPI config), and
 *   2. the future auth wiring — when PF-39 ships cookies, `WITH_CREDENTIALS = true`
 *      and a 401 -> /login redirect get added HERE and every call inherits them.
 *
 * Java analogy: this is the single configured `RestTemplate`/`WebClient` bean the
 * whole app autowires, rather than `new`-ing an HTTP client in every controller.
 */
import { OpenAPI } from "./api/core/OpenAPI";
import { ApiError } from "./api/core/ApiError";

import { AccountsService } from "./api/services/AccountsService";
import { AiService } from "./api/services/AiService";
import { AnalyticsService } from "./api/services/AnalyticsService";
import { CategoriesService } from "./api/services/CategoriesService";
import { CategorizeService } from "./api/services/CategorizeService";
import { DashboardService } from "./api/services/DashboardService";
import { HealthService } from "./api/services/HealthService";
import { HoldingsService } from "./api/services/HoldingsService";
import { ImportsService } from "./api/services/ImportsService";
import { InstrumentsService } from "./api/services/InstrumentsService";
import { InvestmentTxnsService } from "./api/services/InvestmentTxnsService";
import { LedgerService } from "./api/services/LedgerService";
import { TransactionsService } from "./api/services/TransactionsService";

// Point the generated client at the backend. import.meta.env is Vite's compile-
// time env (see .env -> VITE_API_URL). Runs once when this module is first
// imported, which is before any API call because every call comes through here.
OpenAPI.BASE = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

// --- Future auth hook (PF-39) ----------------------------------------------
// When cookie auth lands, uncomment to send the httpOnly session cookie on every
// request, and add a global 401 -> /login redirect in the catch sites / a fetch
// interceptor. Left here as the documented single integration point.
// OpenAPI.WITH_CREDENTIALS = true;
// OpenAPI.CREDENTIALS = "include";

/**
 * Friendly facade over the generated services. The generated method names embed
 * the HTTP verb + path (e.g. `listTransactionsApiTransactionsGet`) which is noisy
 * at call sites; this maps them to readable names like `api.transactions.list`.
 * Re-generating the client (npm run gen:api) only requires updating this file if
 * an endpoint's signature actually changed.
 */
export const api = {
  health: HealthService.healthHealthGet,

  accounts: {
    list: AccountsService.listAccountsApiAccountsGet,
    create: AccountsService.createAccountApiAccountsPost,
    update: AccountsService.updateAccountApiAccountsAccountIdPatch,
    remove: AccountsService.deleteAccountApiAccountsAccountIdDelete,
  },

  categories: {
    list: CategoriesService.listCategoriesApiCategoriesGet,
    create: CategoriesService.createCategoryApiCategoriesPost,
    update: CategoriesService.updateCategoryApiCategoriesCategoryIdPatch,
    remove: CategoriesService.deleteCategoryApiCategoriesCategoryIdDelete,
  },

  transactions: {
    list: TransactionsService.listTransactionsApiTransactionsGet,
    create: TransactionsService.createTransactionApiTransactionsPost,
    update: TransactionsService.updateTransactionApiTransactionsTxnIdPatch,
    remove: TransactionsService.deleteTransactionApiTransactionsTxnIdDelete,
  },

  instruments: {
    list: InstrumentsService.listInstrumentsApiInstrumentsGet,
    create: InstrumentsService.createInstrumentApiInstrumentsPost,
    update: InstrumentsService.updateInstrumentApiInstrumentsInstrumentIdPatch,
  },

  investmentTxns: {
    list: InvestmentTxnsService.listInvestmentTxnsApiInvestmentTxnsGet,
    create: InvestmentTxnsService.createInvestmentTxnApiInvestmentTxnsPost,
    update: InvestmentTxnsService.updateInvestmentTxnApiInvestmentTxnsTxnIdPatch,
    remove: InvestmentTxnsService.deleteInvestmentTxnApiInvestmentTxnsTxnIdDelete,
  },

  holdings: {
    list: HoldingsService.getHoldingsApiHoldingsGet,
  },

  dashboard: {
    get: DashboardService.getDashboardApiDashboardGet,
  },

  ledger: {
    list: LedgerService.listLedgerApiLedgerGet,
  },

  analytics: {
    monthly: AnalyticsService.monthlyCashflowSummaryApiAnalyticsMonthlyGet,
  },

  imports: {
    preview: ImportsService.previewImportApiImportsTransactionsPreviewPost,
    confirm: ImportsService.confirmImportApiImportsTransactionsConfirmPost,
  },

  categorize: {
    suggest: CategorizeService.suggestApiCategorizeSuggestPost,
    suggestBatch: CategorizeService.suggestBatchApiCategorizeSuggestBatchPost,
    accept: CategorizeService.acceptApiCategorizeAcceptPost,
    listRules: CategorizeService.listRulesApiCategorizeRulesGet,
    deleteRule: CategorizeService.deleteRuleApiCategorizeRulesRuleIdDelete,
  },

  ai: {
    usage: AiService.getUsageApiAiUsageGet,
  },
};

/**
 * Normalizes any thrown error into the backend's `{ detail, code }` shape so
 * toasts and form errors have a consistent message to show. The backend wraps
 * every HTTPException (and validation error) in `{ detail, code }`; this just
 * digs that out of the generated client's ApiError, with sensible fallbacks.
 */
export type ApiErrorInfo = { detail: string; code: string; status?: number };

export function getApiError(err: unknown): ApiErrorInfo {
  if (err instanceof ApiError) {
    const body = err.body as { detail?: unknown; code?: unknown } | undefined;
    const rawDetail = body?.detail;

    // Normal case: backend sends `detail` as a human string.
    let detail: string;
    if (typeof rawDetail === "string") {
      detail = rawDetail;
    } else if (Array.isArray(rawDetail)) {
      // FastAPI validation arrays: [{ loc, msg, type }, ...] -> join the messages.
      detail = rawDetail
        .map((d: any) => d?.msg ?? JSON.stringify(d))
        .join("; ");
    } else {
      detail = err.statusText || "Request failed";
    }

    const code = typeof body?.code === "string" ? body.code : `http_${err.status}`;
    return { detail, code, status: err.status };
  }

  if (err instanceof Error) return { detail: err.message, code: "unknown" };
  return { detail: "Something went wrong", code: "unknown" };
}

import { useQuery } from "@tanstack/react-query";

import { api } from "@/lib/http";

/**
 * Shared query for the (non-archived) account list. Many places need it — the
 * global account filter, the transaction form, the trade form — so it lives in
 * one hook. TanStack Query dedupes: mounting this in three components still makes
 * a single network request and shares the cached result under the ['accounts'] key.
 */
export function useAccounts() {
  return useQuery({
    queryKey: ["accounts"],
    // The generated client takes a named-options object; {} = default filters
    // (archived accounts are excluded by the backend default).
    queryFn: () => api.accounts.list({}),
    staleTime: 5 * 60_000, // accounts change rarely; cache for 5 minutes
  });
}

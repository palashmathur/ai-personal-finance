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

/**
 * Returns a function that maps an account id to its display name. Handy in tables
 * (holdings, trades) where rows carry account_id but we want to show the name.
 */
export function useAccountNameLookup() {
  const { data } = useAccounts();
  return (id: number) => data?.find((a) => a.id === id)?.name ?? `#${id}`;
}

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
 * Same accounts, but INCLUDING archived ones — for the Accounts management page,
 * which needs to show (and restore) archived accounts too. `archived: true` tells
 * the backend to return everything, not just the archived rows. Separate query key
 * (['accounts','all']) so it doesn't clobber the filter/forms list, but account
 * mutations invalidate the ['accounts'] prefix which covers both.
 */
export function useAllAccounts() {
  return useQuery({
    queryKey: ["accounts", "all"],
    queryFn: () => api.accounts.list({ archived: true }),
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

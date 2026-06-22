import { useQuery } from "@tanstack/react-query";

import { api } from "@/lib/http";
import { useFiltersStore } from "@/store/filters";

// Holdings are an as-of-now snapshot (current positions), so only the account
// filter applies — not the date range. One account selected => filter to it.
export function useHoldings() {
  const accountIds = useFiltersStore((s) => s.accountIds);
  const accountId = accountIds.length === 1 ? accountIds[0] : undefined;

  return useQuery({
    queryKey: ["holdings", { accountId }],
    queryFn: () => api.holdings.list({ accountId }),
  });
}

// The raw trade ledger. Trades have a date, so the global date range applies here.
export function useTrades() {
  const from = useFiltersStore((s) => s.from);
  const to = useFiltersStore((s) => s.to);
  const accountIds = useFiltersStore((s) => s.accountIds);
  const accountId = accountIds.length === 1 ? accountIds[0] : undefined;

  return useQuery({
    queryKey: ["investment-txns", { from, to, accountId }],
    queryFn: () => api.investmentTxns.list({ from, to, accountId }),
  });
}

// Instrument typeahead. Disabled until the user types so we don't fetch the whole
// catalog on an empty box. keyed by the search term so each keystroke caches.
export function useInstrumentSearch(term: string) {
  return useQuery({
    queryKey: ["instruments", term],
    queryFn: () => api.instruments.list({ search: term }),
    enabled: term.trim().length > 0,
    staleTime: 60_000,
  });
}

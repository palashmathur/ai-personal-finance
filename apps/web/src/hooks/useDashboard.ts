import { useQuery } from "@tanstack/react-query";

import { api } from "@/lib/http";
import { useFiltersStore } from "@/store/filters";

/**
 * Fetches the whole dashboard payload for the active date range. The range is in
 * the query key, so moving the global filter refetches; and because transaction
 * and investment mutations invalidate ['dashboard'], the charts also refresh
 * whenever the underlying data changes — that's the "live dashboard" behaviour.
 */
export function useDashboard() {
  const from = useFiltersStore((s) => s.from);
  const to = useFiltersStore((s) => s.to);

  return useQuery({
    queryKey: ["dashboard", { from, to }],
    queryFn: () => api.dashboard.get({ from, to }),
  });
}

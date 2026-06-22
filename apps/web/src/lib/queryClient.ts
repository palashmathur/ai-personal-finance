import { QueryClient } from "@tanstack/react-query";

/**
 * The single TanStack Query client for the app.
 *
 * TanStack Query for a Spring dev: it's a client-side cache + fetch orchestrator
 * for server data. A `useQuery(key, fn)` is like a cached repository read keyed by
 * `key`; a `useMutation` is a write that can then *invalidate* keys so dependent
 * reads refetch. This is what makes "add a transaction -> dashboard updates" cheap:
 * the mutation invalidates ['dashboard'] and the chart refetches itself.
 */
export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      // Treat data as fresh for 30s before a background refetch is considered.
      staleTime: 30_000,
      // A single-user local app doesn't need aggressive refocus refetching.
      refetchOnWindowFocus: false,
      retry: 1,
    },
  },
});

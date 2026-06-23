import { create } from "zustand";

import { rangeForPreset, type DatePreset } from "@/lib/dateRange";

/**
 * Global filter store (Zustand).
 *
 * Zustand for a Java/Spring dev: think of it as one small application-scoped
 * singleton holding mutable state, where components "subscribe" to just the
 * fields they read and re-render only when those change. There's no
 * action/reducer ceremony like Redux — you declare the state and its updater
 * methods together in a single create() call, and call them directly.
 *
 * Why global (not server) state: the date range and account filter are pure UI
 * intent shared by every page. They get folded into each page's TanStack Query
 * key, so changing a filter automatically refetches the dashboard, transactions,
 * holdings, etc. (server state stays in TanStack Query; only the *filter inputs*
 * live here).
 */
interface FiltersState {
  preset: DatePreset;
  from: string; // YYYY-MM-DD
  to: string; // YYYY-MM-DD
  accountIds: number[]; // empty = all accounts

  // Pick a preset; for everything except "custom" this recomputes from/to.
  setPreset: (preset: DatePreset) => void;
  // Manually set both ends (used by the custom-range date inputs).
  setCustomRange: (from: string, to: string) => void;
  // Toggle one account in/out of the filter (multi-select).
  toggleAccount: (id: number) => void;
  clearAccounts: () => void;
}

// Default view on first load: the current month.
const initial = rangeForPreset("this_month");

export const useFiltersStore = create<FiltersState>((set) => ({
  preset: "this_month",
  from: initial.from,
  to: initial.to,
  accountIds: [],

  setPreset: (preset) =>
    set(() => {
      // "custom" keeps whatever from/to is already there; the user edits the
      // dates directly via setCustomRange.
      if (preset === "custom") return { preset };
      const r = rangeForPreset(preset);
      return { preset, from: r.from, to: r.to };
    }),

  setCustomRange: (from, to) => set({ preset: "custom", from, to }),

  toggleAccount: (id) =>
    set((s) => ({
      accountIds: s.accountIds.includes(id)
        ? s.accountIds.filter((x) => x !== id)
        : [...s.accountIds, id],
    })),

  clearAccounts: () => set({ accountIds: [] }),
}));

/**
 * Convenience selector returning a stable query-key fragment for the date range.
 * Pages spread this into their queryKey: ['dashboard', useDateRangeKey()] so a
 * filter change produces a new key and TanStack Query refetches.
 */
export function useDateRangeKey() {
  const from = useFiltersStore((s) => s.from);
  const to = useFiltersStore((s) => s.to);
  return { from, to };
}

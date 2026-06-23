import { useQuery } from "@tanstack/react-query";

import { api } from "@/lib/http";
import type { CategoryResponse } from "@/lib/api";

/** A flat, selectable category option with a display label like "Food › Dining Out". */
export type CategoryOption = {
  id: number;
  label: string;
  kind: "income" | "expense";
};

/**
 * Fetches the nested category tree (parents with embedded children). Shared, so
 * the form's category picker and the table's category lookups hit one cache.
 */
export function useCategories() {
  return useQuery({
    queryKey: ["categories"],
    queryFn: () => api.categories.list({}),
    staleTime: 5 * 60_000,
  });
}

/**
 * Flattens the tree into selectable options for a given kind. The backend requires
 * a transaction's category to match its kind (income vs expense), so the form only
 * offers the right ones. Both parents ("Food") and leaves ("Food › Dining Out")
 * are selectable — the backend accepts either.
 */
export function flattenCategoryOptions(
  tree: CategoryResponse[] | undefined,
  kind: "income" | "expense"
): CategoryOption[] {
  if (!tree) return [];
  const out: CategoryOption[] = [];
  for (const parent of tree) {
    if (parent.kind !== kind || parent.archived) continue;
    out.push({ id: parent.id, label: parent.name, kind });
    for (const child of parent.children ?? []) {
      if (child.archived) continue;
      out.push({ id: child.id, label: `${parent.name} › ${child.name}`, kind });
    }
  }
  return out;
}

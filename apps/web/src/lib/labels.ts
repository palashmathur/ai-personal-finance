// Turn machine enum strings into human labels, e.g. "mutual_fund" -> "Mutual Fund".
// Used for instrument kinds in the allocation donut and the investments page.
export function titleCase(value: string): string {
  return value
    .split("_")
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(" ");
}

// A small, theme-agnostic palette for charts (donut slices, etc). Picked to be
// readable in both light and dark mode.
export const CHART_COLORS = [
  "#3b82f6", // blue
  "#10b981", // emerald
  "#f59e0b", // amber
  "#8b5cf6", // violet
  "#ef4444", // red
  "#14b8a6", // teal
  "#ec4899", // pink
  "#64748b", // slate
];

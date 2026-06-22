/**
 * Date-range presets for the global filter (PF-F3). Every preset resolves to a
 * concrete { from, to } pair of ISO `YYYY-MM-DD` strings, which is exactly what
 * the backend's `?from=&to=` query params expect.
 */

export type DatePreset = "this_month" | "last_3m" | "fy" | "ytd" | "custom";

// Human labels for the filter buttons. Order here is the order shown in the UI.
export const PRESET_LABELS: Record<DatePreset, string> = {
  this_month: "This Month",
  last_3m: "Last 3M",
  fy: "FY (Apr–Mar)",
  ytd: "YTD",
  custom: "Custom",
};

// Indian financial year starts in April. Hard-coded for now.
// TODO(PF-29 + PF-F11): read fy_start_month from GET /api/settings once that
// endpoint/page exists, instead of assuming April.
const FY_START_MONTH = 4;

// Format a Date as a local-time YYYY-MM-DD. We deliberately avoid toISOString()
// because that converts to UTC and can shift the date across midnight.
function iso(d: Date): string {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

function firstOfMonth(year: number, monthIndex0: number): Date {
  return new Date(year, monthIndex0, 1);
}

function lastOfMonth(year: number, monthIndex0: number): Date {
  // Day 0 of the next month is the last day of this month.
  return new Date(year, monthIndex0 + 1, 0);
}

export interface DateRange {
  from: string;
  to: string;
}

/**
 * Resolve a preset to a concrete date range. `today` is injectable so this stays
 * a pure function (easy to reason about / test). `custom` has no canonical range,
 * so it falls back to the current month; the store keeps the user's chosen dates.
 */
export function rangeForPreset(preset: DatePreset, today = new Date()): DateRange {
  const y = today.getFullYear();
  const m = today.getMonth(); // 0-based

  switch (preset) {
    case "this_month":
      return { from: iso(firstOfMonth(y, m)), to: iso(lastOfMonth(y, m)) };

    case "last_3m":
      // Rolling 3 calendar months ending with the current month.
      return { from: iso(firstOfMonth(y, m - 2)), to: iso(lastOfMonth(y, m)) };

    case "fy": {
      // If we're in/after the FY start month, the FY began this calendar year;
      // otherwise it began last year. FY end is the day before next FY start.
      const fyStartYear = m + 1 >= FY_START_MONTH ? y : y - 1;
      const from = new Date(fyStartYear, FY_START_MONTH - 1, 1);
      const to = new Date(fyStartYear + 1, FY_START_MONTH - 1, 0);
      return { from: iso(from), to: iso(to) };
    }

    case "ytd":
      // Jan 1 of the current calendar year through today.
      return { from: iso(new Date(y, 0, 1)), to: iso(today) };

    case "custom":
    default:
      return { from: iso(firstOfMonth(y, m)), to: iso(lastOfMonth(y, m)) };
  }
}

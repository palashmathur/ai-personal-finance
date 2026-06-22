import { ChevronDown } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuCheckboxItem,
  DropdownMenuContent,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { ModeToggle } from "@/components/theme/ModeToggle";
import { useAccounts } from "@/hooks/useAccounts";
import { useFiltersStore } from "@/store/filters";
import { PRESET_LABELS, type DatePreset } from "@/lib/dateRange";
import { cn } from "@/lib/utils";

const PRESET_ORDER: DatePreset[] = [
  "this_month",
  "last_3m",
  "fy",
  "ytd",
  "custom",
];

/**
 * The global filter bar that sits above every page. Two controls:
 *  - date-range presets (drives every chart/table via TanStack Query keys), and
 *  - an account multi-select.
 * Reading individual fields with separate selectors (one useFiltersStore call per
 * field) means a component only re-renders when the field it reads changes.
 */
export function GlobalFilters() {
  const preset = useFiltersStore((s) => s.preset);
  const from = useFiltersStore((s) => s.from);
  const to = useFiltersStore((s) => s.to);
  const accountIds = useFiltersStore((s) => s.accountIds);
  const setPreset = useFiltersStore((s) => s.setPreset);
  const setCustomRange = useFiltersStore((s) => s.setCustomRange);
  const toggleAccount = useFiltersStore((s) => s.toggleAccount);
  const clearAccounts = useFiltersStore((s) => s.clearAccounts);

  const { data: accounts } = useAccounts();

  const accountLabel =
    accountIds.length === 0
      ? "All accounts"
      : accountIds.length === 1
        ? (accounts?.find((a) => a.id === accountIds[0])?.name ?? "1 account")
        : `${accountIds.length} accounts`;

  return (
    <div className="flex flex-wrap items-center gap-2 border-b bg-background px-4 py-3 md:px-6">
      {/* Date-range presets as a button group. */}
      <div className="flex flex-wrap items-center gap-1">
        {PRESET_ORDER.map((p) => (
          <Button
            key={p}
            size="sm"
            variant={preset === p ? "default" : "outline"}
            onClick={() => setPreset(p)}
          >
            {PRESET_LABELS[p]}
          </Button>
        ))}
      </div>

      {/* Custom range shows two native date inputs. They're already YYYY-MM-DD,
          which is exactly what the backend wants — no parsing needed. */}
      {preset === "custom" && (
        <div className="flex items-center gap-2">
          <input
            type="date"
            value={from}
            max={to}
            onChange={(e) => setCustomRange(e.target.value, to)}
            className="h-9 rounded-md border bg-background px-2 text-sm"
          />
          <span className="text-muted-foreground">→</span>
          <input
            type="date"
            value={to}
            min={from}
            onChange={(e) => setCustomRange(from, e.target.value)}
            className="h-9 rounded-md border bg-background px-2 text-sm"
          />
        </div>
      )}

      {/* Account multi-select. */}
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button variant="outline" size="sm" className="gap-1">
            {accountLabel}
            <ChevronDown className="h-3.5 w-3.5 opacity-60" />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="start" className="max-h-72 overflow-auto">
          <DropdownMenuLabel>Filter by account</DropdownMenuLabel>
          <DropdownMenuSeparator />
          {(accounts ?? []).map((a) => (
            <DropdownMenuCheckboxItem
              key={a.id}
              checked={accountIds.includes(a.id)}
              // Radix closes the menu on select by default; preventDefault keeps
              // it open so you can tick several accounts in one go.
              onSelect={(e) => {
                e.preventDefault();
                toggleAccount(a.id);
              }}
            >
              {a.name}
            </DropdownMenuCheckboxItem>
          ))}
          {accountIds.length > 0 && (
            <>
              <DropdownMenuSeparator />
              <button
                className="w-full px-2 py-1.5 text-left text-sm text-muted-foreground hover:text-foreground"
                onClick={() => clearAccounts()}
              >
                Clear selection
              </button>
            </>
          )}
        </DropdownMenuContent>
      </DropdownMenu>

      {/* Right-aligned: current resolved range + theme toggle. */}
      <div className="ml-auto flex items-center gap-3">
        <span
          className={cn(
            "hidden text-xs text-muted-foreground sm:inline",
            "tabular-nums"
          )}
        >
          {from} → {to}
        </span>
        <ModeToggle />
      </div>
    </div>
  );
}

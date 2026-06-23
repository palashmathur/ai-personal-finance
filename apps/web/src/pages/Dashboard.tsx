import { Loader2 } from "lucide-react";

import { useDashboard } from "@/hooks/useDashboard";
import { CashflowCards } from "@/components/charts/CashflowCards";
import { CategoryBar } from "@/components/charts/CategoryBar";
import { AllocationDonut } from "@/components/charts/AllocationDonut";
import { NetWorthLine } from "@/components/charts/NetWorthLine";

export function Dashboard() {
  const { data, isLoading, isError } = useDashboard();

  if (isLoading) {
    return (
      <div className="flex items-center justify-center gap-2 py-24 text-muted-foreground">
        <Loader2 className="h-4 w-4 animate-spin" /> Loading dashboard…
      </div>
    );
  }

  if (isError || !data) {
    return (
      <div className="py-24 text-center text-sm text-muted-foreground">
        Couldn't load the dashboard. Is the backend running?
      </div>
    );
  }

  // Current net worth = the most recent month-end snapshot (last series point).
  const netWorthMinor =
    data.networth_series.length > 0
      ? data.networth_series[data.networth_series.length - 1].networth_minor
      : null;

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Dashboard</h1>
        <p className="text-sm text-muted-foreground">
          Cashflow, spending, allocation, and net worth for the selected range.
        </p>
      </div>

      <CashflowCards cashflow={data.cashflow} />

      <div className="grid gap-4 lg:grid-cols-2">
        <NetWorthLine data={data.networth_series} />
        <AllocationDonut
          data={data.allocation}
          netWorthMinor={netWorthMinor}
        />
        <CategoryBar data={data.by_category} />
      </div>
    </div>
  );
}

import { ArrowDownRight, ArrowUpRight, PiggyBank } from "lucide-react";

import { Card, CardContent } from "@/components/ui/card";
import { formatMoney } from "@/lib/money";
import type { CashflowBlock } from "@/lib/api";

// The three headline numbers for the period: income, expenses, savings rate.
// savings_rate is null when income is 0 (no division by zero) — show an em dash.
export function CashflowCards({ cashflow }: { cashflow: CashflowBlock }) {
  const savings =
    cashflow.savings_rate == null
      ? "—"
      : `${(cashflow.savings_rate * 100).toFixed(1)}%`;

  return (
    <div className="grid gap-4 sm:grid-cols-3">
      <StatCard
        label="Income"
        value={formatMoney(cashflow.income_minor)}
        icon={<ArrowUpRight className="h-4 w-4 text-emerald-500" />}
      />
      <StatCard
        label="Expenses"
        value={formatMoney(cashflow.expense_minor)}
        icon={<ArrowDownRight className="h-4 w-4 text-red-500" />}
      />
      <StatCard
        label="Savings rate"
        value={savings}
        icon={<PiggyBank className="h-4 w-4 text-primary" />}
      />
    </div>
  );
}

function StatCard({
  label,
  value,
  icon,
}: {
  label: string;
  value: string;
  icon: React.ReactNode;
}) {
  return (
    <Card>
      <CardContent className="flex items-center justify-between p-5">
        <div>
          <p className="text-sm text-muted-foreground">{label}</p>
          <p className="mt-1 text-2xl font-semibold tabular-nums">{value}</p>
        </div>
        <div className="rounded-full bg-muted p-2">{icon}</div>
      </CardContent>
    </Card>
  );
}

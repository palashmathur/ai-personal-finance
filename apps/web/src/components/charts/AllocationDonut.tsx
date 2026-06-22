import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";

import { ChartCard } from "@/components/charts/ChartCard";
import { formatMoney, formatMoneyCompact } from "@/lib/money";
import { CHART_COLORS, titleCase } from "@/lib/labels";
import type { AllocationItem } from "@/lib/api";

// Asset-allocation donut grouped by instrument kind. The center shows current net
// worth (passed in from the last net-worth-series point), per the AC. The donut
// itself only covers investment holdings; net worth in the middle includes cash.
export function AllocationDonut({
  data,
  netWorthMinor,
}: {
  data: AllocationItem[];
  netWorthMinor: number | null;
}) {
  return (
    <ChartCard
      title="Asset allocation"
      isEmpty={data.length === 0}
      emptyHint="No holdings yet — add a trade on the Investments page."
    >
      <div className="flex h-full flex-col">
      <div className="relative min-h-0 flex-1">
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie
              data={data}
              dataKey="market_value_minor"
              nameKey="kind"
              innerRadius="60%"
              outerRadius="85%"
              paddingAngle={2}
              stroke="none"
            >
              {data.map((_, i) => (
                <Cell key={i} fill={CHART_COLORS[i % CHART_COLORS.length]} />
              ))}
            </Pie>
            <Tooltip
              contentStyle={{
                background: "hsl(var(--popover))",
                border: "1px solid hsl(var(--border))",
                borderRadius: 8,
                color: "hsl(var(--popover-foreground))",
              }}
              formatter={(v, name) => [
                formatMoney(v as number),
                titleCase(String(name)),
              ]}
            />
          </PieChart>
        </ResponsiveContainer>

        {/* Center label — absolutely positioned over the donut hole. */}
        <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
          <span className="text-xs text-muted-foreground">Net worth</span>
          <span className="text-xl font-semibold tabular-nums">
            {netWorthMinor == null ? "—" : formatMoneyCompact(netWorthMinor)}
          </span>
        </div>
      </div>

      {/* Legend with kind + percentage, below the donut. */}
      <div className="mt-2 flex flex-wrap justify-center gap-x-4 gap-y-1 text-xs">
        {data.map((d, i) => (
          <span key={d.kind} className="flex items-center gap-1.5">
            <span
              className="inline-block h-2.5 w-2.5 rounded-full"
              style={{ background: CHART_COLORS[i % CHART_COLORS.length] }}
            />
            {titleCase(d.kind)} · {(d.pct * 100).toFixed(0)}%
          </span>
        ))}
      </div>
      </div>
    </ChartCard>
  );
}

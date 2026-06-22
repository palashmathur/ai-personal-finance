import {
  Bar,
  BarChart,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { ChartCard } from "@/components/charts/ChartCard";
import { formatMoney, formatMoneyCompact } from "@/lib/money";
import { CHART_COLORS } from "@/lib/labels";
import type { CategoryBreakdownItem } from "@/lib/api";

// Horizontal bar of the top-10 expense categories for the period. Horizontal
// (layout="vertical" in Recharts terms) so long category names stay readable.
export function CategoryBar({ data }: { data: CategoryBreakdownItem[] }) {
  const top = [...data]
    .sort((a, b) => b.total_minor - a.total_minor)
    .slice(0, 10);

  return (
    <ChartCard
      title="Top expense categories"
      isEmpty={top.length === 0}
      emptyHint="No categorised expenses in this range."
    >
      <ResponsiveContainer width="100%" height="100%">
        <BarChart
          data={top}
          layout="vertical"
          margin={{ left: 8, right: 16, top: 4, bottom: 4 }}
        >
          <XAxis
            type="number"
            tickFormatter={(v) => formatMoneyCompact(v as number)}
            tick={{ fill: "hsl(var(--muted-foreground))", fontSize: 12 }}
            axisLine={false}
            tickLine={false}
          />
          <YAxis
            type="category"
            dataKey="category_name"
            width={110}
            tick={{ fill: "hsl(var(--muted-foreground))", fontSize: 12 }}
            axisLine={false}
            tickLine={false}
          />
          <Tooltip
            cursor={{ fill: "hsl(var(--muted))" }}
            contentStyle={{
              background: "hsl(var(--popover))",
              border: "1px solid hsl(var(--border))",
              borderRadius: 8,
              color: "hsl(var(--popover-foreground))",
            }}
            formatter={(v) => [formatMoney(v as number), "Spent"]}
          />
          <Bar dataKey="total_minor" radius={[0, 4, 4, 0]}>
            {top.map((_, i) => (
              <Cell key={i} fill={CHART_COLORS[i % CHART_COLORS.length]} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </ChartCard>
  );
}

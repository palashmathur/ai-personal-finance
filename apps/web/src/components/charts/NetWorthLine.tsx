import {
  Area,
  AreaChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { ChartCard } from "@/components/charts/ChartCard";
import { formatMoney, formatMoneyCompact } from "@/lib/money";
import type { NetWorthPoint } from "@/lib/api";

// Net-worth-over-time area line. Monthly month-end snapshots from the backend.
// Note (PF-F27 backend): until a price-history table exists, every past month is
// valued at the instrument's CURRENT price — so the line reflects cashflow drift
// more than true historical valuation. Good enough for V1; gets more accurate later.
export function NetWorthLine({ data }: { data: NetWorthPoint[] }) {
  return (
    <ChartCard
      title="Net worth"
      isEmpty={data.length === 0}
      emptyHint="No data yet."
    >
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={data} margin={{ left: 8, right: 16, top: 8, bottom: 4 }}>
          <defs>
            <linearGradient id="nw" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.35} />
              <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
            </linearGradient>
          </defs>
          <XAxis
            dataKey="month"
            tick={{ fill: "hsl(var(--muted-foreground))", fontSize: 12 }}
            axisLine={false}
            tickLine={false}
          />
          <YAxis
            tickFormatter={(v) => formatMoneyCompact(v as number)}
            tick={{ fill: "hsl(var(--muted-foreground))", fontSize: 12 }}
            axisLine={false}
            tickLine={false}
            width={64}
          />
          <Tooltip
            contentStyle={{
              background: "hsl(var(--popover))",
              border: "1px solid hsl(var(--border))",
              borderRadius: 8,
              color: "hsl(var(--popover-foreground))",
            }}
            formatter={(v) => [formatMoney(v as number), "Net worth"]}
          />
          <Area
            type="monotone"
            dataKey="networth_minor"
            stroke="#3b82f6"
            strokeWidth={2}
            fill="url(#nw)"
          />
        </AreaChart>
      </ResponsiveContainer>
    </ChartCard>
  );
}

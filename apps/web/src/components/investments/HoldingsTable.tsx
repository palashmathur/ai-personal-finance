import { RefreshCw } from "lucide-react";

import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { formatMoney } from "@/lib/money";
import { titleCase } from "@/lib/labels";
import { useAccountNameLookup } from "@/hooks/useAccounts";
import type { HoldingResponse, HoldingInstrument } from "@/lib/api";

// Holdings = one row per (account, instrument) open position. We OMIT the XIRR
// column on purpose — its backend (PF-28) isn't built yet (per the build brief).
export function HoldingsTable({
  rows,
  onUpdatePrice,
}: {
  rows: HoldingResponse[];
  onUpdatePrice: (instrument: HoldingInstrument) => void;
}) {
  const accountName = useAccountNameLookup();

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Instrument</TableHead>
          <TableHead>Account</TableHead>
          <TableHead className="text-right">Qty</TableHead>
          <TableHead className="text-right">Avg cost</TableHead>
          <TableHead className="text-right">Price</TableHead>
          <TableHead className="text-right">Market value</TableHead>
          <TableHead className="text-right">P&amp;L</TableHead>
          <TableHead className="w-[60px]" />
        </TableRow>
      </TableHeader>
      <TableBody>
        {rows.map((h) => {
          // Avg cost per unit = total cost basis / quantity (paise).
          const avgCost = h.qty > 0 ? h.cost_basis_minor / h.qty : 0;
          const pnl = h.unrealized_pnl_minor;
          const pnlPct =
            pnl != null && h.cost_basis_minor > 0
              ? (pnl / h.cost_basis_minor) * 100
              : null;
          const pnlColor =
            pnl == null
              ? "text-muted-foreground"
              : pnl >= 0
                ? "text-emerald-600 dark:text-emerald-400"
                : "text-red-600 dark:text-red-400";

          return (
            <TableRow key={`${h.account_id}-${h.instrument_id}`}>
              <TableCell>
                <div className="font-medium">{h.instrument.name}</div>
                <div className="text-xs text-muted-foreground">
                  {h.instrument.symbol} · {titleCase(h.instrument.kind)}
                </div>
              </TableCell>
              <TableCell>{accountName(h.account_id)}</TableCell>
              <TableCell className="text-right tabular-nums">{h.qty}</TableCell>
              <TableCell className="text-right tabular-nums">
                {formatMoney(Math.round(avgCost))}
              </TableCell>
              <TableCell className="text-right tabular-nums">
                {h.instrument.current_price_minor == null ? (
                  <Badge variant="muted">No price</Badge>
                ) : (
                  formatMoney(h.instrument.current_price_minor)
                )}
              </TableCell>
              <TableCell className="text-right tabular-nums">
                {formatMoney(h.market_value_minor)}
              </TableCell>
              <TableCell className={`text-right tabular-nums ${pnlColor}`}>
                {pnl == null ? (
                  "—"
                ) : (
                  <>
                    {pnl >= 0 ? "+" : "−"}
                    {formatMoney(Math.abs(pnl))}
                    {pnlPct != null && (
                      <span className="ml-1 text-xs">
                        ({pnlPct >= 0 ? "+" : ""}
                        {pnlPct.toFixed(1)}%)
                      </span>
                    )}
                  </>
                )}
              </TableCell>
              <TableCell className="text-right">
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-8 w-8"
                  title="Update price"
                  onClick={() => onUpdatePrice(h.instrument)}
                >
                  <RefreshCw className="h-4 w-4" />
                </Button>
              </TableCell>
            </TableRow>
          );
        })}
      </TableBody>
    </Table>
  );
}

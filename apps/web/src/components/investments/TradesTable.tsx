import { Trash2 } from "lucide-react";

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
import type { InvestmentTxnResponse, TxnSide } from "@/lib/api";

const SIDE_BADGE: Record<TxnSide, "success" | "destructive" | "secondary"> = {
  buy: "success",
  sell: "destructive",
  dividend: "secondary",
};

// The raw trade ledger with a delete action per row. Deleting a trade re-derives
// holdings on the next fetch.
export function TradesTable({
  rows,
  onDelete,
}: {
  rows: InvestmentTxnResponse[];
  onDelete: (txn: InvestmentTxnResponse) => void;
}) {
  const accountName = useAccountNameLookup();

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead className="w-[120px]">Date</TableHead>
          <TableHead>Instrument</TableHead>
          <TableHead>Account</TableHead>
          <TableHead>Side</TableHead>
          <TableHead className="text-right">Qty</TableHead>
          <TableHead className="text-right">Price</TableHead>
          <TableHead className="text-right">Fee</TableHead>
          <TableHead className="w-[60px]" />
        </TableRow>
      </TableHeader>
      <TableBody>
        {rows.map((t) => (
          <TableRow key={t.id}>
            <TableCell className="tabular-nums">{t.occurred_on}</TableCell>
            <TableCell>
              <span className="font-medium">{t.instrument.name}</span>{" "}
              <span className="text-xs text-muted-foreground">
                · {t.instrument.symbol}
              </span>
            </TableCell>
            <TableCell>{accountName(t.account_id)}</TableCell>
            <TableCell>
              <Badge variant={SIDE_BADGE[t.side]}>{titleCase(t.side)}</Badge>
            </TableCell>
            <TableCell className="text-right tabular-nums">{t.quantity}</TableCell>
            <TableCell className="text-right tabular-nums">
              {formatMoney(t.price_minor)}
            </TableCell>
            <TableCell className="text-right tabular-nums">
              {formatMoney(t.fee_minor)}
            </TableCell>
            <TableCell className="text-right">
              <Button
                variant="ghost"
                size="icon"
                className="h-8 w-8 text-destructive hover:text-destructive"
                onClick={() => onDelete(t)}
              >
                <Trash2 className="h-4 w-4" />
              </Button>
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}

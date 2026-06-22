import { ArrowDown, ArrowUp, Pencil, Trash2 } from "lucide-react";

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
import {
  amountSign,
  cleanNote,
  displayKind,
  isTransfer,
  KIND_COLOR,
  KIND_LABEL,
} from "@/lib/transactions";
import type { TransactionResponse } from "@/lib/api";

const KIND_BADGE: Record<
  TransactionResponse["kind"],
  "success" | "secondary" | "outline"
> = {
  income: "success",
  expense: "secondary",
  transfer: "outline",
};

interface Props {
  rows: TransactionResponse[];
  sortDir: "asc" | "desc";
  onToggleSort: () => void;
  onEdit: (row: TransactionResponse) => void;
  onDelete: (row: TransactionResponse) => void;
  // PF-F8 injects the auto-categorize chip here for uncategorized rows.
  renderCategory?: (row: TransactionResponse) => React.ReactNode;
}

export function TransactionsTable({
  rows,
  sortDir,
  onToggleSort,
  onEdit,
  onDelete,
  renderCategory,
}: Props) {
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead className="w-[140px]">
            <button
              className="flex items-center gap-1 hover:text-foreground"
              onClick={onToggleSort}
            >
              Date
              {sortDir === "desc" ? (
                <ArrowDown className="h-3.5 w-3.5" />
              ) : (
                <ArrowUp className="h-3.5 w-3.5" />
              )}
            </button>
          </TableHead>
          <TableHead className="w-[110px]">Kind</TableHead>
          <TableHead>Account</TableHead>
          <TableHead>Category</TableHead>
          <TableHead className="text-right">Amount</TableHead>
          <TableHead>Note</TableHead>
          <TableHead className="w-[90px] text-right">Actions</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {rows.map((row) => {
          // Sign still comes from the stored kind (a transfer's debit half is an
          // expense => "−", its credit half is an income => "+"), but a tagged
          // row is labelled "Transfer" and shown in a muted colour.
          const transfer = isTransfer(row);
          const dKind = displayKind(row);
          const sign = amountSign(row.kind);
          const prefix = sign === 1 ? "+" : sign === -1 ? "−" : "";
          const amountColor = transfer
            ? "text-muted-foreground"
            : KIND_COLOR[row.kind];
          return (
            // Clicking a row opens the edit dialog (AC: "inline edit on row click").
            <TableRow
              key={row.id}
              className="cursor-pointer"
              onClick={() => onEdit(row)}
            >
              <TableCell className="tabular-nums">{row.occurred_on}</TableCell>
              <TableCell>
                <Badge variant={KIND_BADGE[dKind]}>{KIND_LABEL[dKind]}</Badge>
              </TableCell>
              <TableCell>{row.account_name}</TableCell>
              <TableCell>
                {transfer ? (
                  <span className="text-muted-foreground">—</span>
                ) : row.category_name ? (
                  row.category_name
                ) : renderCategory ? (
                  // PF-F8 chip slot — only for genuine uncategorized income/expense.
                  renderCategory(row)
                ) : (
                  <span className="text-muted-foreground">Uncategorized</span>
                )}
              </TableCell>
              <TableCell
                className={`text-right tabular-nums font-medium ${amountColor}`}
              >
                {prefix}
                {formatMoney(row.amount_minor)}
              </TableCell>
              <TableCell className="max-w-[220px] truncate text-muted-foreground">
                {cleanNote(row.note) || "—"}
              </TableCell>
              <TableCell className="text-right">
                {/* stopPropagation so these buttons don't also trigger the row's
                    edit-on-click handler. */}
                <div className="flex justify-end gap-1">
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-8 w-8"
                    onClick={(e) => {
                      e.stopPropagation();
                      onEdit(row);
                    }}
                  >
                    <Pencil className="h-4 w-4" />
                  </Button>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-8 w-8 text-destructive hover:text-destructive"
                    onClick={(e) => {
                      e.stopPropagation();
                      onDelete(row);
                    }}
                  >
                    <Trash2 className="h-4 w-4" />
                  </Button>
                </div>
              </TableCell>
            </TableRow>
          );
        })}
      </TableBody>
    </Table>
  );
}

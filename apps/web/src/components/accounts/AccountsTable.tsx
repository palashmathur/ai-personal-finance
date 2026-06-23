import { Archive, ArchiveRestore, Pencil, Trash2 } from "lucide-react";

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
import { cn } from "@/lib/utils";
import type { AccountResponse } from "@/lib/api";

interface Props {
  rows: AccountResponse[];
  onEdit: (account: AccountResponse) => void;
  onToggleArchive: (account: AccountResponse) => void;
  onDelete: (account: AccountResponse) => void;
}

export function AccountsTable({
  rows,
  onEdit,
  onToggleArchive,
  onDelete,
}: Props) {
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Name</TableHead>
          <TableHead>Type</TableHead>
          <TableHead className="text-right">Opening balance</TableHead>
          <TableHead>Status</TableHead>
          <TableHead className="w-[130px] text-right">Actions</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {rows.map((a) => (
          // Archived accounts are dimmed so the active ones stand out.
          <TableRow key={a.id} className={cn(a.archived && "opacity-60")}>
            <TableCell className="font-medium">{a.name}</TableCell>
            <TableCell>{titleCase(a.type)}</TableCell>
            <TableCell className="text-right tabular-nums">
              {formatMoney(a.opening_balance_minor)}
            </TableCell>
            <TableCell>
              {a.archived ? (
                <Badge variant="muted">Archived</Badge>
              ) : (
                <Badge variant="success">Active</Badge>
              )}
            </TableCell>
            <TableCell className="text-right">
              <div className="flex justify-end gap-1">
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-8 w-8"
                  title="Edit"
                  onClick={() => onEdit(a)}
                >
                  <Pencil className="h-4 w-4" />
                </Button>
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-8 w-8"
                  title={a.archived ? "Restore" : "Archive"}
                  onClick={() => onToggleArchive(a)}
                >
                  {a.archived ? (
                    <ArchiveRestore className="h-4 w-4" />
                  ) : (
                    <Archive className="h-4 w-4" />
                  )}
                </Button>
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-8 w-8 text-destructive hover:text-destructive"
                  title="Delete"
                  onClick={() => onDelete(a)}
                >
                  <Trash2 className="h-4 w-4" />
                </Button>
              </div>
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}

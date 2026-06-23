import { useEffect, useMemo, useState } from "react";
import { useQuery, keepPreviousData } from "@tanstack/react-query";
import { Plus, Loader2, Upload } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { TransactionsTable } from "@/components/transactions/TransactionsTable";
import { TransactionFormDialog } from "@/components/transactions/TransactionFormDialog";
import { CsvImportDialog } from "@/components/imports/CsvImportDialog";
import { useTransactionMutations } from "@/hooks/useTransactionMutations";
import { useFiltersStore } from "@/store/filters";
import { api } from "@/lib/http";
import type { TransactionResponse } from "@/lib/api";

const PAGE_SIZE = 50;

export function Transactions() {
  const from = useFiltersStore((s) => s.from);
  const to = useFiltersStore((s) => s.to);
  const accountIds = useFiltersStore((s) => s.accountIds);

  // Backend lists support a single account_id filter. We pass it only when
  // exactly one account is selected; 0 or 2+ selected => no account filter
  // (the backend can't AND multiple). Documented MVP limitation.
  const accountId = accountIds.length === 1 ? accountIds[0] : undefined;

  const [page, setPage] = useState(0);
  const [sortDir, setSortDir] = useState<"asc" | "desc">("desc");

  // Dialog/confirm state.
  const [formOpen, setFormOpen] = useState(false);
  const [importOpen, setImportOpen] = useState(false);
  const [editing, setEditing] = useState<TransactionResponse | null>(null);
  const [deleting, setDeleting] = useState<TransactionResponse | null>(null);

  const { create, update, remove } = useTransactionMutations();

  // Reset to the first page whenever the filters change, so we never land on an
  // out-of-range page (e.g. page 3 of a now-tiny result set).
  useEffect(() => {
    setPage(0);
  }, [from, to, accountId]);

  // The filter values are part of the query key — when they change, TanStack
  // Query treats it as a different query and refetches automatically. This is
  // the mechanism behind "change the global date range -> the table updates".
  const { data, isLoading, isFetching } = useQuery({
    queryKey: ["transactions", { from, to, accountId, page }],
    queryFn: () =>
      api.transactions.list({
        from,
        to,
        accountId,
        limit: PAGE_SIZE,
        offset: page * PAGE_SIZE,
      }),
    // Keep showing the previous page's rows while the next page loads (no flicker).
    placeholderData: keepPreviousData,
  });

  const rows = data ?? [];

  // Client-side date sort of the CURRENT page only (the backend always returns
  // date DESC and paginates server-side, so this just flips the loaded page).
  const sortedRows = useMemo(() => {
    const copy = [...rows];
    copy.sort((a, b) =>
      sortDir === "desc"
        ? b.occurred_on.localeCompare(a.occurred_on)
        : a.occurred_on.localeCompare(b.occurred_on)
    );
    return copy;
  }, [rows, sortDir]);

  const hasNext = rows.length === PAGE_SIZE;
  const isEmpty = !isLoading && rows.length === 0;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Transactions</h1>
          <p className="text-sm text-muted-foreground">
            Income, expenses, and transfers for the selected range.
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={() => setImportOpen(true)}>
            <Upload className="h-4 w-4" /> Import CSV
          </Button>
          <Button
            onClick={() => {
              setEditing(null);
              setFormOpen(true);
            }}
          >
            <Plus className="h-4 w-4" /> Add
          </Button>
        </div>
      </div>

      <Card>
        <CardContent className="p-0">
          {isLoading ? (
            <div className="flex items-center justify-center gap-2 py-16 text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin" /> Loading…
            </div>
          ) : isEmpty ? (
            // Empty state with a call to action (AC).
            <div className="flex flex-col items-center gap-3 py-16 text-center">
              <p className="text-sm text-muted-foreground">
                No transactions in this range yet.
              </p>
              <Button
                onClick={() => {
                  setEditing(null);
                  setFormOpen(true);
                }}
              >
                <Plus className="h-4 w-4" /> Add your first transaction
              </Button>
            </div>
          ) : (
            <TransactionsTable
              rows={sortedRows}
              sortDir={sortDir}
              onToggleSort={() =>
                setSortDir((d) => (d === "desc" ? "asc" : "desc"))
              }
              onEdit={(row) => {
                setEditing(row);
                setFormOpen(true);
              }}
              onDelete={(row) => setDeleting(row)}
            />
          )}
        </CardContent>
      </Card>

      {/* Pagination. We can't know the total count (no count endpoint), so "Next"
          is enabled whenever the page came back full. */}
      {!isEmpty && (
        <div className="flex items-center justify-end gap-2 text-sm">
          <span className="mr-2 text-muted-foreground">
            Page {page + 1}
            {isFetching && " · updating…"}
          </span>
          <Button
            variant="outline"
            size="sm"
            disabled={page === 0}
            onClick={() => setPage((p) => Math.max(0, p - 1))}
          >
            Previous
          </Button>
          <Button
            variant="outline"
            size="sm"
            disabled={!hasNext}
            onClick={() => setPage((p) => p + 1)}
          >
            Next
          </Button>
        </div>
      )}

      {/* CSV import flow. */}
      <CsvImportDialog open={importOpen} onOpenChange={setImportOpen} />

      {/* Add / edit dialog. */}
      <TransactionFormDialog
        open={formOpen}
        onOpenChange={setFormOpen}
        initial={editing}
        onCreate={(body) => create.mutateAsync(body)}
        onUpdate={(txnId, body) => update.mutateAsync({ txnId, body })}
      />

      {/* Delete confirmation. */}
      <AlertDialog
        open={deleting !== null}
        onOpenChange={(o) => !o && setDeleting(null)}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete this transaction?</AlertDialogTitle>
            <AlertDialogDescription>
              {deleting?.kind === "transfer"
                ? "This is a transfer — both halves will be deleted. This cannot be undone."
                : "This cannot be undone."}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
              onClick={() => {
                if (deleting) remove.mutate(deleting);
                setDeleting(null);
              }}
            >
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}

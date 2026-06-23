import { useState } from "react";
import { Loader2, Plus } from "lucide-react";

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
import { AccountsTable } from "@/components/accounts/AccountsTable";
import { AccountFormDialog } from "@/components/accounts/AccountFormDialog";
import { useAllAccounts } from "@/hooks/useAccounts";
import { useAccountMutations } from "@/hooks/useAccountMutations";
import type { AccountResponse } from "@/lib/api";

export function Accounts() {
  // Management view shows archived accounts too (so they can be restored).
  const { data: accounts, isLoading } = useAllAccounts();
  const { create, update, remove } = useAccountMutations();

  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState<AccountResponse | null>(null);
  const [deleting, setDeleting] = useState<AccountResponse | null>(null);

  const isEmpty = !isLoading && (accounts?.length ?? 0) === 0;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Accounts</h1>
          <p className="text-sm text-muted-foreground">
            The banks, wallets, and brokers your money and holdings live in.
          </p>
        </div>
        <Button
          onClick={() => {
            setEditing(null);
            setFormOpen(true);
          }}
        >
          <Plus className="h-4 w-4" /> Add account
        </Button>
      </div>

      <Card>
        <CardContent className="p-0">
          {isLoading ? (
            <div className="flex items-center justify-center gap-2 py-16 text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin" /> Loading…
            </div>
          ) : isEmpty ? (
            <div className="flex flex-col items-center gap-3 py-16 text-center">
              <p className="text-sm text-muted-foreground">No accounts yet.</p>
              <Button
                onClick={() => {
                  setEditing(null);
                  setFormOpen(true);
                }}
              >
                <Plus className="h-4 w-4" /> Add your first account
              </Button>
            </div>
          ) : (
            <AccountsTable
              rows={accounts!}
              onEdit={(a) => {
                setEditing(a);
                setFormOpen(true);
              }}
              onToggleArchive={(a) =>
                update.mutate({ id: a.id, body: { archived: !a.archived } })
              }
              onDelete={(a) => setDeleting(a)}
            />
          )}
        </CardContent>
      </Card>

      {/* Add / edit dialog. */}
      <AccountFormDialog
        open={formOpen}
        onOpenChange={setFormOpen}
        initial={editing}
        onCreate={(body) => create.mutateAsync(body)}
        onUpdate={(id, body) => update.mutateAsync({ id, body })}
      />

      {/* Hard-delete confirmation. The backend rejects (409) if the account is
          referenced by any transaction/trade — that error is toasted, and the
          dialog text steers the user toward archiving instead. */}
      <AlertDialog
        open={deleting !== null}
        onOpenChange={(o) => !o && setDeleting(null)}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete this account?</AlertDialogTitle>
            <AlertDialogDescription>
              Permanently deletes “{deleting?.name}”. This only works if no
              transactions or trades reference it — otherwise archive it instead.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
              onClick={() => {
                if (deleting) remove.mutate(deleting.id);
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

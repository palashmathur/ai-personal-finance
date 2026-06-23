import { useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import { api, getApiError } from "@/lib/http";
import type { AccountCreate, AccountUpdate } from "@/lib/api";

// Account writes (create / update / archive-restore / hard-delete). Plain
// invalidate-on-success (not optimistic) — account changes are infrequent and a
// rename changes the denormalized account_name on every transaction, so a clean
// refetch is simpler than patching caches by hand.
export function useAccountMutations() {
  const qc = useQueryClient();

  // Renaming/archiving an account ripples into transactions (denormalized name),
  // holdings, and the dashboard (opening balances feed net worth) — refetch them.
  const invalidateAll = () => {
    qc.invalidateQueries({ queryKey: ["accounts"] }); // covers ['accounts'] + ['accounts','all']
    qc.invalidateQueries({ queryKey: ["transactions"] });
    qc.invalidateQueries({ queryKey: ["holdings"] });
    qc.invalidateQueries({ queryKey: ["dashboard"] });
  };

  const create = useMutation({
    mutationFn: (body: AccountCreate) =>
      api.accounts.create({ requestBody: body }),
    onSuccess: () => {
      toast.success("Account created");
      invalidateAll();
    },
    onError: (err) => toast.error(getApiError(err).detail),
  });

  const update = useMutation({
    mutationFn: (vars: { id: number; body: AccountUpdate }) =>
      api.accounts.update({ accountId: vars.id, requestBody: vars.body }),
    onSuccess: (_data, vars) => {
      // A pure archive/restore gets a clearer toast than a field edit.
      if (vars.body.archived === true) toast.success("Account archived");
      else if (vars.body.archived === false) toast.success("Account restored");
      else toast.success("Account updated");
      invalidateAll();
    },
    onError: (err) => toast.error(getApiError(err).detail),
  });

  const remove = useMutation({
    mutationFn: (id: number) => api.accounts.remove({ accountId: id }),
    onSuccess: () => {
      toast.success("Account deleted");
      invalidateAll();
    },
    // The backend returns 409 with a clear message when transactions/trades still
    // reference the account ("archive it instead") — getApiError surfaces that.
    onError: (err) => toast.error(getApiError(err).detail),
  });

  return { create, update, remove };
}

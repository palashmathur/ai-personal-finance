import {
  useMutation,
  useQueryClient,
  type QueryKey,
} from "@tanstack/react-query";
import { toast } from "sonner";

import { api, getApiError } from "@/lib/http";
import { transferTag } from "@/lib/transactions";
import type {
  AccountResponse,
  CategoryResponse,
  TransactionCreate,
  TransactionResponse,
  TransactionUpdate,
} from "@/lib/api";

// All transaction writes (create / update / delete) live here so the optimistic
// cache logic is written once and reused by both the form dialog and the table.
//
// Optimistic update pattern (TanStack Query):
//   onMutate  -> cancel in-flight refetches, snapshot the cache, apply the change
//                immediately so the UI feels instant.
//   onError   -> roll back to the snapshot and toast the backend's error.
//   onSettled -> invalidate so the server's real data replaces our guess, and the
//                dashboard recomputes.
// Java analogy: optimistic UI is like updating the local view before the server
// ACKs, holding the previous state so you can "rollback the transaction" on failure.

// Look up a display name from a cache, with a safe fallback for the temp row.
function accountName(accounts: AccountResponse[] | undefined, id: number | null) {
  if (id == null) return "";
  return accounts?.find((a) => a.id === id)?.name ?? "…";
}

function categoryName(
  tree: CategoryResponse[] | undefined,
  id: number | null | undefined
): string | null {
  if (id == null || !tree) return null;
  for (const parent of tree) {
    if (parent.id === id) return parent.name;
    for (const child of parent.children ?? []) {
      if (child.id === id) return child.name;
    }
  }
  return null;
}

// Build the temp row(s) we prepend while the POST is in flight. Income/expense =>
// one row; transfer => two rows (source + destination), matching what the backend
// actually inserts. Negative ids guarantee no collision with real ids.
function optimisticRows(
  body: TransactionCreate,
  accounts: AccountResponse[] | undefined,
  categories: CategoryResponse[] | undefined
): TransactionResponse[] {
  const now = new Date().toISOString();
  const base = {
    amount_minor: body.amount_minor,
    occurred_on: body.occurred_on,
    note: body.note ?? null,
    source: body.source ?? "manual",
    created_at: now,
    updated_at: now,
  } as const;

  if (body.kind === "transfer") {
    const seed = Date.now();
    // Mirror the backend: two rows whose kind is expense (source) / income
    // (destination), tagged so the UI renders them as a transfer immediately —
    // identical to the rows that come back on refetch.
    const tag = "#transfer:optimistic";
    const note = body.note ? `${body.note} ${tag}` : tag;
    return [
      {
        id: -seed,
        kind: "expense",
        account_id: body.from_account_id!,
        account_name: accountName(accounts, body.from_account_id ?? null),
        category_id: null,
        category_name: null,
        ...base,
        note,
      },
      {
        id: -seed - 1,
        kind: "income",
        account_id: body.to_account_id!,
        account_name: accountName(accounts, body.to_account_id ?? null),
        category_id: null,
        category_name: null,
        ...base,
        note,
      },
    ];
  }

  return [
    {
      id: -Date.now(),
      kind: body.kind,
      account_id: body.account_id!,
      account_name: accountName(accounts, body.account_id ?? null),
      category_id: body.category_id ?? null,
      category_name: categoryName(categories, body.category_id),
      ...base,
    },
  ];
}

export function useTransactionMutations() {
  const qc = useQueryClient();

  // Refetch every transaction list and the dashboard after any write settles.
  const invalidateAll = () => {
    qc.invalidateQueries({ queryKey: ["transactions"] });
    qc.invalidateQueries({ queryKey: ["dashboard"] });
  };

  // Snapshot all cached transaction lists so onError can restore them verbatim.
  async function snapshotLists(): Promise<[QueryKey, TransactionResponse[] | undefined][]> {
    await qc.cancelQueries({ queryKey: ["transactions"] });
    return qc.getQueriesData<TransactionResponse[]>({ queryKey: ["transactions"] });
  }

  function restore(prev: [QueryKey, TransactionResponse[] | undefined][] | undefined) {
    prev?.forEach(([key, data]) => qc.setQueryData(key, data));
  }

  const create = useMutation({
    mutationFn: (body: TransactionCreate) =>
      api.transactions.create({ requestBody: body }),
    onMutate: async (body) => {
      const prev = await snapshotLists();
      const accounts = qc.getQueryData<AccountResponse[]>(["accounts"]);
      const categories = qc.getQueryData<CategoryResponse[]>(["categories"]);
      const temp = optimisticRows(body, accounts, categories);
      // Prepend to every cached list — the new row is usually "today" so it
      // belongs at the top of the default (date DESC) view; invalidation on
      // settle fixes any list it doesn't actually belong to.
      qc.setQueriesData<TransactionResponse[]>(
        { queryKey: ["transactions"] },
        (old) => (old ? [...temp, ...old] : old)
      );
      return { prev };
    },
    onError: (err, _body, ctx) => {
      restore(ctx?.prev);
      toast.error(getApiError(err).detail);
    },
    onSuccess: (rows) => {
      toast.success(
        rows.length === 2 ? "Transfer recorded" : "Transaction added"
      );
    },
    onSettled: invalidateAll,
  });

  const update = useMutation({
    mutationFn: (vars: { txnId: number; body: TransactionUpdate }) =>
      api.transactions.update({ txnId: vars.txnId, requestBody: vars.body }),
    onMutate: async ({ txnId, body }) => {
      const prev = await snapshotLists();
      const categories = qc.getQueryData<CategoryResponse[]>(["categories"]);

      // Find the edited row to detect whether it's a transfer (so we patch both
      // halves, matched by the shared #transfer tag).
      let tag: string | null = null;
      for (const [, list] of prev) {
        const hit = list?.find((t) => t.id === txnId);
        if (hit) {
          tag = transferTag(hit.note);
          break;
        }
      }

      qc.setQueriesData<TransactionResponse[]>(
        { queryKey: ["transactions"] },
        (old) =>
          old?.map((t) => {
            const isTarget =
              t.id === txnId || (tag != null && transferTag(t.note) === tag);
            if (!isTarget) return t;
            return {
              ...t,
              amount_minor: body.amount_minor ?? t.amount_minor,
              occurred_on: body.occurred_on ?? t.occurred_on,
              note: body.note !== undefined ? body.note : t.note,
              category_id:
                body.category_id !== undefined ? body.category_id : t.category_id,
              category_name:
                body.category_id !== undefined
                  ? categoryName(categories, body.category_id)
                  : t.category_name,
              updated_at: new Date().toISOString(),
            };
          })
      );
      return { prev };
    },
    onError: (err, _vars, ctx) => {
      restore(ctx?.prev);
      toast.error(getApiError(err).detail);
    },
    onSuccess: () => toast.success("Transaction updated"),
    onSettled: invalidateAll,
  });

  const remove = useMutation({
    mutationFn: (txn: TransactionResponse) =>
      api.transactions.remove({ txnId: txn.id }),
    onMutate: async (txn) => {
      const prev = await snapshotLists();
      const tag = transferTag(txn.note);
      // Remove the row; for a transfer, also remove its partner half.
      qc.setQueriesData<TransactionResponse[]>(
        { queryKey: ["transactions"] },
        (old) =>
          old?.filter((t) => {
            if (t.id === txn.id) return false;
            if (tag != null && transferTag(t.note) === tag) return false;
            return true;
          })
      );
      return { prev };
    },
    onError: (err, _txn, ctx) => {
      restore(ctx?.prev);
      toast.error(getApiError(err).detail);
    },
    onSuccess: () => toast.success("Transaction deleted"),
    onSettled: invalidateAll,
  });

  return { create, update, remove };
}

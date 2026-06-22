import type { TransactionResponse } from "@/lib/api";

// Shared display helpers for transactions — kept out of components so the table,
// the form, and (later) other views all format a transaction the same way.

// The transfer tag the backend embeds in the note, e.g. "Rent #transfer:abc-123".
const TRANSFER_TAG_RE = /\s*#transfer:[a-f0-9-]+/i;

/** Strip the internal "#transfer:<uuid>" tag so the user only sees their own note text. */
export function cleanNote(note: string | null | undefined): string {
  if (!note) return "";
  return note.replace(TRANSFER_TAG_RE, "").trim();
}

/** Return the "#transfer:<uuid>" tag if this note belongs to a transfer, else null. */
export function transferTag(note: string | null | undefined): string | null {
  if (!note) return null;
  const m = note.match(/#transfer:[a-f0-9-]+/i);
  return m ? m[0] : null;
}

// IMPORTANT: the backend splits a transfer into TWO rows whose `kind` is actually
// "expense" (the source/debit half) and "income" (the destination/credit half) —
// NOT "transfer". The only reliable signal that a row is part of a transfer is the
// "#transfer:<uuid>" tag in its note. So everywhere in the UI we detect transfers
// by this tag, never by row.kind.
export function isTransfer(row: { note: string | null | undefined }): boolean {
  return transferTag(row.note) != null;
}

// The kind we show to the user: a tagged row is presented as "transfer" even
// though its stored kind is income/expense.
export function displayKind(
  row: TransactionResponse
): TransactionResponse["kind"] {
  return isTransfer(row) ? "transfer" : row.kind;
}

/** Sign of a transaction for cashflow display: income adds, expense subtracts. */
export function amountSign(kind: TransactionResponse["kind"]): 1 | -1 | 0 {
  if (kind === "income") return 1;
  if (kind === "expense") return -1;
  return 0; // transfer is cash-neutral overall
}

// Tailwind text color per kind, used on the amount cell and kind badge.
export const KIND_COLOR: Record<TransactionResponse["kind"], string> = {
  income: "text-emerald-600 dark:text-emerald-400",
  expense: "text-foreground",
  transfer: "text-muted-foreground",
};

export const KIND_LABEL: Record<TransactionResponse["kind"], string> = {
  income: "Income",
  expense: "Expense",
  transfer: "Transfer",
};

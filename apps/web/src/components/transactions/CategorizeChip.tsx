import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Check, Sparkles, X } from "lucide-react";

import { cn } from "@/lib/utils";
import { api, getApiError } from "@/lib/http";
import type { CategorizeSuggestResponse, TransactionResponse } from "@/lib/api";

// The inline auto-categorize chip (PF-F8). Shown only on uncategorized
// income/expense rows (the table excludes transfers). It asks the backend for a
// suggestion and offers one-click accept (writes a rule + tags the txn) or dismiss.
//
// Cost note: the suggest call is rules-first on the backend (an LLM call only when
// no saved rule matches). We cache by (note, amount) with staleTime: Infinity so
// repeated identical notes — e.g. many "Swiggy" rows — only cost one suggestion.
export function CategorizeChip({ row }: { row: TransactionResponse }) {
  const qc = useQueryClient();
  const [dismissed, setDismissed] = useState(false);
  const hasNote = !!row.note?.trim();

  const suggest = useQuery({
    queryKey: ["categorize-suggest", row.note, row.amount_minor],
    queryFn: () =>
      api.categorize.suggest({
        requestBody: { note: row.note ?? "", amount_minor: row.amount_minor },
      }),
    enabled: hasNote && !dismissed,
    staleTime: Infinity,
    gcTime: Infinity,
    retry: false,
  });

  const accept = useMutation({
    mutationFn: (s: CategorizeSuggestResponse) =>
      api.categorize.accept({
        requestBody: {
          // Save the LLM's suggested regex if present, else fall back to the note
          // as a literal pattern so a rule still gets written.
          pattern: s.suggested_rule ?? (row.note ?? "").trim(),
          category_id: s.category_id!,
          // Also stamp this category onto the transaction right now.
          transaction_id: row.id,
        },
      }),
    onSuccess: (_data, s) => {
      toast.success(`Categorized as ${s.category_name}`);
      qc.invalidateQueries({ queryKey: ["transactions"] });
      qc.invalidateQueries({ queryKey: ["dashboard"] });
    },
    onError: (err) => toast.error(getApiError(err).detail),
  });

  const muted = <span className="text-muted-foreground">Uncategorized</span>;

  if (dismissed || !hasNote) return muted;

  if (suggest.isLoading) {
    return (
      <span className="flex items-center gap-1 text-xs text-muted-foreground">
        <Sparkles className="h-3 w-3 animate-pulse" /> suggesting…
      </span>
    );
  }

  const s = suggest.data;
  if (!s || s.category_id == null || s.category_name == null) return muted;

  const pct = Math.round(s.confidence * 100);
  // Below 60% confidence the suggestion is shown muted (not highlighted).
  const low = s.confidence < 0.6;

  return (
    // stopPropagation so clicking the chip doesn't also open the row's edit dialog.
    <div
      className="flex items-center gap-1.5"
      onClick={(e) => e.stopPropagation()}
    >
      <span
        className={cn(
          "text-xs",
          low ? "text-muted-foreground" : "text-foreground"
        )}
      >
        Suggested: <span className="font-medium">{s.category_name}</span> ({pct}%)
      </span>
      <button
        title="Accept suggestion"
        className="rounded p-0.5 hover:bg-accent disabled:opacity-50"
        disabled={accept.isPending}
        onClick={() => accept.mutate(s)}
      >
        <Check className="h-3.5 w-3.5 text-emerald-600 dark:text-emerald-400" />
      </button>
      <button
        title="Dismiss"
        className="rounded p-0.5 hover:bg-accent"
        onClick={() => setDismissed(true)}
      >
        <X className="h-3.5 w-3.5 text-muted-foreground" />
      </button>
    </div>
  );
}

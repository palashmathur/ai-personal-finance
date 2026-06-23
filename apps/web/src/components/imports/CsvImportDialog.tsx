import { useEffect, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { CheckCircle2, FileUp, Loader2 } from "lucide-react";

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { api, getApiError } from "@/lib/http";
import { formatMoney } from "@/lib/money";
import { useAccounts } from "@/hooks/useAccounts";
import { useCategories, flattenCategoryOptions } from "@/hooks/useCategories";
import type { ImportResult, PreviewRow } from "@/lib/api";

type Step = "upload" | "review" | "done";

// Sentinel value for the "no category" option (Radix Select can't use "").
const NONE = "none";

interface Props {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

// Three-step CSV import: upload -> review/adjust -> confirm.
// Backend note: the confirm endpoint applies ONE account to every row (picked
// once here), while the category is per row. So this dialog has a single account
// selector plus a per-row category dropdown — matching the API, not a per-row
// account (which the backend doesn't support).
export function CsvImportDialog({ open, onOpenChange }: Props) {
  const qc = useQueryClient();
  const { data: accounts } = useAccounts();
  const { data: categories } = useCategories();

  const [step, setStep] = useState<Step>("upload");
  const [file, setFile] = useState<File | null>(null);
  const [rows, setRows] = useState<PreviewRow[]>([]);
  const [accountId, setAccountId] = useState("");
  const [result, setResult] = useState<ImportResult | null>(null);

  // Reset to a clean slate every time the dialog opens.
  useEffect(() => {
    if (!open) return;
    setStep("upload");
    setFile(null);
    setRows([]);
    setAccountId("");
    setResult(null);
  }, [open]);

  const preview = useMutation({
    mutationFn: (f: File) =>
      api.imports.preview({ formData: { file: f } }),
    onSuccess: (res) => {
      setRows(res.rows);
      setStep("review");
    },
    onError: (err) => toast.error(getApiError(err).detail),
  });

  const confirm = useMutation({
    mutationFn: () =>
      api.imports.confirm({
        requestBody: {
          account_id: Number(accountId),
          rows: rows.map((r) => ({
            occurred_on: r.occurred_on,
            amount_minor: r.amount_minor,
            kind: r.kind,
            note: r.note,
            category_id: r.category_id,
          })),
        },
      }),
    onSuccess: (res) => {
      setResult(res);
      setStep("done");
      // New transactions landed — refresh the ledger and dashboard.
      qc.invalidateQueries({ queryKey: ["transactions"] });
      qc.invalidateQueries({ queryKey: ["dashboard"] });
      toast.success(`Imported ${res.inserted}, skipped ${res.skipped}`);
    },
    onError: (err) => toast.error(getApiError(err).detail),
  });

  // Update one row's category in local state before confirming.
  function setRowCategory(index: number, value: string) {
    setRows((prev) =>
      prev.map((r, i) =>
        i === index
          ? { ...r, category_id: value === NONE ? null : Number(value) }
          : r
      )
    );
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-3xl">
        <DialogHeader>
          <DialogTitle>Import transactions from CSV</DialogTitle>
          <DialogDescription>
            Columns: date (DD/MM/YYYY), amount, type (debit/credit), narration,
            category (optional).
          </DialogDescription>
        </DialogHeader>

        {/* STEP 1 — upload. */}
        {step === "upload" && (
          <div className="space-y-4">
            <label className="flex cursor-pointer flex-col items-center gap-2 rounded-lg border border-dashed p-10 text-center hover:bg-accent/40">
              <FileUp className="h-8 w-8 text-muted-foreground" />
              <span className="text-sm font-medium">
                {file ? file.name : "Choose a .csv file"}
              </span>
              <span className="text-xs text-muted-foreground">
                Nothing is saved until you confirm.
              </span>
              <input
                type="file"
                accept=".csv,text/csv"
                className="hidden"
                onChange={(e) => setFile(e.target.files?.[0] ?? null)}
              />
            </label>

            <DialogFooter>
              <Button variant="outline" onClick={() => onOpenChange(false)}>
                Cancel
              </Button>
              <Button
                disabled={!file || preview.isPending}
                onClick={() => file && preview.mutate(file)}
              >
                {preview.isPending && (
                  <Loader2 className="h-4 w-4 animate-spin" />
                )}
                Parse file
              </Button>
            </DialogFooter>
          </div>
        )}

        {/* STEP 2 — review & adjust. */}
        {step === "review" && (
          <div className="space-y-4">
            <div className="flex items-end justify-between gap-4">
              <div className="w-56 space-y-1.5">
                <Label>Import into account</Label>
                <Select value={accountId} onValueChange={setAccountId}>
                  <SelectTrigger>
                    <SelectValue placeholder="Select account" />
                  </SelectTrigger>
                  <SelectContent>
                    {(accounts ?? []).map((a) => (
                      <SelectItem key={a.id} value={String(a.id)}>
                        {a.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <p className="text-sm text-muted-foreground">
                {rows.length} row{rows.length === 1 ? "" : "s"} parsed
              </p>
            </div>

            <div className="max-h-80 overflow-auto rounded-md border">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Date</TableHead>
                    <TableHead>Kind</TableHead>
                    <TableHead className="text-right">Amount</TableHead>
                    <TableHead>Note</TableHead>
                    <TableHead className="w-[200px]">Category</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {rows.map((r, i) => {
                    const options = flattenCategoryOptions(
                      categories,
                      r.kind === "income" ? "income" : "expense"
                    );
                    return (
                      <TableRow key={i}>
                        <TableCell className="tabular-nums">
                          {r.occurred_on}
                        </TableCell>
                        <TableCell>
                          <Badge
                            variant={
                              r.kind === "income" ? "success" : "secondary"
                            }
                          >
                            {r.kind}
                          </Badge>
                        </TableCell>
                        <TableCell className="text-right tabular-nums">
                          {formatMoney(r.amount_minor)}
                        </TableCell>
                        <TableCell className="max-w-[180px] truncate">
                          {r.note}
                        </TableCell>
                        <TableCell>
                          <div className="flex items-center gap-1">
                            <Select
                              value={
                                r.category_id != null
                                  ? String(r.category_id)
                                  : NONE
                              }
                              onValueChange={(v) => setRowCategory(i, v)}
                            >
                              <SelectTrigger className="h-8">
                                <SelectValue placeholder="Uncategorized" />
                              </SelectTrigger>
                              <SelectContent>
                                <SelectItem value={NONE}>
                                  Uncategorized
                                </SelectItem>
                                {options.map((c) => (
                                  <SelectItem key={c.id} value={String(c.id)}>
                                    {c.label}
                                  </SelectItem>
                                ))}
                              </SelectContent>
                            </Select>
                            {/* Where the suggestion came from (csv match / rule / LLM). */}
                            {r.category_source && (
                              <span
                                className="text-[10px] uppercase text-muted-foreground"
                                title="Suggestion source"
                              >
                                {r.category_source}
                              </span>
                            )}
                          </div>
                        </TableCell>
                      </TableRow>
                    );
                  })}
                </TableBody>
              </Table>
            </div>

            <DialogFooter>
              <Button variant="outline" onClick={() => setStep("upload")}>
                Back
              </Button>
              <Button
                disabled={!accountId || confirm.isPending}
                onClick={() => confirm.mutate()}
              >
                {confirm.isPending && (
                  <Loader2 className="h-4 w-4 animate-spin" />
                )}
                Confirm import
              </Button>
            </DialogFooter>
          </div>
        )}

        {/* STEP 3 — done. */}
        {step === "done" && result && (
          <div className="space-y-4">
            <div className="flex flex-col items-center gap-2 py-6 text-center">
              <CheckCircle2 className="h-10 w-10 text-emerald-500" />
              <p className="text-lg font-medium">Import complete</p>
              <p className="text-sm text-muted-foreground">
                <span className="font-semibold text-foreground">
                  {result.inserted}
                </span>{" "}
                inserted ·{" "}
                <span className="font-semibold text-foreground">
                  {result.skipped}
                </span>{" "}
                skipped (already existed)
              </p>
            </div>
            <DialogFooter>
              <Button variant="outline" onClick={() => setStep("upload")}>
                Import another
              </Button>
              <Button onClick={() => onOpenChange(false)}>Done</Button>
            </DialogFooter>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}

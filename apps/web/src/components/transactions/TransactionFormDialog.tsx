import { useEffect, useMemo } from "react";
import { useForm, Controller } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { cn } from "@/lib/utils";
import { rupeesToPaise, paiseToRupees } from "@/lib/money";
import { cleanNote, isTransfer, KIND_LABEL } from "@/lib/transactions";
import { useAccounts } from "@/hooks/useAccounts";
import { useCategories, flattenCategoryOptions } from "@/hooks/useCategories";
import type {
  TransactionCreate,
  TransactionResponse,
  TransactionUpdate,
} from "@/lib/api";

// zod schema. Amount stays a string (what the <input> gives us) and is validated
// numerically; conditional requirements (transfer vs income/expense) are enforced
// in superRefine — the form-layer equivalent of the backend's cross-field checks.
const schema = z
  .object({
    kind: z.enum(["income", "expense", "transfer"]),
    amount: z
      .string()
      .min(1, "Enter an amount")
      .refine((v) => Number(v) > 0, "Amount must be greater than 0"),
    occurred_on: z.string().min(1, "Pick a date"),
    note: z.string().optional(),
    account_id: z.string().optional(),
    category_id: z.string().optional(),
    from_account_id: z.string().optional(),
    to_account_id: z.string().optional(),
  })
  .superRefine((val, ctx) => {
    if (val.kind === "transfer") {
      if (!val.from_account_id)
        ctx.addIssue({ path: ["from_account_id"], code: "custom", message: "Required" });
      if (!val.to_account_id)
        ctx.addIssue({ path: ["to_account_id"], code: "custom", message: "Required" });
      if (
        val.from_account_id &&
        val.to_account_id &&
        val.from_account_id === val.to_account_id
      )
        ctx.addIssue({
          path: ["to_account_id"],
          code: "custom",
          message: "Must differ from source",
        });
    } else {
      if (!val.account_id)
        ctx.addIssue({ path: ["account_id"], code: "custom", message: "Required" });
      if (!val.category_id)
        ctx.addIssue({ path: ["category_id"], code: "custom", message: "Required" });
    }
  });

type FormValues = z.infer<typeof schema>;

function todayIso(): string {
  return new Date().toISOString().slice(0, 10);
}

interface Props {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  // When present, the dialog is in edit mode for this row.
  initial?: TransactionResponse | null;
  onCreate: (body: TransactionCreate) => Promise<unknown>;
  onUpdate: (txnId: number, body: TransactionUpdate) => Promise<unknown>;
}

export function TransactionFormDialog({
  open,
  onOpenChange,
  initial,
  onCreate,
  onUpdate,
}: Props) {
  const isEdit = !!initial;
  // A transfer half is stored as income/expense + a #transfer note tag, so detect
  // it by the tag (not by kind) to drive the transfer-specific edit behaviour.
  const initialIsTransfer = initial ? isTransfer(initial) : false;
  const { data: accounts } = useAccounts();
  const { data: categories } = useCategories();

  const {
    register,
    handleSubmit,
    control,
    watch,
    reset,
    setValue,
    formState: { errors, isSubmitting },
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: {
      kind: "expense",
      amount: "",
      occurred_on: todayIso(),
      note: "",
      account_id: "",
      category_id: "",
      from_account_id: "",
      to_account_id: "",
    },
  });

  const kind = watch("kind");

  // Reset the form whenever the dialog opens or the edited row changes.
  // (Forms are uncontrolled internally; reset() is how RHF re-seeds them.)
  useEffect(() => {
    if (!open) return;
    if (initial) {
      reset({
        kind: initialIsTransfer ? "transfer" : initial.kind,
        amount: String(paiseToRupees(initial.amount_minor)),
        occurred_on: initial.occurred_on,
        note: cleanNote(initial.note),
        account_id: initial.account_id ? String(initial.account_id) : "",
        category_id: initial.category_id ? String(initial.category_id) : "",
        from_account_id: "",
        to_account_id: "",
      });
    } else {
      reset({
        kind: "expense",
        amount: "",
        occurred_on: todayIso(),
        note: "",
        account_id: "",
        category_id: "",
        from_account_id: "",
        to_account_id: "",
      });
    }
  }, [open, initial, reset]);

  // Category options depend on the selected kind (income vs expense). Transfers
  // have no category. When the kind flips in create mode, clear a now-invalid pick.
  const categoryOptions = useMemo(
    () =>
      kind === "transfer"
        ? []
        : flattenCategoryOptions(categories, kind),
    [categories, kind]
  );

  const onValid = handleSubmit(async (values) => {
    const amount_minor = rupeesToPaise(Number(values.amount));
    const note = values.note?.trim() ? values.note.trim() : null;

    try {
      if (isEdit && initial) {
        // TransactionUpdate can't change kind or account; we send the editable
        // fields. category only applies to income/expense rows.
        const body: TransactionUpdate = {
          amount_minor,
          occurred_on: values.occurred_on,
          note,
        };
        if (!initialIsTransfer) {
          body.category_id = Number(values.category_id);
        }
        await onUpdate(initial.id, body);
      } else if (values.kind === "transfer") {
        await onCreate({
          kind: "transfer",
          amount_minor,
          occurred_on: values.occurred_on,
          note,
          from_account_id: Number(values.from_account_id),
          to_account_id: Number(values.to_account_id),
        });
      } else {
        await onCreate({
          kind: values.kind,
          amount_minor,
          occurred_on: values.occurred_on,
          note,
          account_id: Number(values.account_id),
          category_id: Number(values.category_id),
        });
      }
      onOpenChange(false);
    } catch {
      // The mutation already toasts the backend error; keep the dialog open so
      // the user can correct and retry.
    }
  });

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{isEdit ? "Edit transaction" : "Add transaction"}</DialogTitle>
          <DialogDescription>
            {isEdit
              ? "Update the editable fields below."
              : "Record an income, expense, or transfer between your accounts."}
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={onValid} className="space-y-4">
          {/* Kind picker — a 3-way segmented control. Disabled in edit mode
              because changing a transaction's kind isn't a PATCH operation. */}
          <div className="space-y-1.5">
            <Label>Type</Label>
            <div className="grid grid-cols-3 gap-2">
              {(["income", "expense", "transfer"] as const).map((k) => (
                <Button
                  key={k}
                  type="button"
                  variant={kind === k ? "default" : "outline"}
                  disabled={isEdit}
                  onClick={() => {
                    setValue("kind", k);
                    // Clear fields that don't apply to the new kind.
                    setValue("category_id", "");
                  }}
                >
                  {KIND_LABEL[k]}
                </Button>
              ))}
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-1.5">
              <Label htmlFor="amount">Amount (₹)</Label>
              <Input
                id="amount"
                type="number"
                step="0.01"
                min="0"
                placeholder="0.00"
                {...register("amount")}
              />
              <FieldError msg={errors.amount?.message} />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="occurred_on">Date</Label>
              <Input id="occurred_on" type="date" {...register("occurred_on")} />
              <FieldError msg={errors.occurred_on?.message} />
            </div>
          </div>

          {/* Income/expense: account + category. */}
          {kind !== "transfer" && (
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-1.5">
                <Label>Account</Label>
                <Controller
                  control={control}
                  name="account_id"
                  render={({ field }) => (
                    <Select
                      value={field.value}
                      onValueChange={field.onChange}
                      // Account can't be changed on edit (no API field for it).
                      disabled={isEdit}
                    >
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
                  )}
                />
                <FieldError msg={errors.account_id?.message} />
              </div>
              <div className="space-y-1.5">
                <Label>Category</Label>
                <Controller
                  control={control}
                  name="category_id"
                  render={({ field }) => (
                    <Select value={field.value} onValueChange={field.onChange}>
                      <SelectTrigger>
                        <SelectValue placeholder="Select category" />
                      </SelectTrigger>
                      <SelectContent>
                        {categoryOptions.map((c) => (
                          <SelectItem key={c.id} value={String(c.id)}>
                            {c.label}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  )}
                />
                <FieldError msg={errors.category_id?.message} />
              </div>
            </div>
          )}

          {/* Transfer: from + to accounts. Not editable once created (the API has
              no way to re-route an existing transfer — delete & re-create). */}
          {kind === "transfer" && !isEdit && (
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-1.5">
                <Label>From account</Label>
                <Controller
                  control={control}
                  name="from_account_id"
                  render={({ field }) => (
                    <Select value={field.value} onValueChange={field.onChange}>
                      <SelectTrigger>
                        <SelectValue placeholder="Source" />
                      </SelectTrigger>
                      <SelectContent>
                        {(accounts ?? []).map((a) => (
                          <SelectItem key={a.id} value={String(a.id)}>
                            {a.name}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  )}
                />
                <FieldError msg={errors.from_account_id?.message} />
              </div>
              <div className="space-y-1.5">
                <Label>To account</Label>
                <Controller
                  control={control}
                  name="to_account_id"
                  render={({ field }) => (
                    <Select value={field.value} onValueChange={field.onChange}>
                      <SelectTrigger>
                        <SelectValue placeholder="Destination" />
                      </SelectTrigger>
                      <SelectContent>
                        {(accounts ?? []).map((a) => (
                          <SelectItem key={a.id} value={String(a.id)}>
                            {a.name}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  )}
                />
                <FieldError msg={errors.to_account_id?.message} />
              </div>
            </div>
          )}

          {kind === "transfer" && isEdit && (
            <p className="text-xs text-muted-foreground">
              Editing a transfer updates both halves (amount, date, note). To change
              the accounts, delete and re-create the transfer.
            </p>
          )}

          <div className="space-y-1.5">
            <Label htmlFor="note">Note</Label>
            <Input id="note" placeholder="optional" {...register("note")} />
          </div>

          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange(false)}
            >
              Cancel
            </Button>
            <Button type="submit" disabled={isSubmitting}>
              {isEdit ? "Save changes" : "Add"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

// Tiny inline error line under a field.
function FieldError({ msg }: { msg?: string }) {
  if (!msg) return null;
  return <p className={cn("text-xs text-destructive")}>{msg}</p>;
}

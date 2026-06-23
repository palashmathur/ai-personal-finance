import { useEffect } from "react";
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
import { rupeesToPaise, paiseToRupees } from "@/lib/money";
import { titleCase } from "@/lib/labels";
import type { AccountCreate, AccountResponse, AccountType, AccountUpdate } from "@/lib/api";

const ACCOUNT_TYPES: AccountType[] = [
  "bank",
  "cash",
  "broker",
  "wallet",
  "credit_card",
];

const schema = z.object({
  name: z.string().min(1, "Name is required"),
  type: z.enum(["cash", "bank", "broker", "wallet", "credit_card"]),
  // Opening balance is optional; empty = 0. Must be >= 0 (backend rule).
  opening_balance: z
    .string()
    .refine((v) => v === "" || Number(v) >= 0, "Must be ≥ 0"),
});

type FormValues = z.infer<typeof schema>;

interface Props {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  initial?: AccountResponse | null; // present => edit mode
  onCreate: (body: AccountCreate) => Promise<unknown>;
  onUpdate: (id: number, body: AccountUpdate) => Promise<unknown>;
}

export function AccountFormDialog({
  open,
  onOpenChange,
  initial,
  onCreate,
  onUpdate,
}: Props) {
  const isEdit = !!initial;

  const {
    register,
    handleSubmit,
    control,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: { name: "", type: "bank", opening_balance: "" },
  });

  useEffect(() => {
    if (!open) return;
    reset(
      initial
        ? {
            name: initial.name,
            type: initial.type,
            opening_balance: String(paiseToRupees(initial.opening_balance_minor)),
          }
        : { name: "", type: "bank", opening_balance: "" }
    );
  }, [open, initial, reset]);

  const onValid = handleSubmit(async (values) => {
    const opening_balance_minor = rupeesToPaise(Number(values.opening_balance || 0));
    try {
      if (isEdit && initial) {
        await onUpdate(initial.id, {
          name: values.name.trim(),
          type: values.type,
          opening_balance_minor,
        });
      } else {
        await onCreate({
          name: values.name.trim(),
          type: values.type,
          opening_balance_minor,
        });
      }
      onOpenChange(false);
    } catch {
      // Mutation toasts the backend error (e.g. duplicate name 409); keep open.
    }
  });

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>{isEdit ? "Edit account" : "Add account"}</DialogTitle>
          <DialogDescription>
            {isEdit
              ? "Update the account's name, type, or opening balance."
              : "Create a bank, cash, broker, wallet, or credit-card account."}
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={onValid} className="space-y-4">
          <div className="space-y-1.5">
            <Label htmlFor="name">Name</Label>
            <Input id="name" placeholder="e.g. HDFC Savings" {...register("name")} />
            {errors.name && (
              <p className="text-xs text-destructive">{errors.name.message}</p>
            )}
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-1.5">
              <Label>Type</Label>
              <Controller
                control={control}
                name="type"
                render={({ field }) => (
                  <Select value={field.value} onValueChange={field.onChange}>
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {ACCOUNT_TYPES.map((t) => (
                        <SelectItem key={t} value={t}>
                          {titleCase(t)}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                )}
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="opening">Opening balance (₹)</Label>
              <Input
                id="opening"
                type="number"
                step="0.01"
                min="0"
                placeholder="0.00"
                {...register("opening_balance")}
              />
              {errors.opening_balance && (
                <p className="text-xs text-destructive">
                  {errors.opening_balance.message}
                </p>
              )}
            </div>
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
              {isEdit ? "Save changes" : "Add account"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

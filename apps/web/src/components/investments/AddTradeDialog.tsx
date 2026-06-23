import { useEffect, useState } from "react";
import { Check, Plus, Search, X } from "lucide-react";

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
import { rupeesToPaise } from "@/lib/money";
import { titleCase } from "@/lib/labels";
import { useAccounts } from "@/hooks/useAccounts";
import { useInstrumentSearch } from "@/hooks/useInvestments";
import { useInvestmentMutations } from "@/hooks/useInvestmentMutations";
import type { InstrumentKind, InstrumentResponse, TxnSide } from "@/lib/api";

const KINDS: InstrumentKind[] = [
  "mutual_fund",
  "stock",
  "etf",
  "crypto",
  "metal",
  "other",
];

const todayIso = () => new Date().toISOString().slice(0, 10);

interface Props {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

// Add Trade. Two sub-flows for the instrument:
//   - search & pick an existing instrument (typeahead), or
//   - "create new instrument" inline (kind/symbol/name), which is POSTed first,
//     then the trade is recorded against the new id (find-or-create pattern).
// This dialog is hand-rolled with useState rather than react-hook-form because the
// instrument selection is a small state machine that's clearer as plain state.
export function AddTradeDialog({ open, onOpenChange }: Props) {
  const { data: accounts } = useAccounts();
  const { createInstrument, createTrade } = useInvestmentMutations();

  // Investment trades can debit any account except a credit card (per backend rule).
  const tradableAccounts = (accounts ?? []).filter(
    (a) => a.type !== "credit_card"
  );

  // --- instrument selection state ---
  const [search, setSearch] = useState("");
  const [selected, setSelected] = useState<InstrumentResponse | null>(null);
  const [createMode, setCreateMode] = useState(false);
  const [newKind, setNewKind] = useState<InstrumentKind>("stock");
  const [newSymbol, setNewSymbol] = useState("");
  const [newName, setNewName] = useState("");
  const { data: results, isFetching } = useInstrumentSearch(search);

  // --- trade fields ---
  const [accountId, setAccountId] = useState("");
  const [side, setSide] = useState<TxnSide>("buy");
  const [qty, setQty] = useState("");
  const [price, setPrice] = useState("");
  const [fee, setFee] = useState("");
  const [date, setDate] = useState(todayIso());
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const isDividend = side === "dividend";

  // Reset everything each time the dialog opens.
  useEffect(() => {
    if (!open) return;
    setSearch("");
    setSelected(null);
    setCreateMode(false);
    setNewKind("stock");
    setNewSymbol("");
    setNewName("");
    setAccountId("");
    setSide("buy");
    setQty("");
    setPrice("");
    setFee("");
    setDate(todayIso());
    setError(null);
  }, [open]);

  const hasInstrument = selected != null || (createMode && newSymbol && newName);

  async function handleSubmit() {
    setError(null);

    // Validate.
    if (!hasInstrument) return setError("Pick or create an instrument.");
    if (!accountId) return setError("Choose an account.");
    if (!date) return setError("Pick a trade date.");
    const priceNum = Number(price);
    if (!(priceNum >= 0) || price === "")
      return setError(isDividend ? "Enter the dividend amount." : "Enter a price.");
    const qtyNum = isDividend ? 1 : Number(qty);
    if (!isDividend && !(qtyNum > 0)) return setError("Quantity must be > 0.");

    setSubmitting(true);
    try {
      // find-or-create the instrument first.
      let instrumentId: number;
      if (selected) {
        instrumentId = selected.id;
      } else {
        const created = await createInstrument.mutateAsync({
          kind: newKind,
          symbol: newSymbol.trim(),
          name: newName.trim(),
        });
        instrumentId = created.id;
      }

      await createTrade.mutateAsync({
        account_id: Number(accountId),
        instrument_id: instrumentId,
        side,
        // Dividend convention: quantity=1, price_minor = total amount.
        quantity: qtyNum,
        price_minor: rupeesToPaise(priceNum),
        fee_minor: isDividend ? 0 : rupeesToPaise(Number(fee) || 0),
        occurred_on: date,
      });
      onOpenChange(false);
    } catch {
      // mutation already toasted; keep the dialog open for a retry.
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-xl">
        <DialogHeader>
          <DialogTitle>Add trade</DialogTitle>
          <DialogDescription>
            Record a buy, sell, or dividend. New instruments are created on the fly.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          {/* Instrument selection. */}
          <div className="space-y-1.5">
            <Label>Instrument</Label>

            {selected ? (
              <div className="flex items-center justify-between rounded-md border bg-muted/40 px-3 py-2 text-sm">
                <span>
                  <span className="font-medium">{selected.name}</span>{" "}
                  <span className="text-muted-foreground">
                    · {selected.symbol} · {titleCase(selected.kind)}
                  </span>
                </span>
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-7 w-7"
                  onClick={() => setSelected(null)}
                >
                  <X className="h-4 w-4" />
                </Button>
              </div>
            ) : createMode ? (
              <div className="space-y-2 rounded-md border p-3">
                <div className="grid grid-cols-3 gap-2">
                  <div className="space-y-1">
                    <Label className="text-xs">Kind</Label>
                    <Select
                      value={newKind}
                      onValueChange={(v) => setNewKind(v as InstrumentKind)}
                    >
                      <SelectTrigger>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {KINDS.map((k) => (
                          <SelectItem key={k} value={k}>
                            {titleCase(k)}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="space-y-1">
                    <Label className="text-xs">Symbol</Label>
                    <Input
                      value={newSymbol}
                      onChange={(e) => setNewSymbol(e.target.value)}
                      placeholder="e.g. HDFCBANK"
                    />
                  </div>
                  <div className="space-y-1">
                    <Label className="text-xs">Name</Label>
                    <Input
                      value={newName}
                      onChange={(e) => setNewName(e.target.value)}
                      placeholder="e.g. HDFC Bank Ltd"
                    />
                  </div>
                </div>
                <button
                  className="text-xs text-muted-foreground hover:text-foreground"
                  onClick={() => setCreateMode(false)}
                >
                  ← Back to search
                </button>
              </div>
            ) : (
              <div className="rounded-md border">
                <div className="flex items-center gap-2 px-3 py-2">
                  <Search className="h-4 w-4 text-muted-foreground" />
                  <input
                    autoFocus
                    value={search}
                    onChange={(e) => setSearch(e.target.value)}
                    placeholder="Search instruments by name or symbol…"
                    className="w-full bg-transparent text-sm outline-none"
                  />
                </div>
                {(search.trim().length > 0 || (results?.length ?? 0) > 0) && (
                  <div className="max-h-44 overflow-auto border-t">
                    {(results ?? []).map((inst) => (
                      <button
                        key={inst.id}
                        className="flex w-full items-center justify-between px-3 py-2 text-left text-sm hover:bg-accent"
                        onClick={() => {
                          setSelected(inst);
                          setSearch("");
                        }}
                      >
                        <span>
                          {inst.name}{" "}
                          <span className="text-muted-foreground">
                            · {inst.symbol}
                          </span>
                        </span>
                        <Check className="h-4 w-4 opacity-0" />
                      </button>
                    ))}
                    {!isFetching &&
                      search.trim().length > 0 &&
                      (results?.length ?? 0) === 0 && (
                        <p className="px-3 py-2 text-xs text-muted-foreground">
                          No matches.
                        </p>
                      )}
                    <button
                      className="flex w-full items-center gap-2 border-t px-3 py-2 text-left text-sm text-primary hover:bg-accent"
                      onClick={() => {
                        setCreateMode(true);
                        setNewName(search);
                      }}
                    >
                      <Plus className="h-4 w-4" /> Create new instrument
                    </button>
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Account + side. */}
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-1.5">
              <Label>Account</Label>
              <Select value={accountId} onValueChange={setAccountId}>
                <SelectTrigger>
                  <SelectValue placeholder="Select account" />
                </SelectTrigger>
                <SelectContent>
                  {tradableAccounts.map((a) => (
                    <SelectItem key={a.id} value={String(a.id)}>
                      {a.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1.5">
              <Label>Side</Label>
              <Select value={side} onValueChange={(v) => setSide(v as TxnSide)}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="buy">Buy</SelectItem>
                  <SelectItem value="sell">Sell</SelectItem>
                  <SelectItem value="dividend">Dividend</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>

          {/* Numbers. For a dividend the qty/fee fields collapse — the backend
              convention is quantity=1 with the total amount in price. */}
          <div className="grid grid-cols-2 gap-4">
            {!isDividend && (
              <div className="space-y-1.5">
                <Label htmlFor="qty">Quantity</Label>
                <Input
                  id="qty"
                  type="number"
                  step="any"
                  min="0"
                  value={qty}
                  onChange={(e) => setQty(e.target.value)}
                  placeholder="0"
                />
              </div>
            )}
            <div className="space-y-1.5">
              <Label htmlFor="price">
                {isDividend ? "Dividend amount (₹)" : "Price per unit (₹)"}
              </Label>
              <Input
                id="price"
                type="number"
                step="0.01"
                min="0"
                value={price}
                onChange={(e) => setPrice(e.target.value)}
                placeholder="0.00"
              />
            </div>
            {!isDividend && (
              <div className="space-y-1.5">
                <Label htmlFor="fee">Fee (₹)</Label>
                <Input
                  id="fee"
                  type="number"
                  step="0.01"
                  min="0"
                  value={fee}
                  onChange={(e) => setFee(e.target.value)}
                  placeholder="0.00"
                />
              </div>
            )}
            <div className="space-y-1.5">
              <Label htmlFor="trade-date">Date</Label>
              <Input
                id="trade-date"
                type="date"
                value={date}
                onChange={(e) => setDate(e.target.value)}
              />
            </div>
          </div>

          {error && <p className="text-sm text-destructive">{error}</p>}
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button onClick={handleSubmit} disabled={submitting}>
            Add trade
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

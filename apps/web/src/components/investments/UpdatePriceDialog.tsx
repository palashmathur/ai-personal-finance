import { useEffect, useState } from "react";

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
import { paiseToRupees, rupeesToPaise } from "@/lib/money";
import { useInvestmentMutations } from "@/hooks/useInvestmentMutations";
import type { HoldingInstrument } from "@/lib/api";

interface Props {
  // The instrument to re-price; null closes the dialog.
  instrument: HoldingInstrument | null;
  onClose: () => void;
}

// Manual price refresh (until the V2 price-fetch cron exists). PATCHes
// current_price_minor on the instrument, which re-prices holdings + net worth.
export function UpdatePriceDialog({ instrument, onClose }: Props) {
  const { updatePrice } = useInvestmentMutations();
  const [price, setPrice] = useState("");

  // Pre-fill with the current price each time a different instrument is opened.
  useEffect(() => {
    if (instrument) {
      setPrice(
        instrument.current_price_minor != null
          ? String(paiseToRupees(instrument.current_price_minor))
          : ""
      );
    }
  }, [instrument]);

  async function handleSave() {
    if (!instrument) return;
    const num = Number(price);
    if (!(num >= 0) || price === "") return;
    try {
      await updatePrice.mutateAsync({
        instrumentId: instrument.id,
        priceMinor: rupeesToPaise(num),
      });
      onClose();
    } catch {
      // toasted by the mutation; keep open
    }
  }

  return (
    <Dialog open={instrument != null} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-w-sm">
        <DialogHeader>
          <DialogTitle>Update price</DialogTitle>
          <DialogDescription>
            {instrument
              ? `${instrument.name} · ${instrument.symbol}`
              : ""}
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-1.5">
          <Label htmlFor="price">Current price per unit (₹)</Label>
          <Input
            id="price"
            type="number"
            step="0.01"
            min="0"
            autoFocus
            value={price}
            onChange={(e) => setPrice(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleSave()}
          />
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>
            Cancel
          </Button>
          <Button onClick={handleSave} disabled={updatePrice.isPending}>
            Save
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

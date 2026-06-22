import { useState } from "react";
import { Loader2, Plus } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
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
import { HoldingsTable } from "@/components/investments/HoldingsTable";
import { TradesTable } from "@/components/investments/TradesTable";
import { AddTradeDialog } from "@/components/investments/AddTradeDialog";
import { UpdatePriceDialog } from "@/components/investments/UpdatePriceDialog";
import { useHoldings, useTrades } from "@/hooks/useInvestments";
import { useInvestmentMutations } from "@/hooks/useInvestmentMutations";
import type { HoldingInstrument, InvestmentTxnResponse } from "@/lib/api";

export function Investments() {
  const holdings = useHoldings();
  const trades = useTrades();
  const { deleteTrade } = useInvestmentMutations();

  const [addOpen, setAddOpen] = useState(false);
  const [pricing, setPricing] = useState<HoldingInstrument | null>(null);
  const [deleting, setDeleting] = useState<InvestmentTxnResponse | null>(null);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Investments</h1>
          <p className="text-sm text-muted-foreground">
            Current holdings and your trade history.
          </p>
        </div>
        <Button onClick={() => setAddOpen(true)}>
          <Plus className="h-4 w-4" /> Add trade
        </Button>
      </div>

      <Tabs defaultValue="holdings">
        <TabsList>
          <TabsTrigger value="holdings">Holdings</TabsTrigger>
          <TabsTrigger value="trades">Trades</TabsTrigger>
        </TabsList>

        {/* Holdings tab. */}
        <TabsContent value="holdings">
          <Card>
            <CardContent className="p-0">
              {holdings.isLoading ? (
                <Loading />
              ) : (holdings.data?.length ?? 0) === 0 ? (
                <Empty
                  message="No open holdings yet."
                  onAdd={() => setAddOpen(true)}
                />
              ) : (
                <HoldingsTable
                  rows={holdings.data!}
                  onUpdatePrice={(inst) => setPricing(inst)}
                />
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* Trades tab. */}
        <TabsContent value="trades">
          <Card>
            <CardContent className="p-0">
              {trades.isLoading ? (
                <Loading />
              ) : (trades.data?.length ?? 0) === 0 ? (
                <Empty
                  message="No trades in this range."
                  onAdd={() => setAddOpen(true)}
                />
              ) : (
                <TradesTable
                  rows={trades.data!}
                  onDelete={(t) => setDeleting(t)}
                />
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      <AddTradeDialog open={addOpen} onOpenChange={setAddOpen} />
      <UpdatePriceDialog instrument={pricing} onClose={() => setPricing(null)} />

      {/* Delete-trade confirmation. */}
      <AlertDialog
        open={deleting !== null}
        onOpenChange={(o) => !o && setDeleting(null)}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete this trade?</AlertDialogTitle>
            <AlertDialogDescription>
              Holdings will be recalculated. This cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
              onClick={() => {
                if (deleting) deleteTrade.mutate(deleting.id);
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

function Loading() {
  return (
    <div className="flex items-center justify-center gap-2 py-16 text-muted-foreground">
      <Loader2 className="h-4 w-4 animate-spin" /> Loading…
    </div>
  );
}

function Empty({
  message,
  onAdd,
}: {
  message: string;
  onAdd: () => void;
}) {
  return (
    <div className="flex flex-col items-center gap-3 py-16 text-center">
      <p className="text-sm text-muted-foreground">{message}</p>
      <Button onClick={onAdd}>
        <Plus className="h-4 w-4" /> Add a trade
      </Button>
    </div>
  );
}

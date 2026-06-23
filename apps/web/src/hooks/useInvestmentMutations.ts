import { useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import { api, getApiError } from "@/lib/http";
import type { InstrumentCreate, InvestmentTxnCreate } from "@/lib/api";

// Writes for the investments page. We keep these as plain invalidate-on-success
// mutations (not optimistic like transactions): holdings/allocation are computed
// server-side via GROUP BY, so re-deriving them optimistically on the client would
// duplicate backend math and risk drift. A refetch after the write is simpler and
// always correct.
export function useInvestmentMutations() {
  const qc = useQueryClient();

  // After a trade write, holdings + the dashboard (allocation/net worth) + the
  // trade ledger all need to refetch.
  const invalidateTradeViews = () => {
    qc.invalidateQueries({ queryKey: ["holdings"] });
    qc.invalidateQueries({ queryKey: ["dashboard"] });
    qc.invalidateQueries({ queryKey: ["investment-txns"] });
  };

  // Create an instrument (find-or-create flow). No toast here — it's an internal
  // step of "add trade for a brand-new instrument"; the trade toast covers it.
  const createInstrument = useMutation({
    mutationFn: (body: InstrumentCreate) =>
      api.instruments.create({ requestBody: body }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["instruments"] }),
  });

  const createTrade = useMutation({
    mutationFn: (body: InvestmentTxnCreate) =>
      api.investmentTxns.create({ requestBody: body }),
    onSuccess: () => {
      toast.success("Trade recorded");
      invalidateTradeViews();
    },
    onError: (err) => toast.error(getApiError(err).detail),
  });

  // Manual price refresh (PATCH the instrument). Re-prices holdings + net worth.
  const updatePrice = useMutation({
    mutationFn: (vars: { instrumentId: number; priceMinor: number }) =>
      api.instruments.update({
        instrumentId: vars.instrumentId,
        requestBody: { current_price_minor: vars.priceMinor },
      }),
    onSuccess: () => {
      toast.success("Price updated");
      qc.invalidateQueries({ queryKey: ["holdings"] });
      qc.invalidateQueries({ queryKey: ["dashboard"] });
      qc.invalidateQueries({ queryKey: ["instruments"] });
    },
    onError: (err) => toast.error(getApiError(err).detail),
  });

  const deleteTrade = useMutation({
    mutationFn: (txnId: number) => api.investmentTxns.remove({ txnId }),
    onSuccess: () => {
      toast.success("Trade deleted");
      invalidateTradeViews();
    },
    onError: (err) => toast.error(getApiError(err).detail),
  });

  return { createInstrument, createTrade, updatePrice, deleteTrade };
}

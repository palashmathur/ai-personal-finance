# Pydantic schemas for the Holdings resource.
# Holdings are not stored — they are computed on the fly by aggregating investment_txns.
# Think of this as the read-side projection of your trade ledger: "what do I own right now?"
#
# There is no Create/Update/Delete schema here because holdings are never written directly.
# The only write path is through investment_txns — holdings recompute from those rows.

from typing import Optional

from pydantic import BaseModel, ConfigDict


class HoldingInstrument(BaseModel):
    """
    Minimal instrument info embedded in every HoldingResponse.
    Gives the caller the display name, kind (for allocation grouping),
    and current price (for market value) without a separate API call.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    kind: str
    symbol: str
    name: str
    # The most recently known price per unit in paise. NULL means no price has been set yet.
    current_price_minor: Optional[int]


class HoldingResponse(BaseModel):
    """
    One row in the holdings response — represents a single (account, instrument) position.

    All monetary values are in paise (integers). The frontend divides by 100 to display ₹.

    market_value_minor and unrealized_pnl_minor will be None when current_price_minor
    is NULL on the instrument — the UI should show a "price missing" state in that case.
    """

    model_config = ConfigDict(from_attributes=True)

    instrument_id: int
    instrument: HoldingInstrument
    account_id: int
    # Net units currently held: SUM(buy qty) - SUM(sell qty).
    qty: float
    # Total cash invested: SUM(buy qty × price + fee) for all buys on this position.
    cost_basis_minor: int
    # Current market value: qty × instrument.current_price_minor.
    # None when the instrument has no price set.
    market_value_minor: Optional[int]
    # Unrealized gain/loss: market_value - cost_basis.
    # None when market_value_minor is None.
    unrealized_pnl_minor: Optional[int]

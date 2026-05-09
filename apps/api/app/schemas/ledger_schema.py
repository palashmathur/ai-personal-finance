# Pydantic schema for the Unified Ledger endpoint.
# The ledger merges cash transactions and investment trades into one timeline —
# like a bank statement that also shows your stock buys and sells.
#
# Because the two source tables have different columns, some fields will be None
# depending on the row type. The `source` and `kind` fields tell you which:
#
#   source="cash",       kind="income"|"expense"|"transfer"  → category_id set
#   source="investment", kind="inv_buy"|"inv_sell"|"inv_dividend" → instrument_id set

from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel


class LedgerEntryResponse(BaseModel):
    """
    One row in the unified ledger — could be a cash transaction or an investment trade.

    Fields that don't apply to a particular row type are None.
    Use `source` + `kind` to decide how to render the row in the UI.
    """

    # "cash" for transactions table rows, "investment" for investment_txns rows.
    source: str
    # The ID of the originating row in its source table.
    source_id: int
    # income | expense | transfer | inv_buy | inv_sell | inv_dividend
    kind: str
    account_id: int
    # Set for income/expense rows. None for transfer and all investment rows.
    category_id: Optional[int]
    # Set for investment rows. None for all cash rows.
    instrument_id: Optional[int]
    # Set for investment rows (units traded). None for cash rows.
    quantity: Optional[float]
    # Always set. For investments: buy = cash out, sell/dividend = cash in (positive).
    amount_minor: int
    occurred_on: date
    note: Optional[str]
    created_at: datetime

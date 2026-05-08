# Pydantic schemas for the InvestmentTxns resource.
# Every buy, sell, and dividend you've ever made is a row in investment_txns.
# Think of these as your Spring Boot @RequestBody / @ResponseBody DTOs for the trade ledger.
#
# Key design points:
#  - `side` drives all the sign logic: buy = cash out, sell = cash in, dividend = cash in.
#  - `quantity` is a float because mutual funds trade in fractional units (e.g. 12.347 units).
#  - `price_minor` and `fee_minor` are integers in paise — no floats for money.
#  - The response embeds a nested InstrumentSummary so callers know what was traded
#    without a second API call.

from datetime import date, datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict


class TxnSide(str, Enum):
    """
    Direction of the trade. Drives how the row is interpreted in holdings math.
    buy: you spent cash and received units. sell: you received cash and gave up units.
    dividend: you received cash with no change in units (quantity=1, price_minor=total amount).
    """

    buy = "buy"
    sell = "sell"
    dividend = "dividend"


class InvestmentTxnCreate(BaseModel):
    """
    Request body for POST /api/investment-txns.

    Both account_id and instrument_id must reference existing rows — the service
    validates this and returns 404 if either is missing.
    account_id must also be type broker or wallet — the service returns 422 otherwise.
    """

    account_id: int
    instrument_id: int
    side: TxnSide
    # Float because MFs trade fractional units. For dividends, use quantity=1.
    quantity: float
    # Per-unit price in paise. For dividends, store the total payout here (with quantity=1).
    price_minor: int
    # Brokerage + STT + GST + any other fees, in paise. Defaults to 0 if not provided.
    fee_minor: int = 0
    occurred_on: date
    note: Optional[str] = None
    # manual|csv|nl — tracks how this trade was entered, for audit and analytics.
    source: str = "manual"



class InvestmentTxnUpdate(BaseModel):
    """
    Request body for PATCH /api/investment-txns/{id}.
    All fields optional — only the ones you send are changed (true PATCH semantics).

    Most common update: correcting a price or fee after entry.
    """

    model_config = ConfigDict(extra="ignore")

    account_id: Optional[int] = None
    instrument_id: Optional[int] = None
    side: Optional[TxnSide] = None
    quantity: Optional[float] = None
    price_minor: Optional[int] = None
    fee_minor: Optional[int] = None
    occurred_on: Optional[date] = None
    note: Optional[str] = None
    source: Optional[str] = None



class InstrumentSummary(BaseModel):
    """
    Minimal instrument info embedded in every InvestmentTxnResponse.
    Gives the caller enough context to display "what was this trade for"
    without needing a separate GET /api/instruments/{id} call.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    kind: str
    symbol: str
    name: str
    current_price_minor: Optional[int]


class InvestmentTxnResponse(BaseModel):
    """
    Response shape returned by every investment-txns endpoint.
    Embeds a nested instrument summary so the frontend holdings table
    can show instrument details alongside trade details in a single response.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    account_id: int
    instrument_id: int
    instrument: InstrumentSummary
    side: TxnSide
    quantity: float
    price_minor: int
    fee_minor: int
    occurred_on: date
    note: Optional[str]
    source: str
    created_at: datetime
    updated_at: datetime

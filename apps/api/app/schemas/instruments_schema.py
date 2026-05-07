# Pydantic schemas for the Instruments resource.
# Instruments are the catalog of investable things — stocks, mutual funds, ETFs, crypto, metals.
# Think of these as your Spring Boot @RequestBody / @ResponseBody DTOs.
#
# The key design point: an instrument is an *identity* (what you can trade),
# not an event (a trade). So the schema is simple — name, kind, symbol, current price.

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict


class InstrumentKind(str, Enum):
    """
    The asset class of the instrument. Drives two things:
    1. Which price-fetch API is used in V2 (AMFI for mutual_fund, yfinance for stock/etf, etc.)
    2. How holdings are grouped in the allocation donut chart on the dashboard.
    """

    mutual_fund = "mutual_fund"
    stock = "stock"
    etf = "etf"
    crypto = "crypto"
    metal = "metal"
    other = "other"


class InstrumentCreate(BaseModel):
    """
    Request body for POST /api/instruments.

    `symbol` is the machine-readable identifier — NSE ticker for stocks,
    AMFI scheme code for mutual funds, CoinGecko ID for crypto, etc.
    The uniqueness constraint is on (kind, symbol) together, not symbol alone,
    because the same ticker can exist on multiple exchanges with different kinds
    (e.g. a Nifty ETF has both an NSE symbol and an AMFI code).
    """

    kind: InstrumentKind
    symbol: str
    name: str
    # Optional at creation — can be set later via PATCH or bootstrapped from the first trade.
    current_price_minor: Optional[int] = None
    # Flexible bag for source-specific IDs: {"isin": "...", "exchange": "NSE", "amfi_code": "..."}
    meta: Optional[dict] = None


class InstrumentUpdate(BaseModel):
    """
    Request body for PATCH /api/instruments/{id}.
    All fields optional — only the fields you send are updated (PATCH semantics).

    `current_price_minor` is the most common update: when you manually refresh a price
    before the V2 price-fetch cron is built, this is how you do it.
    """

    model_config = ConfigDict(extra="ignore")

    name: Optional[str] = None
    current_price_minor: Optional[int] = None
    meta: Optional[dict] = None


class InstrumentResponse(BaseModel):
    """
    Response shape returned by every instruments endpoint.
    `from_attributes=True` lets Pydantic read directly from SQLAlchemy model instances
    — the same as orm_mode in Pydantic v1.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    kind: InstrumentKind
    symbol: str
    name: str
    current_price_minor: Optional[int]
    price_updated_at: Optional[datetime]
    meta: Optional[dict]

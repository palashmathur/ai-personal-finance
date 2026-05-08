# FastAPI router for the InvestmentTxns resource.
# Pure HTTP plumbing — validate the request, call the service, return the response.
# Think of this as your Spring Boot @RestController for the trade ledger.
#
# Four endpoints:
#   POST   /api/investment-txns          — record a new buy/sell/dividend
#   GET    /api/investment-txns          — list trades with optional filters
#   PATCH  /api/investment-txns/{id}     — partial update of a trade
#   DELETE /api/investment-txns/{id}     — hard-delete a trade

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.investment_txns_schema import (
    InvestmentTxnCreate,
    InvestmentTxnResponse,
    InvestmentTxnUpdate,
    TxnSide,
)
from app.services import investment_txns_service

router = APIRouter(prefix="/api/investment-txns", tags=["investment-txns"])


@router.post("", response_model=InvestmentTxnResponse, status_code=status.HTTP_201_CREATED)
def create_investment_txn(data: InvestmentTxnCreate, db: Session = Depends(get_db)):
    """
    Record a new investment trade (buy, sell, or dividend).

    The account must be type broker, wallet, bank, or cash — credit_card is the only rejected type.
    Bank/cash are allowed because SIP debits come directly from a bank account.
    The instrument must already exist in the catalog — create it first via POST /api/instruments.
    On the very first trade for an instrument, its current_price_minor is bootstrapped
    from this trade's price so the holdings page has a non-NULL price immediately.
    """
    return investment_txns_service.create_investment_txn(db, data)


@router.get("", response_model=list[InvestmentTxnResponse])
def list_investment_txns(
    from_date: Optional[date] = Query(None, alias="from"),
    to_date: Optional[date] = Query(None, alias="to"),
    instrument_id: Optional[int] = None,
    account_id: Optional[int] = None,
    side: Optional[TxnSide] = None,
    db: Session = Depends(get_db),
):
    """
    List investment trades, newest first. All filters are optional and AND-combined.

    - ?from=2026-01-01&to=2026-03-31   — date range filter
    - ?instrument_id=7                  — only trades for one instrument
    - ?account_id=3                     — only trades in one broker account
    - ?side=buy                         — only buys (or sell, dividend)
    """
    return investment_txns_service.list_investment_txns(
        db,
        from_date=from_date,
        to_date=to_date,
        instrument_id=instrument_id,
        account_id=account_id,
        side=side.value if side else None,
    )


@router.patch("/{txn_id}", response_model=InvestmentTxnResponse)
def update_investment_txn(
    txn_id: int, data: InvestmentTxnUpdate, db: Session = Depends(get_db)
):
    """
    Partially update a trade. Only the fields you send are changed.

    Useful for correcting a price, fee, or date after the fact.
    If you change account_id or instrument_id, the new values are validated (404 if missing,
    422 if the account type is wrong).
    """
    return investment_txns_service.update_investment_txn(db, txn_id, data)


@router.delete("/{txn_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_investment_txn(txn_id: int, db: Session = Depends(get_db)):
    """
    Hard-delete a trade by ID.

    The holdings aggregation recalculates from remaining rows — no other cleanup needed.
    Returns 204 No Content on success.
    """
    investment_txns_service.delete_investment_txn(db, txn_id)

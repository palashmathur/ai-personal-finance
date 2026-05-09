# FastAPI router for the Holdings resource.
# Holdings are read-only — there is no POST/PATCH/DELETE here.
# The only way to change a holding is by adding trades via /api/investment-txns.
# Think of this as a materialised view endpoint: the DB does the GROUP BY,
# we just serve the result.

from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.holdings_schema import HoldingResponse
from app.services import holdings_service

router = APIRouter(prefix="/api/holdings", tags=["holdings"])


@router.get("", response_model=list[HoldingResponse])
def get_holdings(account_id: Optional[int] = None, db: Session = Depends(get_db)):
    """
    Return current holdings — one row per (account, instrument) pair with qty > 0.

    Computed live from the investment_txns ledger — no separate holdings table.
    Positions that have been fully sold (qty <= 0) are excluded automatically.

    - No filter: all holdings across all accounts.
    - ?account_id=3: holdings in one specific broker/bank account only.

    Each row includes: qty, cost_basis_minor, market_value_minor (None if no price),
    unrealized_pnl_minor (None if no price), and a nested instrument summary.
    """
    return holdings_service.get_holdings(db, account_id=account_id)

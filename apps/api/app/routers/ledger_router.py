# FastAPI router for the Unified Ledger endpoint.
# One GET endpoint that returns a merged, paginated timeline of cash transactions
# and investment trades — the "bank statement" view of all money movements.

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.ledger_schema import LedgerEntryResponse
from app.services import ledger_service

router = APIRouter(prefix="/api/ledger", tags=["ledger"])


@router.get("", response_model=list[LedgerEntryResponse])
def list_ledger(
    from_date: date = Query(..., alias="from"),
    to_date: date = Query(..., alias="to"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """
    Return a unified, paginated ledger merging cash transactions and investment trades.

    Both `from` and `to` are required. Results are ordered by occurred_on DESC
    (most recent first), then created_at DESC for same-day entries.

    Each row has a `source` field ("cash" or "investment") and a `kind` field:
    - cash rows: income | expense | transfer
    - investment rows: inv_buy | inv_sell | inv_dividend

    Pagination: use `limit` (max 200, default 50) and `offset` for paging.
    """
    if from_date > to_date:
        raise HTTPException(
            status_code=422,
            detail=f"'from' ({from_date}) must not be after 'to' ({to_date}).",
        )

    return ledger_service.list_ledger(
        db,
        from_date=from_date,
        to_date=to_date,
        limit=limit,
        offset=offset,
    )

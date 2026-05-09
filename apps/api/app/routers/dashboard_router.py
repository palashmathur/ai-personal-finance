# FastAPI router for the Dashboard endpoint.
# One GET endpoint that assembles all four dashboard blocks in a single response.
# Think of this as the orchestrator — it calls the analytics service functions
# and bundles their results into the DashboardResponse shape.

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.dashboard_schema import DashboardResponse
from app.services import analytics

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("", response_model=DashboardResponse)
def get_dashboard(
    from_date: date = Query(..., alias="from"),
    to_date: date = Query(..., alias="to"),
    db: Session = Depends(get_db),
):
    """
    Return all four dashboard blocks for the given date range.

    Both `from` and `to` are required — the dashboard always shows a specific period.
    `from` must be on or before `to`, otherwise a 422 is returned.
    Typical values: first and last day of the current month, or a 3-month window.

    Blocks:
    - cashflow: income, expenses, savings rate for the period.
    - by_category: expense breakdown per category, ordered by spend descending.
    - allocation: current portfolio split by asset class (stock, mutual_fund, etc.).
    - networth_series: month-end net worth snapshots across the period.
    """
    if from_date > to_date:
        raise HTTPException(
            status_code=422,
            detail=f"'from' ({from_date}) must not be after 'to' ({to_date}).",
        )

    return DashboardResponse(
        cashflow=analytics.compute_cashflow(db, from_date, to_date),
        by_category=analytics.compute_category_breakdown(db, from_date, to_date),
        allocation=analytics.compute_allocation(db),
        networth_series=analytics.compute_networth_series(db, from_date, to_date),
    )

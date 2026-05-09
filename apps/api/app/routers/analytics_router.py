# FastAPI router for analytics endpoints.
# Grouped under /api/analytics/ — a clean prefix for future analytical endpoints
# beyond just the monthly summary (e.g. category trends, savings rate history).

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.monthly_schema import MonthRow
from app.services import analytics

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


@router.get("/monthly", response_model=list[MonthRow])
def monthly_cashflow_summary(
    from_date: date = Query(..., alias="from"),
    to_date: date = Query(..., alias="to"),
    db: Session = Depends(get_db),
):
    """
    Return per-month income, expense, investment, and savings breakdown.

    One row per calendar month in the requested range. Both `from` and `to`
    are required and `from` must not be after `to`.

    Percentages (expense_pct, invest_pct, savings_pct) are null for any month
    where income is zero — dividing by zero would produce a meaningless value.

    Typical use: drive a monthly bar chart on the dashboard showing income vs
    expenses vs investments side by side across a 3–12 month window.
    """
    if from_date > to_date:
        raise HTTPException(
            status_code=422,
            detail=f"'from' ({from_date}) must not be after 'to' ({to_date}).",
        )

    return analytics.compute_monthly_summary(db, from_date, to_date)

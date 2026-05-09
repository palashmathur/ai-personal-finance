# Pydantic schemas for the Dashboard endpoint.
# The dashboard is a single GET that returns four pre-computed blocks in one response.
# Nothing is written here — this is purely a read-side aggregation schema.
#
# Think of it like a DTO that bundles four different report sections into one API call,
# so the frontend doesn't need four separate requests to render the dashboard page.

from typing import Optional

from pydantic import BaseModel


class CashflowBlock(BaseModel):
    """
    Period income, expenses, and the resulting savings rate.
    savings_rate is None when income is 0 — dividing by zero would give nonsense.
    """

    income_minor: int
    expense_minor: int
    # (income - expense) / income. None when income == 0 to avoid misleading 0%.
    savings_rate: Optional[float]


class CategoryBreakdownItem(BaseModel):
    """
    One row in the expense breakdown — how much was spent in a given category
    during the period. Used to render the horizontal bar chart on the dashboard.
    """

    category_id: int
    category_name: str
    # The parent category name, if this is a child category. None for top-level.
    parent_name: Optional[str]
    total_minor: int


class AllocationItem(BaseModel):
    """
    One slice of the portfolio allocation donut.
    Groups holdings by instrument.kind (stock, mutual_fund, etf, crypto, metal, other).
    """

    kind: str
    market_value_minor: int
    # Percentage of total portfolio value. 0.65 means 65%.
    pct: float


class NetWorthPoint(BaseModel):
    """One data point on the net worth line chart — month-end snapshot."""

    # Year-month label, e.g. "2026-04". Used as the x-axis tick on the chart.
    month: str
    networth_minor: int


class DashboardResponse(BaseModel):
    """
    The full dashboard payload — all four blocks in one response.

    The frontend receives this single JSON object and fans it out to four chart components.
    Keeping it as one call means one loading spinner, not four independent spinners.
    """

    cashflow: CashflowBlock
    by_category: list[CategoryBreakdownItem]
    allocation: list[AllocationItem]
    networth_series: list[NetWorthPoint]

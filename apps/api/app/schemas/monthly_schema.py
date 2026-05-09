# Pydantic schema for the Monthly Cashflow Summary endpoint.
# One MonthRow per calendar month in the requested range — the data behind
# a "monthly trends" bar chart showing income vs expenses vs investments.

from typing import Optional

from pydantic import BaseModel


class MonthRow(BaseModel):
    """
    One month's cashflow breakdown.

    All *_minor fields are in paise (integers).
    All *_pct fields are floats in the range [0, 1] — e.g. 0.60 means 60%.
    *_pct fields are None when income_minor == 0 to avoid meaningless percentages.
    """

    # Year-month string used as the x-axis label, e.g. "2026-04".
    ym: str
    income_minor: int
    expense_minor: int
    # Total cash invested (buy-side trades only — sell/dividend proceeds not included).
    invest_minor: int
    # expense / income. None when income is 0.
    expense_pct: Optional[float]
    # invest / income. None when income is 0.
    invest_pct: Optional[float]
    # income - expense - invest
    savings_minor: int
    # savings / income. None when income is 0.
    savings_pct: Optional[float]

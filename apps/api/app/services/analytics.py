# Analytics service — all dashboard math lives here as pure functions.
# No FastAPI imports, no HTTP concerns. Just data in, numbers out.
# Think of this as the @Service layer that the dashboard @RestController calls.
#
# Every function takes a SQLAlchemy Session + date range and returns a plain
# Python object. This makes them easy to unit-test with a known dataset.

from datetime import date

from sqlalchemy import case, func
from sqlalchemy.orm import Session

from app.models import Account, Category, Instrument, InvestmentTxn, Transaction
from app.schemas.dashboard_schema import (
    AllocationItem,
    CashflowBlock,
    CategoryBreakdownItem,
    NetWorthPoint,
)
from app.schemas.monthly_schema import MonthRow

# ---------------------------------------------------------------------------
# Block 1 — Cashflow
# ---------------------------------------------------------------------------


def compute_cashflow(db: Session, from_date: date, to_date: date) -> CashflowBlock:
    """
    Sum income and expense transactions for the period and compute savings rate.

    Savings rate = (income - expense) / income.
    Returns None for savings_rate when income is 0 to avoid a nonsense percentage.
    Transfer rows are excluded — they're internal money movements, not real cashflow.
    """
    rows = (
        db.query(Transaction.kind, func.sum(Transaction.amount_minor).label("total"))
        .filter(
            Transaction.occurred_on >= from_date,
            Transaction.occurred_on <= to_date,
            Transaction.kind.in_(["income", "expense"]),
        )
        .group_by(Transaction.kind)
        .all()
    )

    totals = {row.kind: row.total for row in rows}
    income = totals.get("income", 0)
    expense = totals.get("expense", 0)
    savings_rate = ((income - expense) / income) if income > 0 else None

    return CashflowBlock(
        income_minor=income,
        expense_minor=expense,
        savings_rate=savings_rate,
    )


# ---------------------------------------------------------------------------
# Block 2 — Category breakdown
# ---------------------------------------------------------------------------


def compute_category_breakdown(
    db: Session, from_date: date, to_date: date
) -> list[CategoryBreakdownItem]:
    """
    Group expense transactions by category for the period, ordered by spend descending.

    Returns leaf-level categories (the actual tags on transactions) along with
    their parent name so the frontend can optionally group or annotate them.
    Parent categories that have no direct transactions don't appear — only categories
    that were actually used show up.

    This is the data behind the horizontal bar chart on the dashboard.
    """
    # Join transactions → category. Parent names resolved separately below (no N+1).
    rows = (
        db.query(
            Category.id.label("category_id"),
            Category.name.label("category_name"),
            Category.parent_id.label("parent_id"),
            func.sum(Transaction.amount_minor).label("total_minor"),
        )
        .join(Transaction, Transaction.category_id == Category.id)
        .filter(
            Transaction.occurred_on >= from_date,
            Transaction.occurred_on <= to_date,
            Transaction.kind == "expense",
        )
        .group_by(Category.id, Category.name, Category.parent_id)
        .order_by(func.sum(Transaction.amount_minor).desc())
        .all()
    )

    if not rows:
        return []

    # Resolve parent names in one extra query rather than N+1 calls.
    parent_ids = {row.parent_id for row in rows if row.parent_id is not None}
    parent_names: dict[int, str] = {}
    if parent_ids:
        parents = db.query(Category.id, Category.name).filter(
            Category.id.in_(parent_ids)
        ).all()
        parent_names = {p.id: p.name for p in parents}

    return [
        CategoryBreakdownItem(
            category_id=row.category_id,
            category_name=row.category_name,
            parent_name=parent_names.get(row.parent_id) if row.parent_id else None,
            total_minor=row.total_minor,
        )
        for row in rows
    ]


# ---------------------------------------------------------------------------
# Block 3 — Portfolio allocation
# ---------------------------------------------------------------------------


def compute_allocation(db: Session) -> list[AllocationItem]:
    """
    Group current holdings by instrument.kind and compute each kind's share of
    the total portfolio value.

    Uses current_price_minor on the instrument for valuation (V1 — PF-27 will
    upgrade this to use historical prices). Instruments with no price set are
    excluded from allocation — we can't value what has no price.

    The allocation donut on the dashboard is driven by this output.
    """
    # Aggregate qty per (instrument_id) across all accounts.
    qty_expr = func.sum(
        case(
            (InvestmentTxn.side == "buy", InvestmentTxn.quantity),
            (InvestmentTxn.side == "sell", -InvestmentTxn.quantity),
            else_=0,
        )
    )

    position_rows = (
        db.query(
            InvestmentTxn.instrument_id,
            qty_expr.label("qty"),
        )
        .group_by(InvestmentTxn.instrument_id)
        .having(qty_expr > 0)
        .all()
    )

    if not position_rows:
        return []

    # Load all relevant instruments in one query.
    instrument_ids = [row.instrument_id for row in position_rows]
    instruments = {
        i.id: i
        for i in db.query(Instrument).filter(Instrument.id.in_(instrument_ids)).all()
    }

    # Compute market value per kind.
    kind_totals: dict[str, int] = {}
    for row in position_rows:
        instrument = instruments.get(row.instrument_id)
        if instrument is None or instrument.current_price_minor is None:
            continue  # can't value without a price
        market_value = int(row.qty * instrument.current_price_minor)
        kind_totals[instrument.kind] = kind_totals.get(instrument.kind, 0) + market_value

    if not kind_totals:
        return []

    total_portfolio = sum(kind_totals.values())

    return [
        AllocationItem(
            kind=kind,
            market_value_minor=value,
            pct=round(value / total_portfolio, 4),
        )
        for kind, value in sorted(kind_totals.items(), key=lambda x: x[1], reverse=True)
    ]


# ---------------------------------------------------------------------------
# Block 4 — Net worth series
# ---------------------------------------------------------------------------


def compute_networth_series(
    db: Session, from_date: date, to_date: date
) -> list[NetWorthPoint]:
    """
    Compute net worth at the end of each month in the date range.

    Net worth (month-end M) =
      SUM of account balances up to M
      + SUM of holdings market value at M (using current_price_minor for all months — V1)

    Account balance up to date D:
      opening_balance_minor
      + SUM(income transactions up to D)
      - SUM(expense transactions up to D)
      (transfers are internal — they net to zero across all accounts)

    V1 limitation: current_price_minor is used for all months, not the actual
    historical price. This makes past months slightly wrong but is correct for
    "today". PF-27 will fix this by joining a prices history table.
    """
    month_ends = _month_ends_in_range(from_date, to_date)
    if not month_ends:
        return []

    # Load all accounts once — we need opening balances.
    accounts = db.query(Account).filter(Account.archived == False).all()  # noqa: E712

    # Load all positions (qty per instrument, all-time — not date-filtered).
    # For V1 we use current price for all months so we only need qty, not historical price.
    qty_expr = func.sum(
        case(
            (InvestmentTxn.side == "buy", InvestmentTxn.quantity),
            (InvestmentTxn.side == "sell", -InvestmentTxn.quantity),
            else_=0,
        )
    )
    all_positions = (
        db.query(InvestmentTxn.instrument_id, qty_expr.label("qty"))
        .group_by(InvestmentTxn.instrument_id)
        .having(qty_expr > 0)
        .all()
    )
    instrument_ids = [p.instrument_id for p in all_positions]
    instruments_by_id = {}
    if instrument_ids:
        instruments_by_id = {
            i.id: i
            for i in db.query(Instrument).filter(Instrument.id.in_(instrument_ids)).all()
        }

    # Total holdings market value (same for every month in V1 since price doesn't change).
    holdings_value = sum(
        int(p.qty * instruments_by_id[p.instrument_id].current_price_minor)
        for p in all_positions
        if p.instrument_id in instruments_by_id
        and instruments_by_id[p.instrument_id].current_price_minor is not None
    )

    points = []
    for month_end in month_ends:
        # Cash balance across all accounts up to this month-end.
        cash_balance = sum(acc.opening_balance_minor for acc in accounts)

        txn_rows = (
            db.query(Transaction.kind, func.sum(Transaction.amount_minor).label("total"))
            .filter(
                Transaction.occurred_on <= month_end,
                Transaction.kind.in_(["income", "expense"]),
            )
            .group_by(Transaction.kind)
            .all()
        )
        txn_totals = {row.kind: row.total for row in txn_rows}
        cash_balance += txn_totals.get("income", 0)
        cash_balance -= txn_totals.get("expense", 0)

        networth = cash_balance + holdings_value
        points.append(NetWorthPoint(month=month_end.strftime("%Y-%m"), networth_minor=networth))

    return points


# ---------------------------------------------------------------------------
# Block 5 — Monthly cashflow summary
# ---------------------------------------------------------------------------


def compute_monthly_summary(
    db: Session, from_date: date, to_date: date
) -> list[MonthRow]:
    """
    Return per-month income, expense, and investment totals for the date range,
    along with derived percentages (expense/income, invest/income, savings/income).

    Uses the same UNION ALL pattern from the design doc §4b:
    - Pull income and expense from transactions, grouped by strftime('%Y-%m').
    - Pull buy-side investment outflows from investment_txns, same grouping.
    - Merge the two result sets in Python by year-month key.

    All *_pct fields are None when income is 0 to avoid division by zero — a month
    with zero income but non-zero expenses would produce a meaningless percentage.
    """
    # Aggregate income and expense per month from the transactions table.
    txn_rows = (
        db.query(
            func.strftime("%Y-%m", Transaction.occurred_on).label("ym"),
            Transaction.kind,
            func.sum(Transaction.amount_minor).label("total"),
        )
        .filter(
            Transaction.occurred_on >= from_date,
            Transaction.occurred_on <= to_date,
            Transaction.kind.in_(["income", "expense"]),
        )
        .group_by(
            func.strftime("%Y-%m", Transaction.occurred_on),
            Transaction.kind,
        )
        .all()
    )

    # Aggregate buy-side investment outflows per month from investment_txns.
    # sell and dividend are cash inflows — excluded from "invest_minor" per the spec.
    inv_rows = (
        db.query(
            func.strftime("%Y-%m", InvestmentTxn.occurred_on).label("ym"),
            func.sum(
                InvestmentTxn.quantity * InvestmentTxn.price_minor
                + InvestmentTxn.fee_minor
            ).label("total"),
        )
        .filter(
            InvestmentTxn.occurred_on >= from_date,
            InvestmentTxn.occurred_on <= to_date,
            InvestmentTxn.side == "buy",
        )
        .group_by(func.strftime("%Y-%m", InvestmentTxn.occurred_on))
        .all()
    )

    # Build a dict keyed by ym so we can merge the two result sets.
    # Start with every ym that appears in either result set.
    all_yms: set[str] = (
        {row.ym for row in txn_rows} | {row.ym for row in inv_rows}
    )

    # If there is no data at all, still emit a row for each month in range
    # so the frontend always gets the full month skeleton.
    if not all_yms:
        all_yms = set(_ym_labels_in_range(from_date, to_date))

    income_by_ym: dict[str, int] = {}
    expense_by_ym: dict[str, int] = {}
    for row in txn_rows:
        if row.kind == "income":
            income_by_ym[row.ym] = income_by_ym.get(row.ym, 0) + row.total
        else:
            expense_by_ym[row.ym] = expense_by_ym.get(row.ym, 0) + row.total

    invest_by_ym: dict[str, int] = {row.ym: int(row.total) for row in inv_rows}

    result = []
    for ym in sorted(all_yms):
        income = income_by_ym.get(ym, 0)
        expense = expense_by_ym.get(ym, 0)
        invest = invest_by_ym.get(ym, 0)
        savings = income - expense - invest

        result.append(
            MonthRow(
                ym=ym,
                income_minor=income,
                expense_minor=expense,
                invest_minor=invest,
                expense_pct=round(expense / income, 4) if income > 0 else None,
                invest_pct=round(invest / income, 4) if income > 0 else None,
                savings_minor=savings,
                savings_pct=round(savings / income, 4) if income > 0 else None,
            )
        )

    return result


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _month_ends_in_range(from_date: date, to_date: date) -> list[date]:
    """
    Return the last day of each calendar month between from_date and to_date (inclusive).

    e.g. from_date=2026-02-15, to_date=2026-04-10 → [2026-02-28, 2026-03-31, 2026-04-10]
    The final month uses to_date itself rather than the true month-end, so a partial month
    is represented correctly.
    """
    import calendar

    months = []
    year, month = from_date.year, from_date.month

    while (year, month) <= (to_date.year, to_date.month):
        last_day = calendar.monthrange(year, month)[1]
        month_end = date(year, month, last_day)
        # For the last month, cap at to_date so partial months work correctly.
        months.append(min(month_end, to_date))

        month += 1
        if month > 12:
            month = 1
            year += 1

    return months


def _ym_labels_in_range(from_date: date, to_date: date) -> list[str]:
    """
    Return "YYYY-MM" labels for every month between from_date and to_date.
    Used to ensure the monthly summary always returns a row for every month
    even when there is no data, so the frontend chart has a complete x-axis.
    """
    labels = []
    year, month = from_date.year, from_date.month
    while (year, month) <= (to_date.year, to_date.month):
        labels.append(f"{year:04d}-{month:02d}")
        month += 1
        if month > 12:
            month = 1
            year += 1
    return labels

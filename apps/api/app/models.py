# All SQLAlchemy ORM models for the MVP schema live here.
# Each class maps to one database table — just like @Entity classes in JPA/Hibernate.
# SQLAlchemy 2.0 style uses Mapped[type] + mapped_column() for type-safe column definitions.
#
# Money rule: every monetary value is stored as an integer in PAISE (1 INR = 100 paise).
# So ₹1,500 is stored as 150000. This avoids floating-point rounding bugs entirely.
# Format to ₹ only at the UI layer.

from datetime import date, datetime
from typing import Optional

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """
    The base class that all ORM models inherit from.
    SQLAlchemy uses this to track all the models registered in the app
    and build the metadata (table definitions) needed for migrations.
    Think of it like a JPA EntityManager's persistence unit — all @Entity classes
    that extend this share the same metadata registry.
    """
    pass


class Account(Base):
    """
    Represents a place where money lives — a bank account, cash wallet, broker account, etc.
    Every transaction must belong to an account. It's the "from where" or "to where" for money.

    Accounts are never hard-deleted — they get archived instead (archived=True).
    This keeps historical transactions intact even if you stop using that account.
    """

    __tablename__ = "accounts"

    # Auto-incrementing primary key. Referenced by transactions and investment_txns.
    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    # Human-readable label shown in dropdowns and the transaction table. e.g. "HDFC Savings".
    name: Mapped[str] = mapped_column(String, nullable=False)

    # What kind of account this is. Drives which forms it appears in and how it's
    # treated in net worth. credit_card = liability. broker/wallet = investment forms only.
    type: Mapped[str] = mapped_column(String, nullable=False)  # cash|bank|broker|wallet|credit_card

    # The balance this account started with before you began tracking in the app.
    # Used in net worth math: balance(D) = opening_balance + sum of all transactions up to D.
    # Stored in paise. Defaults to 0 if you're starting fresh.
    opening_balance_minor: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)

    # Soft-delete flag. When True, the account hides from dropdowns but its transactions remain.
    # We never hard-delete accounts that have transactions — the FK constraint blocks it anyway.
    archived: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # When this account was added to the app. Set automatically by the database on insert.
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )


class Category(Base):
    """
    A two-level tag for classifying income and expense transactions.
    e.g. "Food" (parent) → "Groceries" (child), or "Income" (parent) → "Salary" (child).

    The `kind` field (income vs expense) controls which dropdown a category appears in,
    and a child category must always match its parent's kind — enforced in the service layer.

    Deleting a category doesn't delete its transactions — they just become "Uncategorized"
    (category_id goes NULL via ON DELETE SET NULL on the transactions FK).
    """

    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    # Display name shown in chips, charts, and dropdowns. e.g. "Groceries", "Dining Out".
    name: Mapped[str] = mapped_column(String, nullable=False)

    # Points to the parent category row in this same table (self-referential FK).
    # NULL means this is a top-level (parent) category.
    # ON DELETE RESTRICT: you can't delete a parent while it still has children.
    parent_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("categories.id", ondelete="RESTRICT"), nullable=True
    )

    # Whether this category is for income or expense transactions.
    # A transaction's category must match its own kind — e.g. you can't tag an expense
    # with a "Salary" category. Enforced in service layer, not at DB level.
    kind: Mapped[str] = mapped_column(String, nullable=False)  # income|expense

    # Optional hex color for chart slices and chips. e.g. "#3b82f6".
    # If NULL, the UI derives a color from a hash of the name.
    color: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    # Optional Lucide icon name for the UI. e.g. "utensils-crossed". Pure cosmetic.
    icon: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    # Soft-delete: hide from dropdowns without breaking existing transactions.
    archived: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class Transaction(Base):
    """
    The main ledger — every rupee that moves in or out of an account is a row here.
    Covers income, expenses, and transfers between accounts.

    Transfers are stored as a *pair* of rows sharing a note tag like "#transfer:{uuid}".
    One row is "expense-like" on the source account, one is "income-like" on the destination.
    This keeps the math symmetric without needing a separate transfers table.

    The three indexes on occurred_on, category_id, and account_id exist because
    dashboard queries filter on these columns constantly. Without indexes, every
    date-range filter would scan every row in the table.
    """

    __tablename__ = "transactions"

    # These indexes make the most common dashboard queries fast.
    # occurred_on: almost every query filters by date range.
    # category_id: category breakdown chart groups by this.
    # account_id: per-account filters and balance calculations use this.
    __table_args__ = (
        Index("ix_transactions_occurred_on", "occurred_on"),
        Index("ix_transactions_category_id", "category_id"),
        Index("ix_transactions_account_id", "account_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    # Which account this transaction belongs to.
    # ON DELETE RESTRICT: you can't delete an account that still has transactions.
    # Archive the account instead.
    account_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("accounts.id", ondelete="RESTRICT"), nullable=False
    )

    # Which category this transaction belongs to. Optional — transfers have no category.
    # ON DELETE SET NULL: if a category is deleted, transactions become "Uncategorized"
    # rather than getting deleted along with it.
    category_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("categories.id", ondelete="SET NULL"), nullable=True
    )

    # The type of money movement. Drives sign logic and validation rules.
    # income: money coming in (category required, must be income kind).
    # expense: money going out (category required, must be expense kind).
    # transfer: money moving between your own accounts (no category).
    kind: Mapped[str] = mapped_column(String, nullable=False)  # income|expense|transfer

    # The amount in paise (always positive — sign comes from `kind`, not the value).
    # Using BigInteger because the total of all transactions over years could exceed
    # what a regular Integer holds. 64-bit integers in SQLite can hold up to ~92 lakh crore paise.
    amount_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)

    # The economic date — when the expense actually happened, not when it was entered.
    # All time-series charts and period filters group on this column.
    occurred_on: Mapped[date] = mapped_column(Date, nullable=False)

    # Free-text field. Used by the AI categorizer as the primary signal for suggestions.
    # e.g. "Swiggy order", "HDFC ATM withdrawal", "Zara shirt".
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # How this transaction was created. Useful for debugging and analytics
    # (e.g. "how much of my data is from CSV imports vs manual entry?").
    source: Mapped[str] = mapped_column(String, nullable=False, default="manual")  # manual|csv|nl

    # Set automatically by the database when the row is inserted. Read-only after that.
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )

    # Updated automatically every time the row is modified.
    # Useful for cache-busting — if this changes, the dashboard should refetch.
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now()
    )


class Instrument(Base):
    """
    The catalog of investable things — one row per unique security or asset,
    regardless of how many times you've traded it.

    Think of it as the "product catalog" and InvestmentTxn as the "orders".
    An instrument exists independently of your trades — you can track an asset
    even before you've bought it (watchlist use case).

    This separation is why we can compute holdings by GROUP BY on investment_txns
    without duplicating instrument details on every trade row.
    """

    __tablename__ = "instruments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    # The asset class. Drives how the price is fetched (AMFI for mutual_fund,
    # yfinance for stock/etf, CoinGecko for crypto) and how it's grouped in
    # the allocation donut chart.
    kind: Mapped[str] = mapped_column(String, nullable=False)  # mutual_fund|stock|etf|crypto|metal

    # The machine-readable identifier. e.g. "HDFCBANK" for NSE stocks,
    # "BTC" for crypto, "INF090I01239" for an AMFI mutual fund scheme code.
    symbol: Mapped[str] = mapped_column(String, nullable=False)

    # The human-readable name shown in the UI. e.g. "HDFC Bank Ltd".
    name: Mapped[str] = mapped_column(String, nullable=False)

    # The most recently known price per unit, in paise.
    # NULL until the first price is recorded. In V1 this is set manually.
    # In V2 a cron job will keep this updated from AMFI/yfinance/CoinGecko.
    # Holdings valuation = quantity × current_price_minor.
    current_price_minor: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)

    # When current_price_minor was last refreshed. The UI shows a "stale" badge
    # if this is older than a few days, so you know the price might be outdated.
    price_updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # A flexible bag of source-specific identifiers stored as JSON.
    # e.g. {"isin": "INE040A01034", "exchange": "NSE", "amfi_code": "120503"}
    # Keeps the schema clean — we don't need a column for every possible provider field.
    meta: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)


class InvestmentTxn(Base):
    """
    The per-trade ledger for investments. Every buy, sell, and dividend is one row.
    This is separate from transactions because investments have qty/price/fees
    and completely different math (XIRR, cost basis, holdings aggregation).

    Holdings are computed by GROUP BY on this table — there's no separate holdings table.
    qty = SUM(buy quantities) - SUM(sell quantities) per (account, instrument).
    cost_basis = SUM(buy qty × buy price + fees) per (account, instrument).
    """

    __tablename__ = "investment_txns"

    # Composite index on (instrument_id, occurred_on) because the holdings query
    # and XIRR calculation both need to scan trades for a specific instrument ordered by date.
    __table_args__ = (
        Index("ix_investment_txns_instrument_occurred_on", "instrument_id", "occurred_on"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    # Which broker or wallet account holds this position.
    # Must be type broker or wallet — validated in the service layer.
    # ON DELETE RESTRICT: can't delete the account while it has investment trades.
    account_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("accounts.id", ondelete="RESTRICT"), nullable=False
    )

    # What was traded. Links to the instrument catalog.
    # ON DELETE RESTRICT: can't delete an instrument that has trade history.
    instrument_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("instruments.id", ondelete="RESTRICT"), nullable=False
    )

    # Direction of the trade. Drives sign logic for holdings and cashflow math.
    # buy: +qty, cash goes out. sell: -qty, cash comes in. dividend: no qty change, cash comes in.
    side: Mapped[str] = mapped_column(String, nullable=False)  # buy|sell|dividend

    # Number of units transacted. Float because mutual funds trade in fractional units
    # (e.g. 12.347 units of a scheme). For dividends, store quantity=1.
    quantity: Mapped[float] = mapped_column(Float, nullable=False)

    # Price per unit at the time of the trade, in paise.
    # For dividends: store the total dividend amount here (with quantity=1).
    price_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)

    # Total brokerage + STT + GST + any other fees, in paise.
    # Added to cost basis for buys (makes avg cost higher),
    # subtracted from proceeds for sells (makes realized gain lower).
    fee_minor: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)

    # The trade date — critical for XIRR cashflow timing.
    # XIRR needs to know exactly when each rupee went in or came out.
    occurred_on: Mapped[date] = mapped_column(Date, nullable=False)

    # Optional note. e.g. "SIP April", "Rebalance Q2", "Tax-loss harvesting".
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # How this trade was recorded. Same audit trail as transactions.
    source: Mapped[str] = mapped_column(String, nullable=False, default="manual")

    # Insertion timestamp. Read-only after creation.
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )

    # Last-modified timestamp. Auto-updated by SQLAlchemy on every save.
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now()
    )


class Settings(Base):
    """
    A single-row configuration table for global app settings.
    There will always be exactly one row (id=1) — the CheckConstraint enforces this.

    Think of it like a config file stored in the database instead of a .properties file.
    You can only UPDATE it, never INSERT a second row or DELETE the existing one.
    """

    __tablename__ = "settings"

    # The CheckConstraint guarantees only one row can ever exist.
    # If anyone tries to INSERT a row with id != 1, the DB rejects it.
    __table_args__ = (CheckConstraint("id = 1", name="settings_single_row"),)

    # Always 1. The constraint above enforces it. This is the sentinel row pattern.
    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    # Which month the financial year starts. 4 = April (Indian FY), 1 = January (calendar year).
    # This drives the "FY" preset on the global date-range filter and yearly aggregations.
    fy_start_month: Mapped[int] = mapped_column(Integer, nullable=False, default=4)

    # Target allocation percentages per asset class, stored as a JSON dict.
    # e.g. {"equity": 0.65, "debt": 0.20, "gold": 0.10, "crypto": 0.05}
    # Used to compute drift in the allocation donut chart —
    # how far your actual allocation has drifted from your targets.
    # Stored as JSON because it's a small, flexible, user-editable map.
    allocation_targets: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

# Migration 0001 — the very first schema migration.
# This creates the entire 6-table MVP schema from scratch on an empty database.
#
# Run it with:   alembic upgrade head
# Reverse it with: alembic downgrade base
#
# Alembic tracks which migrations have been applied in a special `alembic_version` table.
# That's how it knows whether this migration needs to run or has already run.

"""0001_init_schema

Revision ID: 4fabbb372f99
Revises:
Create Date: 2026-05-01 23:56:50.978670

"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa

from alembic import op

# Alembic uses these IDs to build the migration chain (like a linked list).
# `down_revision = None` means this is the very first migration — nothing comes before it.
revision: str = "4fabbb372f99"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Reusable shorthand for the CURRENT_TIMESTAMP server default.
# SQLite's way of saying "fill this in automatically with the current time on insert".
_CURRENT_TS = sa.text("(CURRENT_TIMESTAMP)")


def upgrade() -> None:
    """
    Create all 6 MVP tables in dependency order — parents before children,
    because a child table's foreign key must point to a table that already exists.

    Order: accounts → categories → instruments → settings
           → investment_txns (needs accounts + instruments)
           → transactions    (needs accounts + categories)

    Then create the 4 indexes after all tables exist.
    """

    # accounts: where money lives. Every transaction references one.
    op.create_table(
        "accounts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("type", sa.String(), nullable=False),
        sa.Column("opening_balance_minor", sa.BigInteger(), nullable=False),
        sa.Column("archived", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=_CURRENT_TS, nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    # categories: two-level tags for income and expense transactions.
    # parent_id is a self-referential FK — a category can point to another category as its parent.
    # ON DELETE RESTRICT: you can't delete a parent while it still has children.
    op.create_table(
        "categories",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("parent_id", sa.Integer(), nullable=True),
        sa.Column("kind", sa.String(), nullable=False),
        sa.Column("color", sa.String(), nullable=True),
        sa.Column("icon", sa.String(), nullable=True),
        sa.Column("archived", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(["parent_id"], ["categories.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )

    # instruments: the catalog of investable assets (stocks, MFs, crypto, etc.).
    # No FK dependencies — it's a standalone catalog table.
    op.create_table(
        "instruments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(), nullable=False),
        sa.Column("symbol", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("current_price_minor", sa.BigInteger(), nullable=True),
        sa.Column("price_updated_at", sa.DateTime(), nullable=True),
        sa.Column("meta", sa.JSON(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )

    # settings: a single-row config table. The CheckConstraint ensures only id=1 can ever exist.
    op.create_table(
        "settings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("fy_start_month", sa.Integer(), nullable=False),
        sa.Column("allocation_targets", sa.JSON(), nullable=False),
        sa.CheckConstraint("id = 1", name="settings_single_row"),
        sa.PrimaryKeyConstraint("id"),
    )

    # investment_txns: per-trade ledger. References both accounts and instruments.
    # ON DELETE RESTRICT on both FKs — you can't delete an account or instrument
    # that still has trade history attached to it.
    op.create_table(
        "investment_txns",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("account_id", sa.Integer(), nullable=False),
        sa.Column("instrument_id", sa.Integer(), nullable=False),
        sa.Column("side", sa.String(), nullable=False),
        sa.Column("quantity", sa.Float(), nullable=False),
        sa.Column("price_minor", sa.BigInteger(), nullable=False),
        sa.Column("fee_minor", sa.BigInteger(), nullable=False),
        sa.Column("occurred_on", sa.Date(), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("source", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=_CURRENT_TS, nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=_CURRENT_TS, nullable=False),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["instrument_id"], ["instruments.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )

    # transactions: the main ledger — income, expenses, and transfers.
    # category_id uses ON DELETE SET NULL: if a category is deleted, transactions
    # become "Uncategorized" instead of getting deleted along with it.
    op.create_table(
        "transactions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("account_id", sa.Integer(), nullable=False),
        sa.Column("category_id", sa.Integer(), nullable=True),
        sa.Column("kind", sa.String(), nullable=False),
        sa.Column("amount_minor", sa.BigInteger(), nullable=False),
        sa.Column("occurred_on", sa.Date(), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("source", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=_CURRENT_TS, nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=_CURRENT_TS, nullable=False),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["category_id"], ["categories.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )

    # Indexes — created after the tables so the columns already exist.
    # These make the most frequent dashboard queries fast instead of doing full table scans.

    # Almost every query filters transactions by date range, so this is the most important one.
    op.create_index("ix_transactions_occurred_on", "transactions", ["occurred_on"])

    # Category breakdown chart groups all transactions by category_id.
    op.create_index("ix_transactions_category_id", "transactions", ["category_id"])

    # Per-account balance calculations and the account filter on the dashboard use this.
    op.create_index("ix_transactions_account_id", "transactions", ["account_id"])

    # Holdings aggregation and XIRR calculation both scan investment_txns
    # for a specific instrument ordered by date — this composite index serves both.
    op.create_index(
        "ix_investment_txns_instrument_occurred_on",
        "investment_txns",
        ["instrument_id", "occurred_on"],
    )


def downgrade() -> None:
    """
    Tear down the schema in reverse dependency order — children before parents.
    You can't drop `accounts` while `transactions` still references it,
    so we drop the leaf tables first and work our way back to the roots.

    Drop indexes before their tables — SQLite handles this automatically,
    but being explicit keeps the intent clear.
    """

    # Drop indexes first.
    op.drop_index("ix_investment_txns_instrument_occurred_on", table_name="investment_txns")
    op.drop_index("ix_transactions_account_id", table_name="transactions")
    op.drop_index("ix_transactions_category_id", table_name="transactions")
    op.drop_index("ix_transactions_occurred_on", table_name="transactions")

    # Drop tables in reverse dependency order (children before parents).
    op.drop_table("transactions")       # references accounts + categories
    op.drop_table("investment_txns")    # references accounts + instruments
    op.drop_table("settings")           # standalone
    op.drop_table("instruments")        # standalone
    op.drop_table("categories")         # self-referential, but no children left now
    op.drop_table("accounts")           # referenced by both txn tables, now safe to drop

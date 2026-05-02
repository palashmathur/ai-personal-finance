# Migration 0002 — seed data.
# Populates the categories table with a starter taxonomy (income + expense tree)
# and inserts the single settings row with sensible defaults.
#
# This migration only writes data — no schema changes.
# It is idempotent: running it twice produces the same result with no errors or duplicates.

"""0002_seed_data

Revision ID: 218bc22cb8fc
Revises: 4fabbb372f99
Create Date: 2026-05-02 13:52:40.370432

"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa

from alembic import op

revision: str = "218bc22cb8fc"
down_revision: Union[str, Sequence[str], None] = "4fabbb372f99"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# All income categories are top-level (no parent). The AI categorizer uses these
# to tag incoming salary, freelance payments, dividends, etc.
INCOME_CATEGORIES = [
    "Salary",
    "Freelance",
    "Bonus",
    "Interest",
    "Dividend",
    "Refund",
    "Gift",
    "Other Income",
]

# Expense categories are a two-level tree: parent → [children].
# Parents are groupings (e.g. "Food"); children are the tags users actually pick
# (e.g. "Groceries"). The AI categorizer and charts work at the child level.
EXPENSE_TREE = {
    "Food": ["Groceries", "Dining Out", "Snacks & Tea"],
    "Transport": ["Fuel", "Cab/Auto", "Public Transit", "Vehicle Maintenance"],
    "Housing": ["Rent", "Maintenance", "Repairs"],
    "Utilities": ["Electricity", "Internet", "Mobile", "Gas", "Water"],
    "Health": ["Doctor", "Pharmacy", "Insurance Premium", "Fitness"],
    "Shopping": ["Clothing", "Electronics", "Home Goods"],
    "Lifestyle": ["Entertainment", "Subscriptions", "Personal Care"],
    "Travel": ["Flights", "Hotels", "Local Transport (Travel)"],
    "Finance": ["Bank Charges", "Taxes", "Loan EMI", "Interest Paid"],
    "Other": ["Misc"],
}


def upgrade() -> None:
    """
    Seed the categories tree and the settings row.

    Idempotency for categories: if any categories already exist, skip all inserts.
    This means running `alembic upgrade head` twice produces no duplicates and no errors.
    Alembic's own version table normally prevents a migration from running twice,
    but the guard here also protects against manual re-runs or test fixtures that
    call upgrade() directly.

    Idempotency for settings: INSERT OR IGNORE relies on SQLite's primary key
    uniqueness — a second INSERT with id=1 is silently dropped.
    """
    bind = op.get_bind()

    # --- Categories ---

    # Skip seeding if the table already has rows. This is the all-or-nothing guard:
    # either we seed the full taxonomy or we leave it untouched.
    existing_count = bind.execute(sa.text("SELECT COUNT(*) FROM categories")).scalar()
    if existing_count > 0:
        # Already seeded — nothing to do.
        return

    # Insert income categories. They are all top-level (parent_id = NULL) and
    # share kind = 'income'. No children — users add their own if needed.
    for name in INCOME_CATEGORIES:
        bind.execute(
            sa.text(
                "INSERT INTO categories (name, kind, parent_id, archived) "
                "VALUES (:name, 'income', NULL, 0)"
            ),
            {"name": name},
        )

    # Insert each expense parent first, capture its auto-assigned id via lastrowid,
    # then insert its children pointing back at that id.
    # We can't hardcode ids because SQLite assigns them — we have to query after each insert.
    for parent_name, children in EXPENSE_TREE.items():
        result = bind.execute(
            sa.text(
                "INSERT INTO categories (name, kind, parent_id, archived) "
                "VALUES (:name, 'expense', NULL, 0)"
            ),
            {"name": parent_name},
        )
        parent_id = result.lastrowid

        for child_name in children:
            bind.execute(
                sa.text(
                    "INSERT INTO categories (name, kind, parent_id, archived) "
                    "VALUES (:name, 'expense', :parent_id, 0)"
                ),
                {"name": child_name, "parent_id": parent_id},
            )

    # --- Settings ---

    # INSERT OR IGNORE: if id=1 already exists (e.g. a previous partial run),
    # SQLite silently skips this insert. Safe to call multiple times.
    bind.execute(
        sa.text(
            "INSERT OR IGNORE INTO settings (id, fy_start_month, allocation_targets) "
            "VALUES (1, 4, '{}')"
        )
    )


def downgrade() -> None:
    """
    Remove all seeded data.

    Delete children before parents because parent_id has ON DELETE RESTRICT —
    SQLite will reject deleting a parent category that still has child rows referencing it.
    Then remove the settings row.

    Note: if a user has added their own categories on top of the seed data,
    this downgrade will remove those too. Downgrading past the seed migration
    intentionally wipes the taxonomy.
    """
    bind = op.get_bind()

    # Children first (they have a non-NULL parent_id pointing to a parent row).
    bind.execute(sa.text("DELETE FROM categories WHERE parent_id IS NOT NULL"))

    # Now safe to delete parents (no children left referencing them).
    bind.execute(sa.text("DELETE FROM categories WHERE parent_id IS NULL"))

    # Remove the single settings row.
    bind.execute(sa.text("DELETE FROM settings WHERE id = 1"))

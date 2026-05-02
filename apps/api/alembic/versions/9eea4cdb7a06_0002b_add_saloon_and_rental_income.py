# Migration 0002b — add two new categories on top of the 0002 seed.
#
# This is the correct pattern when migration 0002 has already been applied
# to a database with real data: never edit the original migration file,
# always add a new one.
#
# Adds:
#   - "Saloon" as a child of "Lifestyle" (expense)
#   - "Rental Income" as a new top-level income category
#
# Both inserts are idempotent — running this migration twice is safe.

"""0002b_add_saloon_and_rental_income

Revision ID: 9eea4cdb7a06
Revises: 218bc22cb8fc
Create Date: 2026-05-02 14:06:55.849865

"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa

from alembic import op

revision: str = "9eea4cdb7a06"
down_revision: Union[str, Sequence[str], None] = "218bc22cb8fc"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Add "Saloon" under "Lifestyle" and "Rental Income" as a new income category.

    Both inserts use a WHERE NOT EXISTS guard because categories have no unique
    constraint on name — INSERT OR IGNORE alone would not help here.
    The guard makes this migration safe to re-run (e.g. in tests that call
    upgrade() directly on a pre-seeded fixture).
    """
    bind = op.get_bind()

    # --- Saloon under Lifestyle ---

    # Look up the Lifestyle parent's id. We can't hardcode it because SQLite
    # assigns ids sequentially and the value depends on insert order in 0002.
    lifestyle = bind.execute(
        sa.text(
            "SELECT id FROM categories WHERE name = 'Lifestyle' AND kind = 'expense'"
        )
    ).fetchone()

    if lifestyle is None:
        # 0002 seed hasn't been applied — this migration cannot proceed safely.
        raise RuntimeError(
            "Parent category 'Lifestyle' not found. "
            "Run migration 0002 (seed data) before applying 0002b."
        )

    lifestyle_id = lifestyle[0]

    # Insert only if "Saloon" doesn't already exist under Lifestyle.
    # Checking by both name and parent_id so a user-created "Saloon" under a
    # different parent doesn't block this insert.
    bind.execute(
        sa.text("""
            INSERT INTO categories (name, kind, parent_id, archived)
            SELECT 'Saloon', 'expense', :parent_id, 0
            WHERE NOT EXISTS (
                SELECT 1 FROM categories
                WHERE name = 'Saloon' AND parent_id = :parent_id
            )
        """),
        {"parent_id": lifestyle_id},
    )

    # --- Rental Income ---

    # Top-level income category — parent_id is NULL.
    # Guard checks name + kind + parent_id IS NULL to target only top-level income rows.
    bind.execute(
        sa.text("""
            INSERT INTO categories (name, kind, parent_id, archived)
            SELECT 'Rental Income', 'income', NULL, 0
            WHERE NOT EXISTS (
                SELECT 1 FROM categories
                WHERE name = 'Rental Income' AND kind = 'income' AND parent_id IS NULL
            )
        """)
    )


def downgrade() -> None:
    """
    Remove exactly the two categories this migration added.

    We delete by name + parent context rather than by id because ids are
    assigned by SQLite and are not stable across different databases.
    """
    bind = op.get_bind()

    # Remove "Saloon" — scoped to expense children only, so a user-created
    # income category called "Saloon" (unlikely but possible) is left untouched.
    bind.execute(
        sa.text(
            "DELETE FROM categories "
            "WHERE name = 'Saloon' AND kind = 'expense' AND parent_id IS NOT NULL"
        )
    )

    # Remove "Rental Income" — top-level income only.
    bind.execute(
        sa.text(
            "DELETE FROM categories "
            "WHERE name = 'Rental Income' AND kind = 'income' AND parent_id IS NULL"
        )
    )

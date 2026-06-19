# Migration 0005 — categorization_rules table.
#
# Stores regex-based rules that map transaction notes to categories.
# The suggest service checks these first (in priority order) before touching
# the LLM — so a rule like "(?i)swiggy" → Dining Out means Claude is never
# called for Swiggy transactions after the first one.

"""0005_categorization_rules

Revision ID: f7a8b9c0d1e2
Revises: 0b8a1225cc01
Create Date: 2026-06-15 00:00:00.000000

"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa

from alembic import op

revision: str = "f7a8b9c0d1e2"
down_revision: Union[str, Sequence[str], None] = "0b8a1225cc01"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create the categorization_rules table."""
    op.create_table(
        "categorization_rules",
        sa.Column("id", sa.Integer, primary_key=True),
        # The regex pattern to test against the transaction field.
        # e.g. "(?i)swiggy" matches any note containing "swiggy" (case-insensitive).
        sa.Column("pattern", sa.Text, nullable=False),
        # Which transaction field to match against. "note" is the only supported value
        # for now — future versions could add "merchant" or "description" fields.
        sa.Column("field", sa.String, nullable=False, server_default="note"),
        # The category to assign when the pattern matches.
        # ON DELETE CASCADE: if a category is deleted, its rules are removed too —
        # no point keeping a rule that points nowhere.
        sa.Column(
            "category_id",
            sa.Integer,
            sa.ForeignKey("categories.id", ondelete="CASCADE"),
            nullable=False,
        ),
        # Higher priority rules are checked first. This lets you put specific rules
        # (e.g. "(?i)swiggy pro") above general ones (e.g. "(?i)swiggy").
        sa.Column("priority", sa.Integer, nullable=False, server_default="0"),
        # When this rule was created. Useful for auditing and sorting in the UI.
        sa.Column(
            "created_at",
            sa.DateTime,
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    # Index on priority so ORDER BY priority DESC doesn't scan the whole table.
    op.create_index(
        "ix_categorization_rules_priority",
        "categorization_rules",
        ["priority"],
    )


def downgrade() -> None:
    """Drop the categorization_rules table."""
    op.drop_index("ix_categorization_rules_priority", table_name="categorization_rules")
    op.drop_table("categorization_rules")

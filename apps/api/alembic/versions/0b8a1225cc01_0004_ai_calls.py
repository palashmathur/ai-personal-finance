# Migration 0004 — ai_calls audit table.
#
# Creates the table that records every Anthropic API call made by the app:
# which feature triggered it, which model, token counts (including cache tokens),
# and latency in milliseconds.
#
# This is the observability backbone for all AI features. Without it, cost
# regressions and latency spikes are invisible until the bill arrives.

"""0004_ai_calls

Revision ID: 0b8a1225cc01
Revises: 9eea4cdb7a06
Create Date: 2026-05-17 19:40:12.286456

"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa

from alembic import op

revision: str = "0b8a1225cc01"
down_revision: Union[str, Sequence[str], None] = "9eea4cdb7a06"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create the ai_calls table."""
    op.create_table(
        "ai_calls",
        sa.Column("id", sa.Integer, primary_key=True),
        # Which feature triggered this call — used to group costs per feature.
        sa.Column("feature", sa.String, nullable=False),
        # Which Claude model was used — different models have different token prices.
        sa.Column("model", sa.String, nullable=False),
        # Standard billing tokens.
        sa.Column("input_tokens", sa.Integer, nullable=False, server_default="0"),
        sa.Column("output_tokens", sa.Integer, nullable=False, server_default="0"),
        # Prompt cache tokens. Both are 0 when caching wasn't active for this call.
        sa.Column("cache_read_tokens", sa.Integer, nullable=False, server_default="0"),
        sa.Column("cache_creation_tokens", sa.Integer, nullable=False, server_default="0"),
        # End-to-end latency in milliseconds.
        sa.Column("latency_ms", sa.Integer, nullable=False),
        # Timestamp for date-range filtering in the usage endpoint.
        sa.Column(
            "created_at",
            sa.DateTime,
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    # Index on created_at so the usage endpoint (which always filters by date range)
    # doesn't scan the whole table as call volume grows.
    op.create_index("ix_ai_calls_created_at", "ai_calls", ["created_at"])


def downgrade() -> None:
    """Drop the ai_calls table."""
    op.drop_index("ix_ai_calls_created_at", table_name="ai_calls")
    op.drop_table("ai_calls")

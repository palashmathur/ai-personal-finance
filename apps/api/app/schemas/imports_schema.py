# Pydantic schemas for the CSV Import endpoints.
# The import flow is two steps:
#   1. Preview — parse the CSV and return what will be inserted (nothing written yet).
#   2. Confirm — send the reviewed rows back with account_id + category_id, bulk-insert.
#
# This two-step pattern lets the user review and correct before anything hits the DB.

from datetime import date
from typing import Optional

from pydantic import BaseModel, ConfigDict


class PreviewRow(BaseModel):
    """
    One parsed row returned by the preview endpoint.
    Nothing is written to the DB at this stage — this is just the parsed result
    so the user can review it, assign an account, and adjust categories before confirming.
    """

    occurred_on: date
    amount_minor: int
    # "income" for credit rows, "expense" for debit rows.
    kind: str
    note: str
    # Set when the `category` column in the CSV matches a category name in the DB.
    # None when the column is blank or no match is found — user picks manually.
    suggested_category_id: Optional[int]


class ConfirmRow(BaseModel):
    """
    One row in the confirm request body.
    account_id is NOT here — it is a single top-level field on ConfirmRequest,
    applied to all rows. The user picks the account once, not per row.
    """

    occurred_on: date
    amount_minor: int
    kind: str
    note: str
    # Optional — user may leave some rows uncategorized.
    category_id: Optional[int] = None


class ConfirmRequest(BaseModel):
    """
    Full confirm request body.
    account_id is supplied once here and stamped on every row during insert —
    the user selects the account from a single dropdown, not per row.
    """

    # Which account all these transactions belong to.
    account_id: int
    rows: list[ConfirmRow]


class ImportResult(BaseModel):
    """Response from the confirm endpoint — how many rows were inserted vs skipped."""

    # Rows that were newly inserted into the transactions table.
    inserted: int
    # Rows that already existed (matched on amount_minor + occurred_on + note) and were skipped.
    skipped: int


class ImportPreviewResponse(BaseModel):
    """
    Full response from the preview endpoint.
    Wraps the list of parsed rows alongside a summary so the UI can show
    "X rows parsed, Y will be skipped (already exist)" before the user confirms.
    """

    model_config = ConfigDict(from_attributes=True)

    rows: list[PreviewRow]
    total: int

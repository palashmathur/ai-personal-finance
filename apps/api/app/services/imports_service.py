# Business logic for the CSV Import feature.
# Two functions:
#   parse_csv()    — reads the canonical CSV format and returns PreviewRows (no DB writes).
#   confirm_import() — bulk-inserts the confirmed rows, skipping duplicates.
#
# Canonical CSV format (5 columns, header row required):
#   date       YYYY-MM-DD
#   amount     positive decimal e.g. 450.00
#   type       "debit" (expense) or "credit" (income)
#   narration  free text
#   category   optional category name hint (blank = no suggestion)

import csv
import io
from datetime import datetime
from typing import Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models import Category, Transaction
from app.schemas.imports_schema import ConfirmRow, ImportResult, PreviewRow

# The exact column names the parser expects (case-sensitive).
_REQUIRED_COLS = {"date", "amount", "type", "narration"}
_ALL_COLS = {"date", "amount", "type", "narration", "category"}
_VALID_TYPES = {"debit", "credit"}


def parse_csv(file_bytes: bytes, db: Session) -> list[PreviewRow]:
    """
    Parse a CSV file in the canonical format and return a list of preview rows.

    No data is written to the DB here — this is a pure read + parse step.
    The db session is only used to look up suggested_category_id by name.

    Raises 422 for:
    - Missing required columns
    - Blank date, amount, type, or narration on any row
    - date not in YYYY-MM-DD format
    - amount not a positive number
    - type not "debit" or "credit"
    """
    try:
        text = file_bytes.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(
            status_code=422,
            detail="CSV file must be UTF-8 encoded.",
        )

    reader = csv.DictReader(io.StringIO(text))

    # Validate that required columns exist in the header.
    if reader.fieldnames is None:
        raise HTTPException(status_code=422, detail="CSV file is empty or has no header row.")

    actual_cols = {col.strip().lower() for col in reader.fieldnames}
    missing = _REQUIRED_COLS - actual_cols
    if missing:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Missing required column(s): {', '.join(sorted(missing))}. "
                f"Expected columns: date, amount, type, narration, category (optional)."
            ),
        )

    # Pre-load all categories for the suggestion lookup.
    # The category column must contain a category name (e.g. "Food", "Salary").
    # Matching is case-insensitive. Numeric values are not treated as IDs.
    categories = db.query(Category).filter(Category.archived == False).all()  # noqa: E712
    # Name lookup: (lowercase name, kind) → id
    category_lookup: dict[tuple[str, str], int] = {
        (cat.name.lower(), cat.kind): cat.id for cat in categories
    }

    rows: list[PreviewRow] = []
    for line_num, raw_row in enumerate(reader, start=2):
        # Normalise keys to lowercase and strip whitespace from values.
        row = {k.strip().lower(): (v.strip() if v else "") for k, v in raw_row.items()}

        # Skip completely empty rows (e.g. trailing blank lines in the file).
        if not any(row.values()):
            continue

        # Validate each required field on this row.
        _validate_row(row, line_num)

        occurred_on = datetime.strptime(row["date"], "%d/%m/%Y").date()
        amount_minor = int(round(float(row["amount"]) * 100))
        kind = "expense" if row["type"] == "debit" else "income"
        note = row["narration"]

        # Try to match the optional category hint to a real category by name.
        # The category's kind must also match the row kind so we never suggest
        # a Salary (income) category on a debit (expense) row.
        suggested_category_id: Optional[int] = None
        category_hint = row.get("category", "").strip()
        if category_hint:
            suggested_category_id = category_lookup.get((category_hint.lower(), kind))

        rows.append(
            PreviewRow(
                occurred_on=occurred_on,
                amount_minor=amount_minor,
                kind=kind,
                note=note,
                suggested_category_id=suggested_category_id,
            )
        )

    if not rows:
        raise HTTPException(
            status_code=422,
            detail="CSV contains no data rows after the header.",
        )

    return rows


def confirm_import(
    db: Session, account_id: int, rows: list[ConfirmRow]
) -> ImportResult:
    """
    Bulk-insert the confirmed rows into the transactions table.

    account_id is a single value applied to all rows — the user picks the account
    once from a dropdown rather than specifying it per row.

    Duplicate detection: a row is skipped if an existing transaction matches
    on all three of (amount_minor, occurred_on, note). This prevents re-importing
    the same CSV statement twice from creating duplicate entries.

    All inserts happen in a single DB transaction — if anything fails, nothing
    is committed (all-or-nothing).
    """
    inserted = 0
    skipped = 0

    # Load the set of existing (amount_minor, occurred_on, note) tuples in one query
    # rather than checking each row individually — much faster for large imports.
    existing = {
        (t.amount_minor, t.occurred_on, t.note)
        for t in db.query(
            Transaction.amount_minor,
            Transaction.occurred_on,
            Transaction.note,
        ).all()
    }

    new_txns = []
    for row in rows:
        key = (row.amount_minor, row.occurred_on, row.note)
        if key in existing:
            skipped += 1
            continue

        new_txns.append(
            Transaction(
                account_id=account_id,
                category_id=row.category_id,
                kind=row.kind,
                amount_minor=row.amount_minor,
                occurred_on=row.occurred_on,
                note=row.note,
                source="csv",
            )
        )
        # Add to existing set so duplicate rows within the same upload are also caught.
        existing.add(key)
        inserted += 1

    if new_txns:
        db.bulk_save_objects(new_txns)
        db.commit()

    return ImportResult(inserted=inserted, skipped=skipped)


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _validate_row(row: dict, line_num: int) -> None:
    """
    Validate a single CSV row. Raises 422 with the line number on any failure
    so the user knows exactly which row is broken.
    """
    # Required fields must not be blank.
    for field in ("date", "amount", "type", "narration"):
        if not row.get(field):
            raise HTTPException(
                status_code=422,
                detail=f"Row {line_num}: '{field}' is required and cannot be blank.",
            )

    # Date must be DD/MM/YYYY.
    try:
        datetime.strptime(row["date"], "%d/%m/%Y")
    except ValueError:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Row {line_num}: date '{row['date']}' is not in DD/MM/YYYY format."
            ),
        )

    # Amount must be a positive number.
    try:
        amount = float(row["amount"])
        if amount <= 0:
            raise ValueError
    except ValueError:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Row {line_num}: amount '{row['amount']}' must be a positive number."
            ),
        )

    # Type must be debit or credit.
    if row["type"] not in _VALID_TYPES:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Row {line_num}: type '{row['type']}' is invalid. "
                f"Must be 'debit' or 'credit'."
            ),
        )

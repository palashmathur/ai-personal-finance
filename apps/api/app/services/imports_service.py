# Business logic for the CSV Import feature.
# Two functions:
#   parse_csv()    — reads the canonical CSV format, categorizes rows, returns PreviewRows.
#   confirm_import() — bulk-inserts the confirmed rows, skipping duplicates.
#
# Canonical CSV format (5 columns, header row required):
#   date       DD/MM/YYYY
#   amount     positive decimal e.g. 450.00
#   type       "debit" (expense) or "credit" (income)
#   narration  free text
#   category   optional category name hint (blank = auto-categorize via rules/LLM)
#
# Categorization happens inside parse_csv so the frontend only needs one API call:
#   1. Rows whose CSV `category` column matches a DB category name → source="csv" (no AI needed)
#   2. Remaining rows → passed to suggest_batch once for the whole file
#      (rules checked first in one pass, LLM only for what's left)

import csv
import io
from datetime import datetime
from typing import Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models import Category, Transaction
from app.schemas.categorize_schema import CategorizeSuggestRequest
from app.schemas.imports_schema import ConfirmRow, ImportResult, PreviewRow
from app.services import categorize as categorize_svc

# The exact column names the parser expects (case-sensitive).
_REQUIRED_COLS = {"date", "amount", "type", "narration"}
_VALID_TYPES = {"debit", "credit"}


def parse_csv(file_bytes: bytes, db: Session) -> list[PreviewRow]:
    """
    Parse a CSV file in the canonical format and return a list of preview rows
    with categories already resolved — no second API call needed by the frontend.

    Categorization is a two-pass process done entirely on the backend:
      Pass 1 — rows whose CSV category column matches a known category name: resolved instantly.
      Pass 2 — all remaining rows are sent to suggest_batch in one shot:
                rules are checked first (free, instant), LLM only for what slips through.

    The optimization: a 200-row CSV where 50 rows already have category names only
    sends 150 rows to suggest_batch, and within those 150 only the rule misses hit the LLM.

    No data is written to the DB here — this is purely parse + categorize.

    Raises 422 for:
    - Missing required columns
    - Blank date, amount, type, or narration on any row
    - date not in DD/MM/YYYY format
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

    # Load all active categories once — used for both CSV name matching and suggest_batch.
    categories = db.query(Category).filter(Category.archived == False).all()  # noqa: E712
    by_id: dict[int, Category] = {c.id: c for c in categories}
    # (lowercase name, kind) → id — so "food" debit only matches an expense category named "Food"
    category_lookup: dict[tuple[str, str], int] = {
        (c.name.lower(), c.kind): c.id for c in categories
    }

    # Parse all rows into intermediate dicts first (no PreviewRow yet — category data comes later).
    parsed: list[dict] = []
    for line_num, raw_row in enumerate(reader, start=2):
        row = {k.strip().lower(): (v.strip() if v else "") for k, v in raw_row.items()}

        if not any(row.values()):
            continue  # skip trailing blank lines

        _validate_row(row, line_num)

        occurred_on = datetime.strptime(row["date"], "%d/%m/%Y").date()
        amount_minor = int(round(float(row["amount"]) * 100))
        kind = "expense" if row["type"] == "debit" else "income"
        note = row["narration"]

        # Try to match the CSV category hint to a real category by name + kind.
        # Kind must match so a "Salary" income category is never suggested on a debit row.
        category_id: Optional[int] = None
        category_name: Optional[str] = None
        category_source: Optional[str] = None
        category_hint = row.get("category", "").strip()
        if category_hint:
            matched_id = category_lookup.get((category_hint.lower(), kind))
            if matched_id is not None:
                category_id = matched_id
                category_name = by_id[matched_id].name  # use DB name, not the CSV hint
                category_source = "csv"

        parsed.append({
            "occurred_on": occurred_on,
            "amount_minor": amount_minor,
            "kind": kind,
            "note": note,
            "category_id": category_id,
            "category_name": category_name,
            "category_source": category_source,
        })

    if not parsed:
        raise HTTPException(
            status_code=422,
            detail="CSV contains no data rows after the header.",
        )

    # Pass 2 — categorize rows that didn't match a CSV category name.
    # Collect their indices so we can stitch results back in order after the batch call.
    uncategorized = [i for i, p in enumerate(parsed) if p["category_id"] is None]
    if uncategorized:
        requests = [
            CategorizeSuggestRequest(
                note=parsed[i]["note"],
                amount_minor=parsed[i]["amount_minor"],
            )
            for i in uncategorized
        ]
        suggestions = categorize_svc.suggest_batch(requests, db)

        for idx, suggestion in zip(uncategorized, suggestions):
            if suggestion.category_id is not None:
                parsed[idx]["category_id"] = suggestion.category_id
                parsed[idx]["category_name"] = suggestion.category_name
                parsed[idx]["category_source"] = suggestion.source

    return [PreviewRow(**p) for p in parsed]


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
    for field in ("date", "amount", "type", "narration"):
        if not row.get(field):
            raise HTTPException(
                status_code=422,
                detail=f"Row {line_num}: '{field}' is required and cannot be blank.",
            )

    try:
        datetime.strptime(row["date"], "%d/%m/%Y")
    except ValueError:
        raise HTTPException(
            status_code=422,
            detail=f"Row {line_num}: date '{row['date']}' is not in DD/MM/YYYY format.",
        )

    try:
        amount = float(row["amount"])
        if amount <= 0:
            raise ValueError
    except ValueError:
        raise HTTPException(
            status_code=422,
            detail=f"Row {line_num}: amount '{row['amount']}' must be a positive number.",
        )

    if row["type"] not in _VALID_TYPES:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Row {line_num}: type '{row['type']}' is invalid. "
                f"Must be 'debit' or 'credit'."
            ),
        )

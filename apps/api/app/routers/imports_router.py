# FastAPI router for the CSV Import endpoints.
# Two endpoints:
#   POST /api/imports/transactions/preview  — parse and validate, return rows, write nothing
#   POST /api/imports/transactions/confirm  — bulk-insert the reviewed rows

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.imports_schema import (
    ConfirmRequest,
    ImportPreviewResponse,
    ImportResult,
)
from app.services import imports_service

router = APIRouter(prefix="/api/imports", tags=["imports"])

# Maximum file size accepted: 5 MB. A full year of daily transactions is well under 1 MB.
_MAX_FILE_SIZE = 5 * 1024 * 1024


@router.post("/transactions/preview", response_model=ImportPreviewResponse)
async def preview_import(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """
    Parse a CSV file and return the rows that would be inserted — without writing anything.

    The CSV must follow the canonical format:
      date (YYYY-MM-DD), amount (positive decimal), type (debit|credit),
      narration (text), category (optional name hint)

    Returns 422 if the file is malformed, missing required columns, or has invalid values.
    Use this response to review and assign account_id / category_id before calling confirm.
    """
    if file.content_type not in ("text/csv", "application/vnd.ms-excel", "text/plain"):
        raise HTTPException(
            status_code=422,
            detail=(
                f"Unsupported file type '{file.content_type}'. "
                f"Please upload a .csv file."
            ),
        )

    file_bytes = await file.read()

    if len(file_bytes) > _MAX_FILE_SIZE:
        raise HTTPException(
            status_code=422,
            detail="File exceeds the 5 MB size limit.",
        )

    rows = imports_service.parse_csv(file_bytes, db)
    return ImportPreviewResponse(rows=rows, total=len(rows))


@router.post("/transactions/confirm", response_model=ImportResult)
def confirm_import(
    body: ConfirmRequest,
    db: Session = Depends(get_db),
):
    """
    Bulk-insert the confirmed rows into the transactions table.

    account_id is a single top-level field — the user picks the account once
    and it is applied to all rows. Send back the rows from the preview response
    with category_id filled in per row (optional — can be null).

    Rows that already exist in the DB (matched on amount_minor + occurred_on + note)
    are silently skipped. Returns the count of inserted and skipped rows.
    """
    if not body.rows:
        raise HTTPException(
            status_code=422,
            detail="Request body must contain at least one row.",
        )

    return imports_service.confirm_import(db, body.account_id, body.rows)

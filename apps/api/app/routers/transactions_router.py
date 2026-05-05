# FastAPI router for the Transactions resource.
# This is the HTTP layer only — it validates query parameters, delegates to the service,
# and returns the response. No business logic lives here.
# Think of it as the @RestController in Spring Boot: it wires HTTP to the @Service layer.

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.transactions_schema import (
    TransactionCreate,
    TransactionResponse,
    TransactionUpdate,
)
from app.services import transactions_service

router = APIRouter(prefix="/api/transactions", tags=["transactions"])


@router.get("", response_model=list[TransactionResponse])
def list_transactions(
    # `from` is a Python keyword, so we use alias="from" and name the variable from_date.
    from_date: Optional[date] = Query(default=None, alias="from"),
    to_date: Optional[date] = Query(default=None, alias="to"),
    account_id: Optional[int] = None,
    category_id: Optional[int] = None,
    kind: Optional[str] = None,
    q: Optional[str] = None,
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    """
    List transactions with optional filters. Ordered by occurred_on DESC, created_at DESC.

    - `from` / `to`: filter by economic date range (both inclusive).
    - `account_id`: only transactions from this account.
    - `category_id`: only transactions with this category.
    - `kind`: income | expense | transfer.
    - `q`: case-insensitive substring match on the note field.
    - `limit` / `offset`: pagination (default 50 per page, max 500).
    """
    return transactions_service.list_transactions(
        db,
        from_date=from_date,
        to_date=to_date,
        account_id=account_id,
        category_id=category_id,
        kind=kind,
        q=q,
        limit=limit,
        offset=offset,
    )


@router.post("", response_model=list[TransactionResponse], status_code=status.HTTP_201_CREATED)
def create_transaction(data: TransactionCreate, db: Session = Depends(get_db)):
    """
    Create a transaction.

    For income/expense: returns a list with 1 item.
    For transfer: returns a list with 2 items (debit row first, credit row second).

    The response is always a list so the caller doesn't need to check the kind
    to know whether to unpack one or two items.
    """
    return transactions_service.create_transaction(db, data)


@router.patch("/{txn_id}", response_model=list[TransactionResponse])
def update_transaction(txn_id: int, data: TransactionUpdate, db: Session = Depends(get_db)):
    """
    Partially update a transaction. For transfer rows, updates both halves atomically.

    Returns a list with the same shape as create: 1 item for regular transactions,
    2 items for transfer rows (the row you updated + its partner).
    """
    return transactions_service.update_transaction(db, txn_id, data)


@router.delete("/{txn_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_transaction(txn_id: int, db: Session = Depends(get_db)):
    """
    Delete a transaction. For transfer rows, deletes both halves in one atomic operation.
    Returns 204 No Content on success.
    """
    transactions_service.delete_transaction(db, txn_id)

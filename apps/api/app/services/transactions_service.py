# Business logic for the Transactions resource.
# Pure functions — no FastAPI imports, no Depends. Routers call these; these don't know about HTTP.
# Think of this as the @Service layer in Spring Boot: all validation, DB writes, and domain rules live here.
#
# The trickiest concept here is transfer pairing: when the user creates a transfer,
# we insert two DB rows (one expense-like debit, one income-like credit) linked by a
# shared UUID tag embedded in the note field — e.g. "#transfer:abc-123...".
# PATCH and DELETE on either half must find the partner and act on both atomically.

import re
import uuid
from datetime import date
from typing import Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models import Account, Category, Transaction
from app.schemas.transactions_schema import TransactionCreate, TransactionKind, TransactionUpdate

# Regex to extract the UUID from a transfer note tag like "#transfer:abc123-..."
_TRANSFER_TAG_RE = re.compile(r"#transfer:([a-f0-9\-]+)")


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _get_active_account_or_404(db: Session, account_id: int, label: str = "Account") -> Account:
    """
    Fetch an account by ID and verify it's active (not archived).

    404 if the account doesn't exist at all.
    409 Conflict if it exists but is archived — the account is in a conflicting state
    for this operation (archived accounts can't accept new transactions).
    """
    account = db.get(Account, account_id)
    if account is None:
        raise HTTPException(status_code=404, detail=f"{label} {account_id} not found.")
    if account.archived:
        raise HTTPException(
            status_code=409,
            detail=f"{label} '{account.name}' is archived and cannot accept new transactions.",
        )
    return account


def _get_category_and_validate_kind(db: Session, category_id: int, txn_kind: str) -> Category:
    """
    Fetch a category by ID and verify its kind matches the transaction kind.

    404 if the category doesn't exist.
    422 if the kinds don't match — e.g. tagging an expense transaction with a Salary category.
    We return 422 (not 409) because this is a semantic validation failure, not a resource conflict.
    """
    category = db.get(Category, category_id)
    if category is None:
        raise HTTPException(status_code=404, detail=f"Category {category_id} not found.")
    if category.kind != txn_kind:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Kind mismatch: transaction kind is '{txn_kind}' but "
                f"category '{category.name}' is '{category.kind}'. "
                f"Use a {txn_kind} category for {txn_kind} transactions."
            ),
        )
    return category


def _find_transfer_partner(db: Session, txn: Transaction) -> Optional[Transaction]:
    """
    Given one half of a transfer pair, find the other half.

    Transfers are linked by a shared UUID tag embedded in both rows' note field:
    e.g. "Moving savings #transfer:abc-123". We extract the UUID with a regex,
    then query for the sibling row that contains the same tag but has a different id.

    Returns None if this transaction has no transfer tag (i.e. it's not a transfer row).
    """
    if not txn.note:
        return None
    match = _TRANSFER_TAG_RE.search(txn.note)
    if match is None:
        return None
    transfer_tag = f"#transfer:{match.group(1)}"
    return (
        db.query(Transaction)
        .filter(
            Transaction.note.like(f"%{transfer_tag}%"),
            Transaction.id != txn.id,
        )
        .first()
    )


def _attach_display_names(db: Session, txn: Transaction) -> Transaction:
    """
    Attach account_name and category_name as transient Python attributes on the ORM object.

    Pydantic's from_attributes=True reads from Python object attributes — not just DB columns.
    So we can add these computed display fields directly onto the ORM instance before
    Pydantic serializes it, without needing to change the DB schema or use a JOIN.
    This is the same technique used for category.children in categories_service.py.
    """
    account = db.get(Account, txn.account_id)
    txn.account_name = account.name if account else ""
    if txn.category_id is not None:
        cat = db.get(Category, txn.category_id)
        txn.category_name = cat.name if cat else None
    else:
        txn.category_name = None
    return txn


def get_transaction_or_404(db: Session, txn_id: int) -> Transaction:
    """Fetch a transaction by ID or raise 404. Used by update and delete."""
    txn = db.get(Transaction, txn_id)
    if txn is None:
        raise HTTPException(status_code=404, detail=f"Transaction {txn_id} not found.")
    return txn


# ---------------------------------------------------------------------------
# List
# ---------------------------------------------------------------------------


def list_transactions(
    db: Session,
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
    account_id: Optional[int] = None,
    category_id: Optional[int] = None,
    kind: Optional[str] = None,
    q: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> list[Transaction]:
    """
    List transactions with optional filters.

    Filters are additive (AND logic): passing account_id AND kind narrows to
    transactions that match both. All filters are optional — omitting them returns all rows.

    `q` does a case-insensitive substring match on the note field (ilike = SQL LIKE with case folding).
    This is the primary search mechanism before we add FTS5 in a later ticket.

    Orders by occurred_on DESC, created_at DESC so the most recent entries appear first.
    When two transactions happened on the same date, the one entered later comes first.
    """
    query = db.query(Transaction)

    if from_date is not None:
        query = query.filter(Transaction.occurred_on >= from_date)
    if to_date is not None:
        query = query.filter(Transaction.occurred_on <= to_date)
    if account_id is not None:
        query = query.filter(Transaction.account_id == account_id)
    if category_id is not None:
        query = query.filter(Transaction.category_id == category_id)
    if kind is not None:
        query = query.filter(Transaction.kind == kind)
    if q is not None:
        query = query.filter(Transaction.note.ilike(f"%{q}%"))

    txns = (
        query
        .order_by(Transaction.occurred_on.desc(), Transaction.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    for txn in txns:
        _attach_display_names(db, txn)
    return txns


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------


def _validate_create_fields(data: TransactionCreate) -> None:
    """
    Enforce the cross-field rules that depend on `kind`.

    We do this in the service (raising HTTPException) rather than in a Pydantic model_validator
    because model_validator errors don't reliably flow through FastAPI's custom exception handler
    in all version combinations — they can surface as 500s instead of 422s.
    """
    if data.kind == TransactionKind.transfer:
        if data.from_account_id is None or data.to_account_id is None:
            raise HTTPException(
                status_code=422,
                detail="Transfer requires both from_account_id and to_account_id.",
            )
        if data.from_account_id == data.to_account_id:
            raise HTTPException(
                status_code=422,
                detail="from_account_id and to_account_id must be different accounts.",
            )
        if data.account_id is not None:
            raise HTTPException(
                status_code=422,
                detail="Transfer must not include account_id — use from_account_id and to_account_id.",
            )
        if data.category_id is not None:
            raise HTTPException(
                status_code=422,
                detail="Transfer transactions cannot have a category_id.",
            )
    else:
        # income or expense
        if data.account_id is None:
            raise HTTPException(
                status_code=422,
                detail=f"{data.kind.value} transaction requires account_id.",
            )
        if data.category_id is None:
            raise HTTPException(
                status_code=422,
                detail=f"{data.kind.value} transaction requires category_id.",
            )
        if data.from_account_id is not None or data.to_account_id is not None:
            raise HTTPException(
                status_code=422,
                detail=f"{data.kind.value} transaction must not include from_account_id or to_account_id.",
            )


def create_transaction(db: Session, data: TransactionCreate) -> list[Transaction]:
    """
    Create a transaction (or a transfer pair) and return all inserted rows.

    Always returns a list:
    - income/expense → list with 1 item
    - transfer → list with 2 items (debit row first, credit row second)

    Consistent list shape means the router and frontend never need to check the kind
    to know whether to unpack one or two items.
    """
    _validate_create_fields(data)
    if data.kind == TransactionKind.transfer:
        return _create_transfer(db, data)
    return [_create_income_expense(db, data)]


def _create_income_expense(db: Session, data: TransactionCreate) -> Transaction:
    """
    Insert a single income or expense transaction.
    Validates account existence + activity, and category kind match, before writing.
    """
    _get_active_account_or_404(db, data.account_id)
    _get_category_and_validate_kind(db, data.category_id, data.kind.value)

    txn = Transaction(
        account_id=data.account_id,
        category_id=data.category_id,
        kind=data.kind.value,
        amount_minor=data.amount_minor,
        occurred_on=data.occurred_on,
        note=data.note,
        source=data.source.value,
    )
    db.add(txn)
    db.commit()
    db.refresh(txn)
    _attach_display_names(db, txn)
    return txn


def _create_transfer(db: Session, data: TransactionCreate) -> list[Transaction]:
    """
    Insert two rows for a transfer — one debit on the source account, one credit on the destination.

    Both rows share a UUID tag embedded in their note field (e.g. "#transfer:abc-123...").
    This UUID is the link that lets PATCH and DELETE find the partner row later.

    The user's own note text (if any) is preserved alongside the tag:
    e.g. "Moving savings #transfer:abc-123..."

    A single db.commit() inserts both rows atomically — either both succeed or neither does.
    """
    _get_active_account_or_404(db, data.from_account_id, label="Source account")
    _get_active_account_or_404(db, data.to_account_id, label="Destination account")

    transfer_uuid = str(uuid.uuid4())
    transfer_tag = f"#transfer:{transfer_uuid}"
    # Preserve the user's note alongside the system tag so the note field remains readable.
    note_with_tag = f"{data.note} {transfer_tag}" if data.note else transfer_tag

    # Debit row: the account losing money (source). Kind=expense so dashboard math subtracts it.
    debit_row = Transaction(
        account_id=data.from_account_id,
        category_id=None,
        kind="expense",
        amount_minor=data.amount_minor,
        occurred_on=data.occurred_on,
        note=note_with_tag,
        source=data.source.value,
    )
    # Credit row: the account gaining money (destination). Kind=income so dashboard math adds it.
    credit_row = Transaction(
        account_id=data.to_account_id,
        category_id=None,
        kind="income",
        amount_minor=data.amount_minor,
        occurred_on=data.occurred_on,
        note=note_with_tag,
        source=data.source.value,
    )

    db.add(debit_row)
    db.add(credit_row)
    db.commit()  # single commit = both rows inserted atomically
    db.refresh(debit_row)
    db.refresh(credit_row)

    for row in [debit_row, credit_row]:
        _attach_display_names(db, row)
    return [debit_row, credit_row]


# ---------------------------------------------------------------------------
# Update
# ---------------------------------------------------------------------------


def update_transaction(db: Session, txn_id: int, data: TransactionUpdate) -> list[Transaction]:
    """
    Update a transaction and return all affected rows.

    Like create, always returns a list — 1 item for a regular transaction, 2 for a transfer.
    For transfer rows, fields that logically apply to the whole transfer (amount, date, note)
    are updated on both halves in one commit so they stay in sync.
    """
    txn = get_transaction_or_404(db, txn_id)
    updates = data.model_dump(exclude_unset=True)

    # Detect whether this is a transfer row by looking for the transfer tag in the note.
    partner = _find_transfer_partner(db, txn)

    if partner is not None:
        return _update_transfer(db, txn, partner, updates)
    return [_update_single(db, txn, updates)]


def _update_single(db: Session, txn: Transaction, updates: dict) -> Transaction:
    """
    Apply a partial update to a regular (non-transfer) transaction.
    Re-validates category kind if category_id is being changed.
    """
    if "category_id" in updates and updates["category_id"] is not None:
        _get_category_and_validate_kind(db, updates["category_id"], txn.kind)

    for field, value in updates.items():
        setattr(txn, field, value)

    db.commit()
    db.refresh(txn)
    _attach_display_names(db, txn)
    return txn


def _update_transfer(
    db: Session, txn: Transaction, partner: Transaction, updates: dict
) -> list[Transaction]:
    """
    Apply a partial update to a transfer pair.

    Fields that are shared across both halves (amount, date) are propagated to both rows.
    The note update preserves the #transfer:{uuid} tag so the pairing link is never broken.
    Account changes are routed to the correct half:
    - from_account_id → debit row (the one with kind=expense)
    - to_account_id   → credit row (the one with kind=income)

    One commit covers both rows — either both update or neither does.
    """
    if "category_id" in updates and updates["category_id"] is not None:
        raise HTTPException(
            status_code=422,
            detail="Transfer transactions cannot have a category_id.",
        )

    # Fields that apply identically to both halves of the transfer.
    shared_fields = {"amount_minor", "occurred_on"}
    for field in shared_fields:
        if field in updates:
            setattr(txn, field, updates[field])
            setattr(partner, field, updates[field])

    # Note update: preserve the #transfer:{uuid} tag in both rows so the link is never lost.
    if "note" in updates:
        match = _TRANSFER_TAG_RE.search(txn.note or "")
        if match:
            transfer_tag = f"#transfer:{match.group(1)}"
            user_note = updates["note"]
            new_note = f"{user_note} {transfer_tag}" if user_note else transfer_tag
        else:
            # No tag found (shouldn't happen for a valid transfer row, but handle gracefully)
            new_note = updates["note"]
        txn.note = new_note
        partner.note = new_note

    # Account reassignment: debit row is always kind=expense, credit row is always kind=income.
    # This invariant is established at create time and must be preserved.
    debit = txn if txn.kind == "expense" else partner
    credit = txn if txn.kind == "income" else partner

    if "from_account_id" in updates:
        _get_active_account_or_404(db, updates["from_account_id"], label="Source account")
        debit.account_id = updates["from_account_id"]

    if "to_account_id" in updates:
        _get_active_account_or_404(db, updates["to_account_id"], label="Destination account")
        credit.account_id = updates["to_account_id"]

    db.commit()
    db.refresh(txn)
    db.refresh(partner)
    for row in [txn, partner]:
        _attach_display_names(db, row)
    return [txn, partner]


# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------


def delete_transaction(db: Session, txn_id: int) -> None:
    """
    Delete a transaction. For transfer rows, also deletes the paired partner row.

    Both deletes happen in one commit so there's no moment where only one half of a
    transfer exists — either both rows are deleted or neither is.
    """
    txn = get_transaction_or_404(db, txn_id)
    partner = _find_transfer_partner(db, txn)

    db.delete(txn)
    if partner is not None:
        db.delete(partner)

    db.commit()

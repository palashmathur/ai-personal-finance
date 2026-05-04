# Business logic for the Accounts resource.
# Pure functions only — no FastAPI imports, no HTTP concerns, no Depends().
# Think of this as your Spring Boot @Service class: the router calls in,
# the service does the work, and the router sends the result back to the caller.
#
# Every function takes an explicit `db: Session` argument rather than pulling one
# from a global — this makes unit testing straightforward (pass in a test session,
# assert on the result).

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import Account, InvestmentTxn, Transaction
from app.schemas.accounts_schema import AccountCreate, AccountUpdate


def list_accounts(db: Session, include_archived: bool = False) -> list[Account]:
    """
    Return all accounts, optionally including archived ones.

    By default we filter out archived accounts because they shouldn't appear in
    dropdowns or the active account list — they're soft-deleted.
    Pass include_archived=True to show everything (e.g. for an admin view or audit).
    """
    query = db.query(Account)
    if not include_archived:
        query = query.filter(Account.archived == False)  # noqa: E712
    return query.order_by(Account.created_at).all()


def get_account_or_404(db: Session, account_id: int) -> Account:
    """
    Fetch a single account by ID, raising a 404 if it doesn't exist.
    Used internally by update and delete so they share the same not-found logic.
    """
    account = db.get(Account, account_id)
    if account is None:
        raise HTTPException(status_code=404, detail=f"Account {account_id} not found.")
    return account


def create_account(db: Session, data: AccountCreate) -> Account:
    """
    Insert a new account row and return it.

    Rejects duplicates: an account with the same name (case-insensitive) and type
    cannot be created twice, even if the existing one is archived. If you want to
    reuse an archived account, restore it via PATCH instead of creating a new one.

    opening_balance_minor represents the balance the account held before you
    started tracking it in this app — needed so net worth math is correct from day 1.
    The ge=0 constraint in the schema already blocks negative values, so we don't
    re-validate here.
    """
    # Case-insensitive name match so "ICICI" and "icici" are treated as the same account.
    existing = (
        db.query(Account)
        .filter(
            func.lower(Account.name) == func.lower(data.name),
            Account.type == data.type.value,
        )
        .first()
    )
    if existing is not None:
        status = "archived" if existing.archived else "active"
        raise HTTPException(
            status_code=409,
            detail=(
                f"An {status} account named '{existing.name}' of type '{existing.type}' "
                f"already exists (id={existing.id}). "
                f"{'Restore it via PATCH instead of creating a new one.' if existing.archived else 'Use PATCH to update it.'}"
            ),
        )

    account = Account(
        name=data.name,
        type=data.type.value,
        opening_balance_minor=data.opening_balance_minor,
    )
    db.add(account)
    db.commit()
    db.refresh(account)
    return account


def update_account(db: Session, account_id: int, data: AccountUpdate) -> Account:
    """
    Partially update an account — only the fields explicitly included in the request
    body are changed, everything else stays as-is.

    This is the PATCH semantics (vs PUT which replaces the whole resource).
    We iterate over the schema's set fields rather than checking each field manually,
    so adding a new field to AccountUpdate automatically works here without code changes.

    Setting archived=True is the soft-delete path — the account disappears from
    active lists but its transactions remain fully intact.
    """
    account = get_account_or_404(db, account_id)

    # model_fields_set contains only the keys the caller actually sent in the body,
    # so we never accidentally overwrite a field with None just because it was omitted.
    for field, value in data.model_dump(exclude_unset=True).items():
        # AccountType is an enum — store its raw string value, not the enum object.
        if hasattr(value, "value"):
            value = value.value
        setattr(account, field, value)

    db.commit()
    db.refresh(account)
    return account


def delete_account(db: Session, account_id: int) -> None:
    """
    Hard-delete an account. Raises 409 if any transactions or investment trades
    reference this account, because removing it would leave orphaned records.

    We check in the service layer rather than letting the DB raise an IntegrityError
    so we can return a clean {"detail": "...", "code": "conflict"} response instead
    of a raw SQLAlchemy exception that would produce a confusing 500.

    The right way to "remove" an account that has history is to archive it
    (PATCH with archived=true), not delete it.
    """
    account = get_account_or_404(db, account_id)

    # Check for referencing cash transactions.
    txn_count = db.query(Transaction).filter(Transaction.account_id == account_id).count()
    if txn_count > 0:
        raise HTTPException(
            status_code=409,
            detail=(
                f"Cannot delete account '{account.name}': "
                f"{txn_count} transaction(s) reference it. Archive the account instead."
            ),
        )

    # Check for referencing investment trades.
    inv_count = (
        db.query(InvestmentTxn).filter(InvestmentTxn.account_id == account_id).count()
    )
    if inv_count > 0:
        raise HTTPException(
            status_code=409,
            detail=(
                f"Cannot delete account '{account.name}': "
                f"{inv_count} investment transaction(s) reference it. Archive the account instead."
            ),
        )

    db.delete(account)
    db.commit()

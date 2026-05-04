# FastAPI router for the Accounts resource.
# Pure HTTP plumbing — validate the request, call the service, return the response.
# No business logic lives here; it all lives in accounts_service.py.
# Think of this as your Spring Boot @RestController — it wires URLs to service calls.

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.accounts_schema import AccountCreate, AccountResponse, AccountUpdate
from app.services import accounts_service

router = APIRouter(prefix="/api/accounts", tags=["accounts"])


@router.get("", response_model=list[AccountResponse])
def list_accounts(archived: bool = False, db: Session = Depends(get_db)):
    """
    List all accounts.

    By default returns only active (non-archived) accounts — what you'd show in
    any dropdown or dashboard widget. Pass ?archived=true to include soft-deleted
    accounts as well (useful for audit or to restore one).
    """
    return accounts_service.list_accounts(db, include_archived=archived)


@router.post("", response_model=AccountResponse, status_code=status.HTTP_201_CREATED)
def create_account(data: AccountCreate, db: Session = Depends(get_db)):
    """
    Create a new account.

    Returns 201 with the created account. The `type` field must be one of:
    cash | bank | broker | wallet | credit_card — anything else is a 422.
    `opening_balance_minor` is the account's balance in paise before you started
    tracking it in this app. Defaults to 0.
    """
    return accounts_service.create_account(db, data)


@router.patch("/{account_id}", response_model=AccountResponse)
def update_account(account_id: int, data: AccountUpdate, db: Session = Depends(get_db)):
    """
    Partially update an account. Only the fields you include in the body are changed.

    This doubles as the soft-delete endpoint: send {"archived": true} to hide the
    account from active lists while preserving all its transaction history.
    Send {"archived": false} to restore it.
    """
    return accounts_service.update_account(db, account_id, data)


@router.delete("/{account_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_account(account_id: int, db: Session = Depends(get_db)):
    """
    Hard-delete an account. Returns 204 No Content on success.

    Returns 409 Conflict if any transactions or investment trades reference this account.
    In that case, use PATCH with {"archived": true} to soft-delete instead.
    """
    accounts_service.delete_account(db, account_id)

# Pydantic schemas for the Transactions resource.
# These are the request/response contracts — the API boundary where data is validated
# before it ever reaches the service layer.
#
# TransactionCreate uses a single unified body for both regular transactions and transfers.
# Cross-field rules (e.g. "transfer requires from/to accounts, not account_id") are
# enforced in the service layer via HTTPException(422) rather than in a Pydantic
# model_validator, because model_validator errors don't reliably pass through FastAPI's
# custom exception handler in all version combinations.

from datetime import date, datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class TransactionKind(str, Enum):
    """
    The allowed transaction kinds. Drives validation rules and sign logic.
    - income: money coming in — requires account_id + category_id (income kind).
    - expense: money going out — requires account_id + category_id (expense kind).
    - transfer: money moving between your own accounts — no category, uses from/to accounts.
    """

    income = "income"
    expense = "expense"
    transfer = "transfer"


class TransactionSource(str, Enum):
    """
    How the transaction was created. Useful for audit and debugging
    (e.g. "how much of my data came from CSV imports vs manual entry?").
    """

    manual = "manual"
    csv = "csv"
    nl = "nl"


class TransactionCreate(BaseModel):
    """
    Request body for POST /api/transactions.

    One schema handles both regular transactions and transfers. All kind-specific
    fields are optional at the schema level; the service enforces the cross-field
    rules and raises HTTPException(422) if they are violated.

    - income/expense: needs account_id + category_id; from/to_account_id must be absent.
    - transfer: needs from_account_id + to_account_id (different); account_id + category_id must be absent.
    """

    kind: TransactionKind
    # gt=0 means "greater than 0" — zero-amount transactions are meaningless.
    amount_minor: int = Field(gt=0, description="Amount in paise (1 INR = 100 paise). Must be > 0.")
    occurred_on: date
    note: Optional[str] = None
    source: TransactionSource = TransactionSource.manual

    # Fields for income/expense only
    account_id: Optional[int] = None
    category_id: Optional[int] = None

    # Fields for transfer only
    from_account_id: Optional[int] = None
    to_account_id: Optional[int] = None


class TransactionUpdate(BaseModel):
    """
    Request body for PATCH /api/transactions/{id}.
    Every field is optional — callers send only what they want to change.

    `kind` is intentionally absent: changing a transaction's kind (e.g. expense → transfer)
    is a destructive semantic change that requires delete + re-create, not a patch.

    `extra="ignore"` means unknown keys in the request body are silently dropped
    rather than causing a 422 — same pattern as AccountUpdate and CategoryUpdate.
    """

    model_config = ConfigDict(extra="ignore")

    amount_minor: Optional[int] = Field(default=None, gt=0)
    occurred_on: Optional[date] = None
    note: Optional[str] = None
    category_id: Optional[int] = None

    # Transfer-specific: lets the caller change which account is source or destination
    from_account_id: Optional[int] = None
    to_account_id: Optional[int] = None


class TransactionResponse(BaseModel):
    """
    Response shape for all transaction endpoints.

    Includes `account_name` and `category_name` as denormalized display fields —
    the service attaches these as transient Python attributes before returning, so the
    frontend doesn't need to make separate account/category lookups for every row.

    from_attributes=True (Pydantic v2's orm_mode equivalent) lets Pydantic read directly
    from SQLAlchemy ORM instances, including the transient attrs set by the service.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    account_id: int
    account_name: str
    category_id: Optional[int]
    category_name: Optional[str]
    kind: TransactionKind
    amount_minor: int
    occurred_on: date
    note: Optional[str]
    source: TransactionSource
    created_at: datetime
    updated_at: datetime

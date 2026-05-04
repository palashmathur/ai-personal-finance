# Pydantic schemas for the Accounts resource.
# These are the request/response contracts — what the API accepts and what it returns.
# Think of these as your Spring Boot @RequestBody and @ResponseBody DTOs.
#
# Separating schemas from ORM models matters because what the API exposes doesn't
# have to match what the DB stores 1:1. For example, we never expose the raw DB
# primary key type decisions to callers, and we validate enums here before they
# even reach the service layer.

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class AccountType(str, Enum):
    """
    The allowed account types. Stored as a string in the DB, but validated as an
    enum at the API boundary so callers get a clear 422 if they pass an unknown type.

    - cash/bank/wallet: liquid accounts tracked in the cash ledger.
    - broker: investment accounts — only appear on investment transaction forms.
    - credit_card: treated as a liability in net worth calculations.
    """

    cash = "cash"
    bank = "bank"
    broker = "broker"
    wallet = "wallet"
    credit_card = "credit_card"


class AccountCreate(BaseModel):
    """
    Request body for POST /api/accounts.
    All fields are required except opening_balance_minor, which defaults to 0
    (sensible default when you start tracking an account mid-life).
    """

    name: str
    type: AccountType
    # ge=0 means "greater than or equal to 0" — negative opening balances are not allowed.
    # The balance can go negative later due to transactions, but the starting point can't be.
    opening_balance_minor: int = Field(default=0, ge=0)


class AccountUpdate(BaseModel):
    """
    Request body for PATCH /api/accounts/{id}.
    Every field is optional so callers can update just the fields they care about
    — same pattern as a Spring Boot @PatchMapping where you merge only non-null fields.

    Setting archived=True is how you soft-delete an account (hides it from dropdowns
    but keeps all its transaction history intact).
    """

    model_config = ConfigDict(extra="ignore")

    name: Optional[str] = None
    type: Optional[AccountType] = None
    opening_balance_minor: Optional[int] = Field(default=None, ge=0)
    archived: Optional[bool] = None


class AccountResponse(BaseModel):
    """
    Response shape for every account endpoint. Maps 1:1 to the DB row.
    orm_mode (from_attributes in Pydantic v2) lets Pydantic read directly
    from SQLAlchemy model instances without needing to convert to a dict first.
    Think of it like Jackson's @JsonProperty reading from a JPA entity.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    type: AccountType
    opening_balance_minor: int
    archived: bool
    created_at: datetime

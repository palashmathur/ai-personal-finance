# Business logic for the InvestmentTxns resource.
# Pure functions — no FastAPI imports, no Depends. Routers call these.
# Think of this as the @Service layer in Spring Boot.
#
# The two most important domain rules here:
#  1. account.type must be broker or wallet — you can't record investment trades
#     against a bank savings account.
#  2. Bootstrap side-effect on first trade: if instrument.current_price_minor is NULL,
#     we set it to this trade's price_minor so the holdings page has a non-NULL price
#     to render immediately. This only fires when the price is NULL (idempotent).

from datetime import date
from typing import Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models import Account, Instrument, InvestmentTxn
from app.schemas.investment_txns_schema import InvestmentTxnCreate, InvestmentTxnUpdate

# Account types that can be used for investment trades.
# broker/wallet: direct investment accounts (Zerodha, Coinbase, etc.)
# bank/cash: allowed because SIP debits come directly from a bank account —
# the MF units are linked to the bank, not a separate broker account.
# credit_card is still excluded — you can't invest via a credit card.
_INVESTMENT_ACCOUNT_TYPES = {"broker", "wallet", "bank", "cash"}


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _get_investment_account_or_error(db: Session, account_id: int) -> Account:
    """
    Fetch an account and validate it's suitable for investment trades.

    404 if the account doesn't exist.
    422 if the account is a credit_card — the only excluded type.
    broker/wallet: direct investment accounts. bank/cash: allowed because
    SIP debits come directly from a bank account without a separate broker.
    """
    account = db.get(Account, account_id)
    if account is None:
        raise HTTPException(status_code=404, detail=f"Account {account_id} not found.")
    if account.type not in _INVESTMENT_ACCOUNT_TYPES:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Account '{account.name}' has type '{account.type}'. "
                f"Investment trades require an account of type broker, wallet, bank, or cash."
            ),
        )
    return account


def _get_instrument_or_404(db: Session, instrument_id: int) -> Instrument:
    """
    Fetch an instrument from the catalog by ID.
    Raises 404 if the instrument doesn't exist — caller must create the instrument
    first via POST /api/instruments before recording a trade against it.
    """
    instrument = db.get(Instrument, instrument_id)
    if instrument is None:
        raise HTTPException(
            status_code=404,
            detail=(
                f"Instrument {instrument_id} not found. "
                f"Create the instrument first via POST /api/instruments."
            ),
        )
    return instrument


def _get_txn_or_404(db: Session, txn_id: int) -> InvestmentTxn:
    """Fetch a single investment trade by ID, raising 404 if missing."""
    txn = db.get(InvestmentTxn, txn_id)
    if txn is None:
        raise HTTPException(
            status_code=404, detail=f"Investment transaction {txn_id} not found."
        )
    return txn


def _bootstrap_instrument_price(db: Session, instrument: Instrument, price_minor: int) -> None:
    """
    Set the instrument's current price from this trade's price — but only if no price
    has been recorded yet (current_price_minor IS NULL).

    This is the "first trade bootstrap" pattern: when you record your very first buy of
    HDFCBANK at ₹1,600, the holdings page needs a price to compute market value.
    Without this, every newly-added instrument would show ₹0 or NULL until you manually
    update the price. The UPDATE ... WHERE NULL guard makes it idempotent — once a real
    price exists (from a later PATCH or cron job), this will never overwrite it.
    """
    if instrument.current_price_minor is None:
        instrument.current_price_minor = price_minor
        # Don't set price_updated_at here — that field is reserved for explicit price
        # refreshes (manual PATCH or V2 cron). Bootstrap is just a convenience default.


# ---------------------------------------------------------------------------
# Public service functions
# ---------------------------------------------------------------------------


def create_investment_txn(db: Session, data: InvestmentTxnCreate) -> InvestmentTxn:
    """
    Record a new investment trade and return it with the related instrument loaded.

    Steps:
    1. Validate account exists and is broker/wallet type.
    2. Validate instrument exists in the catalog.
    3. Insert the trade row.
    4. Bootstrap the instrument price if this is the first trade (price was NULL).
    """
    _get_investment_account_or_error(db, data.account_id)
    instrument = _get_instrument_or_404(db, data.instrument_id)

    # Validate numeric constraints here rather than in the Pydantic schema because
    # field_validator errors don't reliably produce 422s in Python 3.9 + this FastAPI version.
    # Raising HTTPException(422) from the service layer is always caught correctly.
    if data.quantity <= 0:
        raise HTTPException(status_code=422, detail="quantity must be greater than 0.")
    if data.price_minor < 0:
        raise HTTPException(status_code=422, detail="price_minor must be >= 0.")
    if data.fee_minor < 0:
        raise HTTPException(status_code=422, detail="fee_minor must be >= 0.")

    txn = InvestmentTxn(
        account_id=data.account_id,
        instrument_id=data.instrument_id,
        side=data.side.value,
        quantity=data.quantity,
        price_minor=data.price_minor,
        fee_minor=data.fee_minor,
        occurred_on=data.occurred_on,
        note=data.note,
        source=data.source,
    )
    db.add(txn)

    # Bootstrap price before commit so both changes land in the same transaction.
    _bootstrap_instrument_price(db, instrument, data.price_minor)

    db.commit()
    db.refresh(txn)
    return txn


def list_investment_txns(
    db: Session,
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
    instrument_id: Optional[int] = None,
    account_id: Optional[int] = None,
    side: Optional[str] = None,
) -> list[InvestmentTxn]:
    """
    List investment trades with optional filters.

    All filters are AND-combined — e.g. instrument_id=7 AND side=buy returns only
    buys of that specific instrument. Ordered by occurred_on DESC (most recent first).
    """
    query = db.query(InvestmentTxn)

    if from_date is not None:
        query = query.filter(InvestmentTxn.occurred_on >= from_date)
    if to_date is not None:
        query = query.filter(InvestmentTxn.occurred_on <= to_date)
    if instrument_id is not None:
        query = query.filter(InvestmentTxn.instrument_id == instrument_id)
    if account_id is not None:
        query = query.filter(InvestmentTxn.account_id == account_id)
    if side is not None:
        query = query.filter(InvestmentTxn.side == side)

    return query.order_by(InvestmentTxn.occurred_on.desc()).all()


def update_investment_txn(
    db: Session, txn_id: int, data: InvestmentTxnUpdate
) -> InvestmentTxn:
    """
    Partially update a trade — only the fields present in the request body change.

    If instrument_id is being changed, we validate the new instrument exists.
    If account_id is being changed, we validate the new account is broker/wallet.
    """
    txn = _get_txn_or_404(db, txn_id)

    update_data = data.model_dump(exclude_unset=True)

    # Validate any FK references that are being changed.
    if "account_id" in update_data:
        _get_investment_account_or_error(db, update_data["account_id"])
    if "instrument_id" in update_data:
        _get_instrument_or_404(db, update_data["instrument_id"])

    # Convert enum to its string value before writing to the DB.
    if "side" in update_data and update_data["side"] is not None:
        update_data["side"] = update_data["side"].value

    for field, value in update_data.items():
        setattr(txn, field, value)

    db.commit()
    db.refresh(txn)
    return txn


def delete_investment_txn(db: Session, txn_id: int) -> None:
    """
    Hard-delete a trade by ID.

    No FK in the schema points at investment_txns, so hard delete is safe.
    The holdings aggregation query just recalculates from the remaining rows.
    """
    txn = _get_txn_or_404(db, txn_id)
    db.delete(txn)
    db.commit()

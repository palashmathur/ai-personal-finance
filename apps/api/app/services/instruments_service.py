# Business logic for the Instruments resource.
# Pure functions only — no FastAPI routing, no HTTP concerns.
# Think of this as your Spring Boot @Service class.
#
# Instruments are the catalog of things you can invest in.
# The key uniqueness rule: (kind, symbol) must be unique — not symbol alone.
# The same "HDFCBANK" symbol could exist as a stock and theoretically as an ETF,
# so we scope uniqueness to kind+symbol together.

from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import Instrument
from app.schemas.instruments_schema import InstrumentCreate, InstrumentUpdate


def list_all_instruments(db: Session) -> list[Instrument]:
    """
    Return every instrument in the catalog, ordered by name.
    Used by the GET /api/instruments endpoint when no search term is provided —
    e.g. to populate a full dropdown or an admin list view.
    """
    return db.query(Instrument).order_by(Instrument.name).all()


def search_instruments(db: Session, q: str) -> list[Instrument]:
    """
    Case-insensitive search across both symbol and name, returning up to 20 results.

    This powers the typeahead on the "Add Investment" form — as you type "HDFC",
    it should surface "HDFCBANK" (stock) and "HDFC Top 100 Fund" (mutual fund) together.

    Ordered by name so results are consistent and easy to scan.
    """
    pattern = f"%{q}%"
    return (
        db.query(Instrument)
        .filter(
            func.lower(Instrument.symbol).like(func.lower(pattern))
            | func.lower(Instrument.name).like(func.lower(pattern))
        )
        .order_by(Instrument.name)
        .limit(20)
        .all()
    )


def get_instrument_or_404(db: Session, instrument_id: int) -> Instrument:
    """
    Fetch a single instrument by ID, raising 404 if it doesn't exist.
    Shared by update so not-found logic stays in one place.
    """
    instrument = db.get(Instrument, instrument_id)
    if instrument is None:
        raise HTTPException(
            status_code=404, detail=f"Instrument {instrument_id} not found."
        )
    return instrument


def create_instrument(db: Session, data: InstrumentCreate) -> Instrument:
    """
    Insert a new instrument into the catalog and return it.

    Enforces the (kind, symbol) uniqueness constraint at the service layer with a
    clear 409 response — much friendlier than letting the DB raise an IntegrityError
    and returning a confusing 500.

    The symbol comparison is case-insensitive so "hdfcbank" and "HDFCBANK" are
    treated as the same ticker.
    """
    existing = (
        db.query(Instrument)
        .filter(
            func.lower(Instrument.symbol) == func.lower(data.symbol),
            Instrument.kind == data.kind.value,
        )
        .first()
    )
    if existing is not None:
        raise HTTPException(
            status_code=409,
            detail=(
                f"An instrument with symbol '{existing.symbol}' and kind '{existing.kind}' "
                f"already exists (id={existing.id}). "
                f"Use PATCH /api/instruments/{existing.id} to update it."
            ),
        )

    instrument = Instrument(
        kind=data.kind.value,
        symbol=data.symbol,
        name=data.name,
        current_price_minor=data.current_price_minor,
        # If a price is given at creation, record when it was set so the UI
        # can show a "stale price" badge if it goes unrefreshed for too long.
        price_updated_at=datetime.now(timezone.utc) if data.current_price_minor is not None else None,
        meta=data.meta,
    )
    db.add(instrument)
    db.commit()
    db.refresh(instrument)
    return instrument


def update_instrument(db: Session, instrument_id: int, data: InstrumentUpdate) -> Instrument:
    """
    Partially update an instrument — only the fields included in the request body change.

    The most common use case is updating current_price_minor when you manually
    refresh a price. When a price update is included we also stamp price_updated_at
    so the UI can tell when the price was last refreshed.

    PATCH semantics: fields absent from the request body are left untouched.
    """
    instrument = get_instrument_or_404(db, instrument_id)

    update_data = data.model_dump(exclude_unset=True)

    # When a new price comes in, stamp the refresh time so the UI can show
    # "last updated 2 days ago" and warn when a price is stale.
    if "current_price_minor" in update_data:
        instrument.price_updated_at = datetime.now(timezone.utc)

    for field, value in update_data.items():
        setattr(instrument, field, value)

    db.commit()
    db.refresh(instrument)
    return instrument

# FastAPI router for the Instruments resource.
# Pure HTTP plumbing — validate the request, call the service, return the response.
# Think of this as your Spring Boot @RestController for the instruments catalog.
#
# Three endpoints:
#   GET  /api/instruments?q=  — typeahead search (used by the Add Investment form)
#   POST /api/instruments     — create a new instrument in the catalog
#   PATCH /api/instruments/{id} — update name, price, or meta (no delete — see service)

from typing import Optional

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.instruments_schema import (
    InstrumentCreate,
    InstrumentResponse,
    InstrumentUpdate,
)
from app.services import instruments_service

router = APIRouter(prefix="/api/instruments", tags=["instruments"])


@router.get("", response_model=list[InstrumentResponse])
def list_instruments(search: Optional[str] = None, db: Session = Depends(get_db)):
    """
    List instruments, with optional search filtering by symbol or name.

    - No `search` param → returns all instruments, ordered by name.
    - `?search=hdfc` → returns up to 20 instruments whose symbol or name contains
      "hdfc" (case-insensitive). Used by the typeahead on the Add Investment form.
    """
    if search and search.strip():
        return instruments_service.search_instruments(db, search.strip())
    return instruments_service.list_all_instruments(db)


@router.post("", response_model=InstrumentResponse, status_code=status.HTTP_201_CREATED)
def create_instrument(data: InstrumentCreate, db: Session = Depends(get_db)):
    """
    Add a new instrument to the catalog.

    Returns 409 if an instrument with the same (kind, symbol) already exists.
    The same symbol can exist under different kinds — e.g. "NIFTYBEES" can be
    both a stock and an ETF — so the uniqueness check is on the combination.
    """
    return instruments_service.create_instrument(db, data)


@router.patch("/{instrument_id}", response_model=InstrumentResponse)
def update_instrument(
    instrument_id: int, data: InstrumentUpdate, db: Session = Depends(get_db)
):
    """
    Partially update an instrument. Only fields included in the body are changed.

    Most commonly used to refresh `current_price_minor` manually before the V2
    price-fetch cron is built. When a new price is provided, `price_updated_at`
    is automatically stamped so the UI can track price freshness.
    """
    return instruments_service.update_instrument(db, instrument_id, data)

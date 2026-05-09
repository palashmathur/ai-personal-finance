# Business logic for the Holdings resource.
# Holdings are computed entirely from investment_txns — no separate table.
# Think of this as the read-side projection of your trade ledger.
#
# The core idea: GROUP BY (instrument_id, account_id) across all trades and
# compute qty, cost_basis, market_value, and unrealized P&L in one SQL pass.
# This is identical to how a brokerage back-office computes positions — aggregate
# the event log, never store derived state.

from typing import Optional

from sqlalchemy import case, func
from sqlalchemy.orm import Session

from app.models import Instrument, InvestmentTxn
from app.schemas.holdings_schema import HoldingInstrument, HoldingResponse


def get_holdings(db: Session, account_id: Optional[int] = None) -> list[HoldingResponse]:
    """
    Compute current holdings by aggregating all investment trades.

    For each (instrument_id, account_id) pair:
      qty          = SUM(buy qty) - SUM(sell qty)
      cost_basis   = SUM(buy qty × price_minor + fee_minor)

    Positions where qty <= 0 are excluded — they represent fully sold holdings.
    market_value and unrealized_pnl are computed in Python after the query
    because current_price_minor lives on the instrument, not the trade rows.

    The optional account_id filter lets the frontend show holdings for a
    specific broker account (e.g. "what do I hold in Zerodha only?").
    """
    # Build the aggregation query.
    # case() is SQLAlchemy's way of writing SQL CASE WHEN expressions —
    # same as a ternary in application code but evaluated inside the DB.
    qty_expr = func.sum(
        case(
            (InvestmentTxn.side == "buy", InvestmentTxn.quantity),
            (InvestmentTxn.side == "sell", -InvestmentTxn.quantity),
            else_=0,  # dividends don't change qty
        )
    )

    # Cost basis: only buy-side trades contribute.
    # fee_minor is added to cost because brokerage fees raise your effective purchase price.
    cost_basis_expr = func.sum(
        case(
            (
                InvestmentTxn.side == "buy",
                InvestmentTxn.quantity * InvestmentTxn.price_minor + InvestmentTxn.fee_minor,
            ),
            else_=0,
        )
    )

    query = (
        db.query(
            InvestmentTxn.instrument_id,
            InvestmentTxn.account_id,
            qty_expr.label("qty"),
            cost_basis_expr.label("cost_basis_minor"),
        )
        .group_by(InvestmentTxn.instrument_id, InvestmentTxn.account_id)
        .having(qty_expr > 0)  # exclude fully sold positions
    )

    if account_id is not None:
        query = query.filter(InvestmentTxn.account_id == account_id)

    rows = query.all()

    # Fetch the instruments needed to compute market value and build the response.
    # Collect unique instrument IDs from the aggregated rows, then load them in one query
    # instead of one query per row (avoids N+1).
    instrument_ids = {row.instrument_id for row in rows}
    instruments_by_id: dict[int, Instrument] = {}
    if instrument_ids:
        instruments = db.query(Instrument).filter(Instrument.id.in_(instrument_ids)).all()
        instruments_by_id = {i.id: i for i in instruments}

    holdings = []
    for row in rows:
        instrument = instruments_by_id.get(row.instrument_id)

        # Compute market value and P&L only when a price is available.
        # If no price has been set on the instrument yet, these come back None
        # so the frontend can show a "price missing" indicator rather than ₹0.
        if instrument and instrument.current_price_minor is not None:
            market_value = int(row.qty * instrument.current_price_minor)
            unrealized_pnl = market_value - int(row.cost_basis_minor)
        else:
            market_value = None
            unrealized_pnl = None

        holdings.append(
            HoldingResponse(
                instrument_id=row.instrument_id,
                instrument=HoldingInstrument(
                    id=instrument.id,
                    kind=instrument.kind,
                    symbol=instrument.symbol,
                    name=instrument.name,
                    current_price_minor=instrument.current_price_minor,
                )
                if instrument
                else None,
                account_id=row.account_id,
                qty=row.qty,
                cost_basis_minor=int(row.cost_basis_minor),
                market_value_minor=market_value,
                unrealized_pnl_minor=unrealized_pnl,
            )
        )

    return holdings

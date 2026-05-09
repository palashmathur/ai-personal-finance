# Business logic for the Unified Ledger endpoint.
# Merges cash transactions and investment trades into one chronological list
# using a SQL UNION ALL — the same pattern described in the design doc §4b.
#
# Why raw SQL instead of ORM here?
# The UNION ALL spans two unrelated tables with different columns. SQLAlchemy's ORM
# is designed for single-table queries and joins — making it do a UNION requires
# ugly workarounds. Raw SQL with text() is cleaner, easier to read, and exactly
# what the design doc shows. Think of it like a native query in Spring Data JPA
# when a @Query annotation is cleaner than building a CriteriaQuery.

from datetime import date

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.schemas.ledger_schema import LedgerEntryResponse

# The UNION ALL query that merges both tables into a single timeline.
# Each branch produces the same 12 columns so UNION ALL can stack them.
#
# Investment amount_minor sign convention (matches the design doc):
#   buy:      cash goes OUT  → positive (an outflow from your perspective)
#   sell:     cash comes IN  → negative outflow = positive inflow, stored positive here too
#   dividend: cash comes IN  → same as sell
# The frontend uses `kind` (inv_buy vs inv_sell) to decide sign for display.
_LEDGER_SQL = text("""
    SELECT
        'cash'                          AS source,
        t.id                            AS source_id,
        t.kind                          AS kind,
        t.account_id                    AS account_id,
        t.category_id                   AS category_id,
        NULL                            AS instrument_id,
        NULL                            AS quantity,
        t.amount_minor                  AS amount_minor,
        t.occurred_on                   AS occurred_on,
        t.note                          AS note,
        t.created_at                    AS created_at
    FROM transactions t
    WHERE t.occurred_on BETWEEN :from_date AND :to_date

    UNION ALL

    SELECT
        'investment'                    AS source,
        it.id                           AS source_id,
        'inv_' || it.side               AS kind,
        it.account_id                   AS account_id,
        NULL                            AS category_id,
        it.instrument_id                AS instrument_id,
        it.quantity                     AS quantity,
        CASE it.side
            WHEN 'buy'      THEN it.quantity * it.price_minor + it.fee_minor
            WHEN 'sell'     THEN it.quantity * it.price_minor - it.fee_minor
            WHEN 'dividend' THEN it.price_minor
        END                             AS amount_minor,
        it.occurred_on                  AS occurred_on,
        it.note                         AS note,
        it.created_at                   AS created_at
    FROM investment_txns it
    WHERE it.occurred_on BETWEEN :from_date AND :to_date

    ORDER BY occurred_on DESC, created_at DESC
    LIMIT :limit OFFSET :offset
""")


def list_ledger(
    db: Session,
    from_date: date,
    to_date: date,
    limit: int = 50,
    offset: int = 0,
) -> list[LedgerEntryResponse]:
    """
    Return a unified, paginated ledger of all cash transactions and investment trades
    for the given period, ordered most-recent first.

    This is the "bank statement" view — one list covering everything that moved money,
    regardless of whether it came from the transactions table or investment_txns.

    Pagination: `limit` controls page size (default 50), `offset` skips rows.
    For page 2 with 50 per page: limit=50, offset=50.
    """
    rows = db.execute(
        _LEDGER_SQL,
        {
            "from_date": from_date.isoformat(),
            "to_date": to_date.isoformat(),
            "limit": limit,
            "offset": offset,
        },
    ).mappings().all()

    return [
        LedgerEntryResponse(
            source=row["source"],
            source_id=row["source_id"],
            kind=row["kind"],
            account_id=row["account_id"],
            category_id=row["category_id"],
            instrument_id=row["instrument_id"],
            quantity=row["quantity"],
            amount_minor=row["amount_minor"],
            occurred_on=row["occurred_on"],
            note=row["note"],
            created_at=row["created_at"],
        )
        for row in rows
    ]

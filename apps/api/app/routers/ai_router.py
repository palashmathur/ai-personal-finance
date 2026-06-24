# FastAPI router for AI-related endpoints.
# Grouped under /api/ai/ — covers usage stats now, and will gain more
# endpoints (nl-input, chat) as subsequent AI tickets land.

from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import AICall
from app.schemas.ai_schema import FeatureUsageSummary, UsageResponse
from app.schemas.nl_input_schema import NLEntryResponse, NLInputRequest
from app.services import nl_input as nl_input_svc

router = APIRouter(prefix="/api/ai", tags=["ai"])


@router.post("/nl-input", response_model=NLEntryResponse)
def nl_input(nl_input_request: NLInputRequest, db: Session = Depends(get_db)):
    """
    Parse a natural-language sentence into a draft transaction.

    Send a sentence like "spent 1200 on groceries at DMart yesterday" plus the
    account to fall back to when none is named. You get back a fully resolved draft
    (amount in paise, ISO date, account/category IDs) ready for a confirm card.

    This does NOT save anything — the frontend shows the draft, the user confirms or
    edits, then POSTs to /api/transactions. Returns 422 if no amount is found in the
    text or the default account doesn't exist.
    """
    return nl_input_svc.parse_nl_entry(db, nl_input_request)


@router.get("/usage", response_model=UsageResponse)
def get_usage(
    from_date: date = Query(..., alias="from"),
    to_date: date = Query(..., alias="to"),
    db: Session = Depends(get_db),
):
    """
    Return aggregated AI token usage for a date range.

    Both `from` and `to` are required. Results are inclusive of both endpoints.
    The response breaks totals down by feature so you can see which part of the
    app is responsible for most of the token spend.

    Typical use: monitor AI costs after adding a new feature, or check whether
    prompt caching is actually working (estimated_cache_hit_rate should be > 0.8
    for high-frequency features like auto-categorization).
    """
    if from_date > to_date:
        raise HTTPException(
            status_code=422,
            detail=f"'from' ({from_date}) must not be after 'to' ({to_date}).",
        )

    # Convert dates to datetimes for the BETWEEN comparison — ai_calls.created_at
    # is a DateTime column, so comparing against a bare date may miss rows on to_date.
    from_dt = datetime.combine(from_date, datetime.min.time())
    to_dt = datetime.combine(to_date, datetime.max.time())

    # Aggregate totals and per-feature breakdowns in a single query using GROUP BY.
    # Each row in the result is one feature slug with its summed token counts.
    rows = (
        db.query(
            AICall.feature,
            func.count(AICall.id).label("calls"),
            func.sum(AICall.input_tokens).label("input_tokens"),
            func.sum(AICall.output_tokens).label("output_tokens"),
            func.sum(AICall.cache_read_tokens).label("cache_read_tokens"),
            func.sum(AICall.cache_creation_tokens).label("cache_creation_tokens"),
        )
        .filter(AICall.created_at.between(from_dt, to_dt))
        .group_by(AICall.feature)
        .all()
    )

    # Build the per-feature map and accumulate grand totals in one pass.
    by_feature: dict[str, FeatureUsageSummary] = {}
    total_calls = 0
    total_input = 0
    total_output = 0
    total_cache_read = 0
    total_cache_creation = 0

    for row in rows:
        by_feature[row.feature] = FeatureUsageSummary(
            calls=row.calls,
            input_tokens=row.input_tokens or 0,
            output_tokens=row.output_tokens or 0,
            cache_read_tokens=row.cache_read_tokens or 0,
            cache_creation_tokens=row.cache_creation_tokens or 0,
        )
        total_calls += row.calls
        total_input += row.input_tokens or 0
        total_output += row.output_tokens or 0
        total_cache_read += row.cache_read_tokens or 0
        total_cache_creation += row.cache_creation_tokens or 0

    # Cache hit rate = cache reads / (regular input + cache reads).
    # This is the fraction of input tokens that were served from the cache.
    # We exclude cache_creation tokens from the denominator — those were paid
    # once to build the cache, not to answer the actual request.
    denominator = total_input + total_cache_read
    cache_hit_rate = (total_cache_read / denominator) if denominator > 0 else None

    return UsageResponse(
        total_calls=total_calls,
        total_input_tokens=total_input,
        total_output_tokens=total_output,
        total_cache_read_tokens=total_cache_read,
        total_cache_creation_tokens=total_cache_creation,
        estimated_cache_hit_rate=cache_hit_rate,
        by_feature=by_feature,
    )

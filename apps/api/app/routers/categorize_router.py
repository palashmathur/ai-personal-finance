# FastAPI router for the auto-categorize feature.
# Endpoints are grouped under /api/categorize/.
#
# POST /suggest         — single suggestion (used when manually adding a transaction)
# POST /suggest-batch   — batch suggestions (used by CSV import preview)
# POST /accept          — save a rule + optionally update a transaction's category
# GET  /rules           — list all saved rules
# DELETE /rules/{id}    — delete a rule

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import Category
from app.schemas.categorize_schema import (
    CategorizeAcceptRequest,
    CategorizeBatchRequest,
    CategorizeRuleResponse,
    CategorizeSuggestRequest,
    CategorizeSuggestResponse,
)
from app.services import categorize as svc

router = APIRouter(prefix="/api/categorize", tags=["categorize"])


@router.post("/suggest", response_model=CategorizeSuggestResponse)
def suggest(body: CategorizeSuggestRequest, db: Session = Depends(get_db)):
    """
    Return a category suggestion for a single transaction note.

    Checks saved rules first (free, instant). Falls back to the LLM only
    when no rule matches. The source field in the response tells you which path
    was taken: "rule" or "llm".
    """
    return svc.suggest(body.note, body.amount_minor, db)


@router.post("/suggest-batch", response_model=list[CategorizeSuggestResponse])
def suggest_batch(body: CategorizeBatchRequest, db: Session = Depends(get_db)):
    """
    Return one suggestion per row, in the same order as the input.

    Designed for the CSV import preview step — rules are loaded once for the
    whole batch, so a 200-row import only hits the LLM for rows that don't
    match any saved rule. Much cheaper than calling /suggest 200 times.
    """
    return svc.suggest_batch(body.rows, db)


@router.post("/accept", response_model=CategorizeRuleResponse)
def accept(body: CategorizeAcceptRequest, db: Session = Depends(get_db)):
    """
    Save a categorization rule so future matching transactions skip the LLM.

    If transaction_id is provided, that transaction's category_id is also
    updated immediately so the user sees the correct category straight away.
    """
    rule = svc.accept_rule(body, db)
    category = db.get(Category, rule.category_id)
    # Build the response manually because CategorizeRuleResponse includes category_name
    # which isn't a column on the rule — we fetch it from the category row.
    return CategorizeRuleResponse(
        id=rule.id,
        pattern=rule.pattern,
        field=rule.field,
        category_id=rule.category_id,
        category_name=category.name,
        priority=rule.priority,
        created_at=rule.created_at,
    )


@router.get("/rules", response_model=list[CategorizeRuleResponse])
def list_rules(db: Session = Depends(get_db)):
    """Return all saved categorization rules, highest priority first."""
    rules = svc.list_rules(db)
    category_by_id = {
        c.id: c for c in db.query(Category).filter(
            Category.id.in_([r.category_id for r in rules])
        ).all()
    }
    return [
        CategorizeRuleResponse(
            id=r.id,
            pattern=r.pattern,
            field=r.field,
            category_id=r.category_id,
            category_name=category_by_id[r.category_id].name,
            priority=r.priority,
            created_at=r.created_at,
        )
        for r in rules
    ]


@router.delete("/rules/{rule_id}", status_code=204)
def delete_rule(rule_id: int, db: Session = Depends(get_db)):
    """Hard-delete a categorization rule. Returns 404 if not found."""
    svc.delete_rule(rule_id, db)

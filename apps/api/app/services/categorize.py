# Business logic for the auto-categorize feature.
#
# Two-layer approach:
#   1. Regex rules — checked first, in priority order. Free, instant, deterministic.
#   2. LLM         — called only when no rule matches. Which provider/model runs is
#                    decided by config via the get_llm() factory; this module stays
#                    provider-agnostic.
#
# Over time, users accept suggestions → rules grow → AI calls drop toward zero.

import re
from pathlib import Path
from typing import Optional

from fastapi import HTTPException
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.ai.llm import get_llm
from app.models import CategorizationRule, Category, Transaction
from app.schemas.categorize_schema import (
    CategorizeAcceptRequest,
    CategorizeSuggestRequest,
    CategorizeSuggestResponse,
)

# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

_PROMPT_PATH = Path(__file__).parent.parent / "ai" / "prompts" / "categorize.md"
_SYSTEM_PROMPT = _PROMPT_PATH.read_text(encoding="utf-8")

# ---------------------------------------------------------------------------
# Structured output schema.
#
# We hand this Pydantic model to LangChain's with_structured_output(). Under the
# hood LangChain generates a tool-use schema from it and forces LLM to "call"
# that tool, so the response comes back as a populated _SuggestCategoryOutput
# instance instead of free text. We never write a handler — the model *is* the
# contract, and the validated instance is our answer.
# ---------------------------------------------------------------------------


class _SuggestCategoryOutput(BaseModel):
    category_id: Optional[int] = Field(
        description=(
            "ID of the best matching category from the list, "
            "or null if no category is a reasonable fit"
        )
    )
    confidence: float = Field(description="Confidence score from 0.0 to 1.0")
    suggested_rule: Optional[str] = Field(
        description=(
            "Python regex (re.search style) to save as a rule for similar future transactions. "
            "Prefix with (?i) for case-insensitive matching. Null if unsure."
        )
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def suggest(note: str, amount_minor: int, db: Session) -> CategorizeSuggestResponse:
    """
    Return a category suggestion for a single transaction note.

    Checks saved rules first (no AI call). Falls back to LLM only when
    no rule matches. The LLM call uses with_structured_output, so we always
    get a validated _SuggestCategoryOutput back — not free text.
    """
    rules = _load_rules(db)
    rule_match = _match_rule(note, rules, db)
    if rule_match:
        return rule_match

    categories = _load_categories(db)
    return _suggest_with_llm(note, amount_minor, categories)


def suggest_batch(
    rows: list[CategorizeSuggestRequest], db: Session
) -> list[CategorizeSuggestResponse]:
    """
    Return one suggestion per row, in the same order as the input.

    Rules are loaded once for the whole batch (one DB query, not N).
    Categories are loaded lazily — only if at least one row needs the LLM.
    This means a 200-row import where 150 rows hit rules makes only ~50 LLM calls.
    """
    rules = _load_rules(db)
    categories: Optional[list[Category]] = None  # loaded lazily on first LLM miss

    results = []
    for row in rows:
        match = _match_rule(row.note, rules, db)
        if match:
            results.append(match)
            continue

        # Rule miss — need the LLM. Load categories once on the first miss.
        if categories is None:
            categories = _load_categories(db)

        categorizeSuggestResponse = _suggest_with_llm(row.note, row.amount_minor, categories)
        results.append(categorizeSuggestResponse)

    return results


def accept_rule(data: CategorizeAcceptRequest, db: Session) -> CategorizationRule:
    """
    Save a new categorization rule and optionally apply it to an existing transaction.

    The pattern is saved as-is — callers are responsible for providing a valid
    Python regex. The suggested_rule from the suggest response is a safe value to pass.
    If transaction_id is provided, that transaction's category_id is also updated now.
    """
    category = db.get(Category, data.category_id)
    if category is None:
        raise HTTPException(
            status_code=404, detail=f"Category with ID: {data.category_id} not found."
        )

    rule = CategorizationRule(
        pattern=data.pattern,
        field="note",
        category_id=data.category_id,
        priority=data.priority,
    )
    db.add(rule)

    if data.transaction_id is not None:
        txn = db.get(Transaction, data.transaction_id)
        if txn is None:
            raise HTTPException(
                status_code=404, detail=f"Transaction {data.transaction_id} not found."
            )
        txn.category_id = data.category_id

    db.commit()
    db.refresh(rule)
    return rule


def list_rules(db: Session) -> list[CategorizationRule]:
    """Return all rules ordered by priority descending (highest priority first)."""
    return (
        db.query(CategorizationRule)
        .order_by(CategorizationRule.priority.desc(), CategorizationRule.id.asc())
        .all()
    )


def delete_rule(rule_id: int, db: Session) -> None:
    """Hard-delete a rule. Raises 404 if not found."""
    rule = db.get(CategorizationRule, rule_id)
    if rule is None:
        raise HTTPException(status_code=404, detail=f"Rule {rule_id} not found.")
    db.delete(rule)
    db.commit()


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _load_rules(db: Session) -> list[CategorizationRule]:
    """Load all rules ordered by priority — called once per request or batch."""
    return (
        db.query(CategorizationRule)
        .order_by(CategorizationRule.priority.desc(), CategorizationRule.id.asc())
        .all()
    )


def _load_categories(db: Session) -> list[Category]:
    """Load all active (non-archived) categories for the LLM context."""
    return db.query(Category).filter(Category.archived.is_(False)).all()


def _match_rule(
    note: str,
    rules: list[CategorizationRule],
    db: Session,
) -> Optional[CategorizeSuggestResponse]:
    """
    Test each rule's regex against the note in priority order.
    Returns a response on the first match, or None if no rule fires.
    re.search() is used so the pattern doesn't need to anchor to the start.
    """
    for rule in rules:
        try:
            if re.search(rule.pattern, note or "", re.IGNORECASE):
                category = db.get(Category, rule.category_id)
                if category is None:
                    # Rule points to a deleted category — skip it. Only possible if
                    # the category was deleted after we loaded the rules but before
                    # we reached here.
                    continue
                return CategorizeSuggestResponse(
                    category_id=rule.category_id,
                    category_name=category.name,
                    confidence=1.0,
                    suggested_rule=None,
                    source="rule",
                )
        except re.error:
            # A badly-formed regex in the DB should never crash the app —
            # just skip it and try the next rule.
            continue
    return None


def _suggest_with_llm(
    note: str,
    amount_minor: int,
    categories: list[Category],
) -> CategorizeSuggestResponse:
    """
    Ask the configured LLM for a category suggestion when no rule matched.

    Routing goes through the get_llm() factory, so which provider and model are
    used is purely a config concern — this code stays provider-agnostic and never
    names an LLM. get_llm() also attaches the audit callback, so we don't pass a
    DB session here; the ai_calls row is written by AuditCallbackHandler on its
    own session when the call returns.

    with_structured_output() makes LangChain force a tool/JSON schema derived from
    _SuggestCategoryOutput, so .invoke() hands us back a validated instance of
    that model rather than free text.
    """
    llm = get_llm(feature="categorize", provider="groq")
    structured = llm.with_structured_output(_SuggestCategoryOutput)

    # Plain-text system prompt: the static instructions followed by the category
    # list. Kept provider-agnostic on purpose — no provider-specific hints (e.g.
    # prompt-cache markers) leak into feature code; that's the factory's concern.
    system = SystemMessage(
        content=f"{_SYSTEM_PROMPT}\n\n{_format_categories(categories)}"
    )
    human = HumanMessage(
        content=(
            f"Transaction note: {note or '(no note)'}\n"
            f"Amount: ₹{amount_minor / 100:.2f}"
        )
    )

    result: _SuggestCategoryOutput = structured.invoke([system, human])

    cat_id = result.category_id
    return CategorizeSuggestResponse(
        category_id=cat_id,
        category_name=_category_name(cat_id, categories),
        confidence=float(result.confidence),
        suggested_rule=result.suggested_rule,
        source="llm",
    )


def _format_categories(categories: list[Category]) -> str:
    """
    Format the category list as a stable string for the LLM system prompt.

    Stable = same categories always produce the same string, so the prompt
    cache stays valid across calls. We include the ID (what the LLM must return),
    the name, the kind, and the parent name for context.
    """
    by_id = {c.id: c for c in categories}
    lines = ["Available categories (ID | Name | Kind | Parent):"]
    for cat in sorted(categories, key=lambda c: (c.kind, c.name)):
        parent_name = by_id[cat.parent_id].name if cat.parent_id else "—"
        lines.append(f"{cat.id} | {cat.name} | {cat.kind} | {parent_name}")
    return "\n".join(lines)


def _category_name(category_id: Optional[int], categories: list[Category]) -> Optional[str]:
    """Look up a category name by ID from the in-memory list."""
    if category_id is None:
        return None
    for cat in categories:
        if cat.id == category_id:
            return cat.name
    return None

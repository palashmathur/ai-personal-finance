# Business logic for natural-language transaction entry (Layer 2).
#
# One sentence in ("spent 1200 on groceries yesterday"), one structured draft out.
# We do a single LLM call to *extract* fields, then resolve every number, date and
# ID in plain Python. The model never does arithmetic and never invents an ID — it
# only picks names from the closed lists we hand it (the same trick categorize uses).
#
# This service does NOT insert anything. It returns a draft the frontend shows on a
# confirm card; the user reviews/edits and then POSTs to /api/transactions to save.
#
# Provider-agnostic by rule: which provider/model runs is decided by config via the
# get_llm() factory. Nothing here names an LLM. The ai_calls audit row and LangSmith
# trace are attached automatically inside get_llm(feature="nl_input").

from datetime import date
from pathlib import Path
from typing import Optional

from fastapi import HTTPException
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.ai.llm import get_llm
from app.models import Account, Category
from app.schemas.nl_input_schema import NLEntryResponse, NLInputRequest
from app.services import categorize
from app.services.accounts_service import list_accounts

# ---------------------------------------------------------------------------
# System prompt — loaded once at import, same as categorize.
# ---------------------------------------------------------------------------

_PROMPT_PATH = Path(__file__).parent.parent / "ai" / "prompts" / "nl_input.md"
_SYSTEM_PROMPT = _PROMPT_PATH.read_text(encoding="utf-8")

# The two kinds a manual cash entry can be. Transfers aren't an NL target — they
# need two accounts and a different flow, so the parser only ever returns these.
_VALID_KINDS = {"income", "expense"}


# ---------------------------------------------------------------------------
# Structured output schema.
#
# Handed to with_structured_output(): LangChain turns this into a tool/JSON schema
# and forces the model to fill it, so .invoke() returns a validated _NLParse instead
# of free text. Every field is what the model *saw* in the sentence — the raw figure,
# the words, the chosen names — not a resolved value. The resolution happens below.
# ---------------------------------------------------------------------------
class _NLParse(BaseModel):
    kind: str = Field(description="Either 'income' or 'expense'.")
    amount: Optional[float] = Field(
        description="The rupee figure exactly as written in the sentence, e.g. 1200. Null if none."
    )
    occurred_on: Optional[str] = Field(
        description="ISO date (YYYY-MM-DD) the money moved, relative words resolved. Null if none."
    )
    account_name: Optional[str] = Field(
        description="Exact name of an account from the provided list, or null if none fits."
    )
    category_name: Optional[str] = Field(
        description="Exact name of a category from the provided list, or null if none fits."
    )
    note: str = Field(description="Short, clean description of the transaction.")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def parse_nl_entry(db: Session, nl_input_request: NLInputRequest) -> NLEntryResponse:
    """
    Parse a free-text sentence into a draft transaction for the confirm card.

    Steps:
      1. Validate default_account_id up front — it's our fallback, so it must exist.
      2. Load the active accounts + categories as a closed list for the model.
      3. One LLM call extracts the raw fields.
      4. Resolve amount (→ paise), date (→ ISO, default today), account (→ id),
         and category (→ id) in Python. Unknown category falls back to the
         auto-categorizer so the card still gets a suggestion.

    Raises 422 when default_account_id doesn't exist or no amount was found.
    """
    # The default account is what we fall back to when the sentence names no account
    # (or names one we don't have). If it's bogus there's nothing safe to draft against.
    default_account = db.get(Account, nl_input_request.default_account_id)
    if default_account is None:
        raise HTTPException(
            status_code=422,
            detail=f"default_account_id {nl_input_request.default_account_id} does not exist.",
        )

    accounts = list_accounts(db, include_archived=False)
    categories = _load_categories(db)

    # Pass today in so the model can turn "yesterday"/"for May" into a real ISO date.
    today = date.today()
    parsed = _extract_fields_with_llm(nl_input_request.text, accounts, categories, today)

    # --- kind ---------------------------------------------------------------
    # The prompt asks for income|expense. If the model ever returns something else,
    # fall back to "expense" (by far the common case) — the user confirms anyway.
    kind = (parsed.kind or "").strip().lower()
    if kind not in _VALID_KINDS:
        kind = "expense"

    # --- amount -------------------------------------------------------------
    # No amount means we can't draft a transaction at all — surface a clear 422.
    if parsed.amount is None:
        raise HTTPException(
            status_code=422,
            detail="Could not find an amount in the text. Please include how much.",
        )
    # paise = rupees × 100. round() guards against float drift (12.1 * 100 = 1209.9999…).
    amount_minor = round(parsed.amount * 100)
    if amount_minor <= 0:
        raise HTTPException(
            status_code=422,
            detail="Amount must be greater than zero.",
        )

    # --- date ---------------------------------------------------------------
    occurred_on = _resolve_date(parsed.occurred_on, today)

    # --- account ------------------------------------------------------------
    # Match the model's chosen name against our list; fall back to the default account.
    account = _match_account(parsed.account_name, accounts) or default_account

    # --- category -----------------------------------------------------------
    note = parsed.note or nl_input_request.text
    category_id, category_name, category_source, confidence = _resolve_category(
        parsed.category_name, kind, note, categories, db
    )

    return NLEntryResponse(
        kind=kind,
        amount_minor=amount_minor,
        occurred_on=occurred_on,
        account_id=account.id,
        account_name=account.name,
        category_id=category_id,
        category_name=category_name,
        category_source=category_source,
        category_confidence=confidence,
        note=note,
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _extract_fields_with_llm(
    text: str,
    accounts: list[Account],
    categories: list[Category],
    today: date,
) -> _NLParse:
    """
    Single structured-extraction call to the LLM. The system message carries the static
    instructions, today's date, and the closed account/category lists; the human
    message is just the user's sentence. with_structured_output() hands us back a
    validated _NLParse, so there's nothing to parse out of free text.
    """
    llm = get_llm(feature="nl_input", provider="groq")
    structured = llm.with_structured_output(_NLParse)

    # Reuse categorize's category formatter so the two AI features describe the
    # category list to the model identically — one place to change the format.
    system = SystemMessage(
        content=(
            f"{_SYSTEM_PROMPT}\n\n"
            f"Today's date is {today.isoformat()}.\n\n"
            f"{_format_accounts(accounts)}\n\n"
            f"{categorize.format_categories(categories)}"
        )
    )
    human = HumanMessage(content=text)

    result: _NLParse = structured.invoke([system, human])
    return result


def _resolve_date(raw: Optional[str], today: date) -> date:
    """
    Turn the model's ISO string into a real date. Defaults to today when the model
    returned nothing, and also when it returned something that won't parse — we never
    let a malformed date from the model crash the request.
    """
    if not raw:
        return today
    try:
        return date.fromisoformat(raw.strip())
    except (ValueError, AttributeError):
        return today


def _match_account(name: Optional[str], accounts: list[Account]) -> Optional[Account]:
    """Case-insensitive name match against the active accounts. None if no name or no hit."""
    if not name:
        return None
    target = name.strip().lower()
    for acc in accounts:
        if acc.name.strip().lower() == target:
            return acc
    return None


def _resolve_category(
    name: Optional[str],
    kind: str,
    note: str,
    categories: list[Category],
    db: Session,
) -> tuple[Optional[int], Optional[str], str, Optional[float]]:
    """
    Resolve a category for the draft, returning (id, name, source, confidence).

    First try an exact name match within the right kind (income categories for income,
    expense for expense). On a miss, fall back to the user's saved rules ONLY — not the
    auto-categorizer's LLM. The model already saw the same category list and returned no
    match, so a second LLM call over that same list is redundant cost; the rules, though,
    are the user's learned corrections the model never sees, so they're worth checking.
    We keep a rule's category only if its kind matches our draft, otherwise the save
    endpoint would reject it (it enforces category.kind == txn kind).
    """
    # 1. Exact match from the closed list, constrained to the chosen kind.
    if name:
        target = name.strip().lower()
        for cat in categories:
            if cat.kind == kind and cat.name.strip().lower() == target:
                return cat.id, cat.name, "matched", 1.0

    # 2. Rules-only fallback — no LLM call. Picks up "Swiggy → Dining Out" style rules.
    suggestion = categorize.suggest_from_rules(note, db)
    if suggestion is not None and suggestion.category_id is not None:
        # Only trust it if the rule's category is the same kind as our draft.
        suggested = next(
            (c for c in categories if c.id == suggestion.category_id), None
        )
        if suggested is not None and suggested.kind == kind:
            return (
                suggestion.category_id,
                suggestion.category_name,
                suggestion.source,
                suggestion.confidence,
            )

    # 3. Nothing usable — leave the category blank for the user to pick on the card.
    return None, None, "none", None


def _load_categories(db: Session) -> list[Category]:
    """Load all active (non-archived) categories — the closed list for the model."""
    return db.query(Category).filter(Category.archived.is_(False)).all()


def _format_accounts(accounts: list[Account]) -> str:
    """
    Stable, sorted account list for the prompt. The model returns a name from here;
    we resolve it back to an ID. Sorting keeps the prompt text stable across calls.
    """
    lines = ["Available accounts (Name | Type):"]
    for acc in sorted(accounts, key=lambda a: a.name):
        lines.append(f"{acc.name} | {acc.type}")
    return "\n".join(lines)

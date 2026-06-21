# Pydantic schemas for the auto-categorize endpoints.
# Covers suggest (single + batch), accept (save a rule), and rule management.

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class CategorizeSuggestRequest(BaseModel):
    """
    Input for a single categorization suggestion.
    Send the raw transaction note and amount; get back a category suggestion.
    """

    note: str
    amount_minor: int  # in paise


class CategorizeSuggestResponse(BaseModel):
    """
    The categorization suggestion returned by the suggest endpoints.

    source="rule"  → matched a saved regex rule instantly; no AI call was made.
    source="llm"   → no rule matched; the LLM was asked.

    category_id is null when no suitable category was found (the LLM returned null
    rather than guess — better than a wrong category silently applied).
    """

    category_id: Optional[int]
    category_name: Optional[str]
    confidence: float
    suggested_rule: Optional[str]  # regex pattern the user can save as a rule
    source: str  # "rule" | "llm"


class CategorizeBatchRequest(BaseModel):
    """
    Input for batch categorization — used by the CSV import preview step.
    Send up to N rows; get back one suggestion per row in the same order.
    """

    rows: list[CategorizeSuggestRequest]


class CategorizeAcceptRequest(BaseModel):
    """
    Save a categorization rule after accepting a suggestion.

    pattern     — the regex to save (usually the suggested_rule from the suggest response).
    category_id — the category this pattern should map to.
    priority    — higher = checked first. Default 0 is fine for most rules.
    transaction_id — if provided, also updates that transaction's category_id right now.
    """

    pattern: str
    category_id: int
    priority: int = 0
    transaction_id: Optional[int] = None


class CategorizeRuleResponse(BaseModel):
    """
    A single saved categorization rule, as returned by the list-rules endpoint.
    """

    model_config = {"from_attributes": True}

    id: int
    pattern: str
    field: str
    category_id: int
    category_name: str
    priority: int
    created_at: datetime

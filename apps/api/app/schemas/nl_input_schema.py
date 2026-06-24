# Pydantic schemas for the natural-language input endpoint (POST /api/ai/nl-input).
#
# This feature turns a free-text sentence into a *draft* transaction that the
# frontend shows on a confirm card. Nothing is inserted here — the request goes
# in as plain text, the response comes back as a ready-to-confirm entry.

from datetime import date
from typing import Optional

from pydantic import BaseModel


class NLInputRequest(BaseModel):
    """
    Input for the NL parser.

    text               — the sentence the user typed, e.g. "spent 1200 on groceries yesterday".
    default_account_id — the account to fall back to when the sentence doesn't name one
                         (usually the account the user currently has selected in the UI).
    """

    text: str
    default_account_id: int


class NLEntryResponse(BaseModel):
    """
    A parsed draft transaction — everything the confirm card needs to pre-fill the form.

    All numbers and dates here are computed in Python, never by the model: the LLM only
    extracts the raw figure/words, and this service turns them into amount_minor (paise),
    an ISO date, and resolved account/category IDs.

    category_id can be null when nothing fit — neither the model's pick nor a saved rule —
    in which case the card shows an empty category for the user to pick. category_source
    records how we arrived at the category so the UI can hint at it:
        "matched" → the model picked a category that exists in the list.
        "rule"    → the model found nothing, but a saved categorization rule fired.
        "none"    → no category could be resolved; the user picks one on the card.
    """

    kind: str  # "income" | "expense"
    amount_minor: int  # in paise
    occurred_on: date
    account_id: int
    account_name: str
    category_id: Optional[int]
    category_name: Optional[str]
    category_source: str  # "matched" | "rule" | "none"
    category_confidence: Optional[float]
    note: str

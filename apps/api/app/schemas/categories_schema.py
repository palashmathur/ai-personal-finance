# Pydantic schemas for the Categories resource.
# Categories are a two-level tree: a parent has children, a child belongs to one parent.
# The depth limit (max 2 levels) is enforced in the service layer, not the schema.
#
# Think of these as your Spring Boot DTOs — what the API accepts and what it returns,
# decoupled from the SQLAlchemy ORM model.

from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict


class CategoryKind(str, Enum):
    """
    Whether this category classifies income or expense transactions.
    A child's kind must always match its parent's — you can't put a Salary
    subcategory under a Food parent. Enforced in the service layer.
    """

    income = "income"
    expense = "expense"


class CategoryCreate(BaseModel):
    """
    Request body for POST /api/categories.
    Leave parent_id as null to create a top-level (parent) category.
    Set parent_id to an existing parent's id to create a subcategory (child).
    """

    name: str
    kind: CategoryKind
    parent_id: Optional[int] = None
    # Hex color used in chart slices and chips. e.g. "#3b82f6".
    # If omitted, the UI derives one from a hash of the name.
    color: Optional[str] = None
    # Lucide icon name for the UI. e.g. "utensils-crossed". Purely cosmetic.
    icon: Optional[str] = None


class CategoryUpdate(BaseModel):
    """
    Request body for PATCH /api/categories/{id}.
    All fields are optional — only the ones you include are changed.

    Setting archived=True soft-deletes the category (and cascades to its children).
    Setting archived=False restores it (children stay archived — restore them individually).
    """

    model_config = ConfigDict(extra="ignore")

    name: Optional[str] = None
    kind: Optional[CategoryKind] = None
    parent_id: Optional[int] = None
    color: Optional[str] = None
    icon: Optional[str] = None
    archived: Optional[bool] = None


class CategoryChildResponse(BaseModel):
    """
    Response shape for a child (leaf) category.
    No `children` field here because children cannot have children — max depth is 2.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    kind: CategoryKind
    parent_id: int  # always set on a child
    color: Optional[str]
    icon: Optional[str]
    archived: bool


class CategoryResponse(BaseModel):
    """
    Response shape for any category, with children embedded.
    Used by GET /api/categories (parents have children populated, children have []).
    Also used by POST and PATCH — parent_id will be None for roots, int for children.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    kind: CategoryKind
    parent_id: Optional[int]  # None for root categories, set for children
    color: Optional[str]
    icon: Optional[str]
    archived: bool
    children: list[CategoryChildResponse] = []


class CategoryDeleteResponse(BaseModel):
    """
    Response body for DELETE /api/categories/{id}.
    Returns how many transactions were updated to category_id=NULL as a result
    of the deletion, so the caller knows how many items are now "Uncategorized".
    """

    id: int
    name: str
    # Number of transactions whose category_id was set to NULL by this delete.
    # The transactions themselves are untouched — only their category reference is cleared.
    deleted_transactions_count: int

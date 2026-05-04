# FastAPI router for the Categories resource.
# Pure HTTP plumbing — validates the request, calls the service, returns the response.
# Think of this as your Spring Boot @RestController for categories.

from typing import Optional

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.categories_schema import (
    CategoryCreate,
    CategoryDeleteResponse,
    CategoryResponse,
    CategoryUpdate,
)
from app.services import categories_service

router = APIRouter(prefix="/api/categories", tags=["categories"])


@router.get("", response_model=list[CategoryResponse])
def list_categories(
    kind: Optional[str] = None,
    archived: bool = False,
    db: Session = Depends(get_db),
):
    """
    List all parent categories, each with their children embedded.

    Optional filters:
    - ?kind=income   — only income categories (useful for the income transaction form)
    - ?kind=expense  — only expense categories (useful for the expense transaction form)
    - ?archived=true — include soft-deleted categories
    """
    return categories_service.list_categories(db, kind=kind, include_archived=archived)


@router.post("", response_model=CategoryResponse, status_code=status.HTTP_201_CREATED)
def create_category(data: CategoryCreate, db: Session = Depends(get_db)):
    """
    Create a new category.

    - Leave parent_id null to create a top-level (parent) category.
    - Set parent_id to create a subcategory. The child's kind must match the parent's.
    - Returns 422 if kind mismatches or parent is itself a child.
    - Returns 409 if a category with the same name + kind + parent already exists.

    Note: the response is always CategoryResponse (with a children field), but a
    newly created child will be returned wrapped in its parent context only via GET.
    For POST we return the created row directly — the children array will be empty.
    """
    category = categories_service.create_category(db, data)
    # Attach an empty children list so the CategoryResponse schema validates cleanly.
    # A newly created category has no children yet.
    category.children = []
    return category


@router.patch("/{category_id}", response_model=CategoryResponse)
def update_category(
    category_id: int, data: CategoryUpdate, db: Session = Depends(get_db)
):
    """
    Partially update a category.

    - Setting archived=true soft-deletes it and cascades to all its children.
    - Setting archived=false restores only this category (children stay archived).
    - Changing parent_id is validated for cycles, depth, and kind mismatch.
    """
    category = categories_service.update_category(db, category_id, data)
    # Re-attach children for the response so the schema validates correctly.
    from app.models import Category as CategoryModel

    category.children = (
        db.query(CategoryModel)
        .filter(CategoryModel.parent_id == category_id)
        .all()
    )
    return category


@router.delete(
    "/{category_id}",
    response_model=CategoryDeleteResponse,
    status_code=status.HTTP_200_OK,
)
def delete_category(category_id: int, db: Session = Depends(get_db)):
    """
    Hard-delete a category.

    - Returns 409 if the category has children. Delete or archive them first.
    - On success, returns the count of transactions that are now "Uncategorized"
      (their category_id was set to NULL automatically by the DB).
    - The transactions themselves are untouched — only their category reference is cleared.
    """
    return categories_service.delete_category(db, category_id)

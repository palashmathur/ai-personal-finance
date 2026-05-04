# Business logic for the Categories resource.
# Pure functions only — no FastAPI imports, no HTTP concerns.
# Think of this as your Spring Boot @Service class.
#
# Categories are a two-level tree. All depth and cycle rules are enforced here,
# not at the DB level (SQLite can't enforce depth, only FK existence).

from typing import Optional

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import Category, Transaction
from app.schemas.categories_schema import (
    CategoryCreate,
    CategoryDeleteResponse,
    CategoryUpdate,
)


def list_categories(
    db: Session,
    kind: Optional[str] = None,
    include_archived: bool = False,
) -> list[Category]:
    """
    Return all parent categories, each with their children embedded.

    We fetch all rows in one query, then stitch the tree in Python.
    For a single-user app with < 100 categories, this is faster than
    multiple queries or a self-join — and the code stays easy to follow.

    Filtering by kind is useful for dropdowns: the transaction form only
    needs income categories for income entries, and expense categories for expenses.
    """
    query = db.query(Category)
    if kind is not None:
        query = query.filter(Category.kind == kind)
    if not include_archived:
        query = query.filter(Category.archived == False)  # noqa: E712

    all_cats = query.order_by(Category.id).all()

    # Separate roots from children, then attach children to their parents.
    # This gives the nested structure the API response needs without extra SQL.
    parents = [c for c in all_cats if c.parent_id is None]
    children_by_parent: dict[int, list[Category]] = {}
    for c in all_cats:
        if c.parent_id is not None:
            children_by_parent.setdefault(c.parent_id, []).append(c)

    # Attach the children list as a transient attribute so Pydantic can read it.
    # SQLAlchemy models are plain Python objects — setting extra attributes is fine.
    for parent in parents:
        parent.children = children_by_parent.get(parent.id, [])

    return parents


def get_category_or_404(db: Session, category_id: int) -> Category:
    """
    Fetch a single category by ID. Raises 404 if it doesn't exist.
    Used internally so update and delete share the same not-found logic.
    """
    category = db.get(Category, category_id)
    if category is None:
        raise HTTPException(status_code=404, detail=f"Category {category_id} not found.")
    return category


def _check_duplicate(
    db: Session,
    name: str,
    kind: str,
    parent_id: Optional[int],
    exclude_id: Optional[int] = None,
) -> None:
    """
    Raise 409 if a category with the same name (case-insensitive), kind, and
    parent_id already exists. exclude_id is used during updates to skip the
    category being updated itself.
    """
    query = db.query(Category).filter(
        func.lower(Category.name) == func.lower(name),
        Category.kind == kind,
        Category.parent_id == parent_id,
    )
    if exclude_id is not None:
        query = query.filter(Category.id != exclude_id)

    existing = query.first()
    if existing is not None:
        level = "child" if parent_id else "parent"
        raise HTTPException(
            status_code=409,
            detail=(
                f"A {level} category named '{existing.name}' of kind '{existing.kind}' "
                f"already exists (id={existing.id})."
            ),
        )


def _validate_parent(db: Session, parent_id: int, child_kind: str) -> Category:
    """
    Validate that a given parent_id is a legitimate parent to attach a child to.
    Three rules enforced here:
    1. Parent must exist.
    2. Parent must be a root category (parent_id=NULL) — enforces the 2-level depth limit.
    3. Child's kind must match parent's kind — you can't nest income under an expense parent.
    """
    parent = db.get(Category, parent_id)
    if parent is None:
        raise HTTPException(status_code=404, detail=f"Parent category {parent_id} not found.")

    # Rule 2: reject if the "parent" is itself a child — this would create a 3rd level.
    if parent.parent_id is not None:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Category '{parent.name}' is already a child category and cannot be "
                f"used as a parent. Maximum tree depth is 2 levels."
            ),
        )

    # Rule 3: kind must match so income and expense categories never mix.
    if parent.kind != child_kind:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Kind mismatch: parent '{parent.name}' is '{parent.kind}' "
                f"but child kind is '{child_kind}'. They must match."
            ),
        )

    return parent


def create_category(db: Session, data: CategoryCreate) -> Category:
    """
    Create a new category — either a root (parent_id=None) or a child (parent_id set).

    Validation order:
    1. If parent_id given: validate parent exists, is a root, and kind matches.
    2. Check for duplicate name+kind+parent_id.
    3. Insert.
    """
    if data.parent_id is not None:
        _validate_parent(db, data.parent_id, data.kind.value)

    _check_duplicate(db, data.name, data.kind.value, data.parent_id)

    category = Category(
        name=data.name,
        kind=data.kind.value,
        parent_id=data.parent_id,
        color=data.color,
        icon=data.icon,
    )
    db.add(category)
    db.commit()
    db.refresh(category)
    return category


def update_category(db: Session, category_id: int, data: CategoryUpdate) -> Category:
    """
    Partially update a category. Enforces cycle prevention and kind rules when
    parent_id is being changed, and cascades archive status to children.

    Cycle / depth rules when parent_id is in the payload:
    - Cannot set parent_id to self (direct cycle).
    - Cannot set parent_id to a category that already has a parent (depth > 2).
    - Cannot make a category a child if it already has children of its own
      (those children would become grandchildren, violating the 2-level limit).

    Archive cascade:
    - archived=True  → archive the category AND all its children.
    - archived=False → restore only this category; children stay archived.
    """
    category = get_category_or_404(db, category_id)
    updates = data.model_dump(exclude_unset=True)

    # --- parent_id change: cycle and depth checks ---
    if "parent_id" in updates and updates["parent_id"] is not None:
        new_parent_id = updates["parent_id"]

        # Cannot set parent to self.
        if new_parent_id == category_id:
            raise HTTPException(
                status_code=422,
                detail="A category cannot be its own parent.",
            )

        # Cannot become a child if it already has children (depth violation).
        has_children = (
            db.query(Category).filter(Category.parent_id == category_id).first()
        ) is not None
        if has_children:
            raise HTTPException(
                status_code=422,
                detail=(
                    f"Category '{category.name}' has children and cannot be made a child itself. "
                    f"It would push its children to a 3rd level which is not allowed."
                ),
            )

        # Validate the new parent (exists, is a root, kind matches).
        new_kind = updates.get("kind", category.kind)
        if hasattr(new_kind, "value"):
            new_kind = new_kind.value
        _validate_parent(db, new_parent_id, new_kind)

    # --- kind change: re-validate against existing parent if still a child ---
    if "kind" in updates and category.parent_id is not None:
        new_kind = updates["kind"]
        if hasattr(new_kind, "value"):
            new_kind = new_kind.value
        parent_id_to_check = updates.get("parent_id", category.parent_id)
        _validate_parent(db, parent_id_to_check, new_kind)

    # --- archive cascade ---
    if updates.get("archived") is True:
        # Archive all children of this category in the same commit.
        db.query(Category).filter(Category.parent_id == category_id).update(
            {"archived": True}
        )

    # Apply updates to the category itself.
    for field, value in updates.items():
        if hasattr(value, "value"):
            value = value.value
        setattr(category, field, value)

    db.commit()
    db.refresh(category)
    return category


def delete_category(db: Session, category_id: int) -> CategoryDeleteResponse:
    """
    Hard-delete a category. Returns how many transactions are now "Uncategorized"
    as a result of the deletion.

    Rejects with 409 if the category has children — delete or archive children first.

    The actual nulling of transactions.category_id is handled automatically by SQLite's
    ON DELETE SET NULL constraint on the transactions.category_id FK. We count
    affected transactions BEFORE deleting so we can report the number back.
    """
    category = get_category_or_404(db, category_id)

    # Cannot delete a parent that still has children — the children would become orphans
    # with a parent_id pointing to a non-existent row, breaking the tree structure.
    children_count = (
        db.query(Category).filter(Category.parent_id == category_id).count()
    )
    if children_count > 0:
        raise HTTPException(
            status_code=409,
            detail=(
                f"Cannot delete category '{category.name}': it has {children_count} "
                f"child categor{'y' if children_count == 1 else 'ies'}. "
                f"Delete or archive the children first."
            ),
        )

    # Count referencing transactions before we delete, so the count is still accurate.
    # After deletion, those rows will have category_id=NULL and we can't identify them anymore.
    affected_count = (
        db.query(Transaction).filter(Transaction.category_id == category_id).count()
    )

    category_name = category.name
    db.delete(category)
    db.commit()
    # ON DELETE SET NULL has now run — transactions.category_id is NULL for affected rows.

    return CategoryDeleteResponse(
        id=category_id,
        name=category_name,
        deleted_transactions_count=affected_count,
    )

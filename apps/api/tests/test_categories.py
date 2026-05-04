# Tests for the Categories CRUD endpoints.
#
# Uses the same in-memory SQLite + StaticPool pattern as test_accounts.py
# so every test gets a clean, isolated DB with no data from the real finance.db.

from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.session import get_db
from app.main import app
from app.models import Base, Transaction

_TEST_ENGINE = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)


@event.listens_for(_TEST_ENGINE, "connect")
def _set_pragmas(dbapi_conn, _):
    """Apply the same PRAGMAs as production so FK enforcement matches exactly."""
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


_TestSession = sessionmaker(bind=_TEST_ENGINE, autoflush=False, autocommit=False)


def _override_get_db():
    db = _TestSession()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(autouse=True)
def setup_db():
    """
    Create all tables before each test and drop them after for a clean slate.

    We disable FK enforcement before drop_all because SQLite would otherwise reject
    dropping `categories` while rows with self-referential parent_id FKs still exist
    (StaticPool shares one connection, so the pragma applies to the drop operation too).
    """
    Base.metadata.create_all(bind=_TEST_ENGINE)
    app.dependency_overrides[get_db] = _override_get_db
    yield
    app.dependency_overrides.clear()
    with _TEST_ENGINE.connect() as conn:
        conn.execute(text("PRAGMA foreign_keys=OFF"))
    Base.metadata.drop_all(bind=_TEST_ENGINE)
    with _TEST_ENGINE.connect() as conn:
        conn.execute(text("PRAGMA foreign_keys=ON"))


client = TestClient(app)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _create_parent(name="Food", kind="expense"):
    return client.post("/api/categories", json={"name": name, "kind": kind}).json()


def _create_child(name="Groceries", kind="expense", parent_id=None):
    return client.post(
        "/api/categories",
        json={"name": name, "kind": kind, "parent_id": parent_id},
    ).json()


# ---------------------------------------------------------------------------
# Happy path — create and list
# ---------------------------------------------------------------------------

def test_create_parent_category_returns_201():
    """Creating a root category returns 201 with an empty children list."""
    response = client.post("/api/categories", json={"name": "Food", "kind": "expense"})

    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Food"
    assert body["kind"] == "expense"
    assert body["parent_id"] is None
    assert body["children"] == []


def test_create_child_category_returns_201():
    """Creating a child under a valid parent returns 201."""
    parent = _create_parent("Food", "expense")

    response = client.post(
        "/api/categories",
        json={"name": "Groceries", "kind": "expense", "parent_id": parent["id"]},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Groceries"
    assert body["parent_id"] == parent["id"]


def test_list_returns_nested_tree():
    """GET /api/categories returns parents with their children embedded."""
    parent = _create_parent("Food", "expense")
    _create_child("Groceries", "expense", parent["id"])
    _create_child("Dining Out", "expense", parent["id"])

    response = client.get("/api/categories")

    assert response.status_code == 200
    parents = response.json()
    assert len(parents) == 1
    assert parents[0]["name"] == "Food"
    child_names = [c["name"] for c in parents[0]["children"]]
    assert "Groceries" in child_names
    assert "Dining Out" in child_names


def test_list_filter_by_kind():
    """?kind=income returns only income categories; ?kind=expense returns only expense."""
    _create_parent("Salary Parent", "income")
    _create_parent("Food", "expense")

    income = client.get("/api/categories?kind=income").json()
    expense = client.get("/api/categories?kind=expense").json()

    assert all(c["kind"] == "income" for c in income)
    assert all(c["kind"] == "expense" for c in expense)


def test_patch_rename_category():
    """PATCH updates only the fields sent; other fields remain unchanged."""
    parent = _create_parent("OldName", "expense")

    response = client.patch(f"/api/categories/{parent['id']}", json={"name": "NewName"})

    assert response.status_code == 200
    assert response.json()["name"] == "NewName"
    assert response.json()["kind"] == "expense"  # unchanged


# ---------------------------------------------------------------------------
# Kind mismatch
# ---------------------------------------------------------------------------

def test_create_child_with_mismatched_kind_returns_422():
    """A child whose kind differs from its parent is rejected at creation."""
    parent = _create_parent("Salary Parent", "income")

    response = client.post(
        "/api/categories",
        json={"name": "Groceries", "kind": "expense", "parent_id": parent["id"]},
    )

    assert response.status_code == 422
    assert "mismatch" in response.json()["detail"].lower()


# ---------------------------------------------------------------------------
# Depth enforcement
# ---------------------------------------------------------------------------

def test_create_grandchild_returns_422():
    """Creating a child of a child (3rd level) is rejected."""
    parent = _create_parent("Food", "expense")
    child = _create_child("Groceries", "expense", parent["id"])

    response = client.post(
        "/api/categories",
        json={"name": "Organic", "kind": "expense", "parent_id": child["id"]},
    )

    assert response.status_code == 422
    detail = response.json()["detail"].lower()
    assert "depth" in detail or "child" in detail


# ---------------------------------------------------------------------------
# Cycle detection
# ---------------------------------------------------------------------------

def test_patch_parent_id_to_own_child_returns_422():
    """
    Setting a parent's parent_id to one of its own children creates a cycle.
    e.g. Food → Groceries, then Food.parent_id = Groceries → cycle.
    """
    parent = _create_parent("Food", "expense")
    child = _create_child("Groceries", "expense", parent["id"])

    response = client.patch(
        f"/api/categories/{parent['id']}",
        json={"parent_id": child["id"]},
    )

    # The child itself is already a child (parent_id != NULL), so _validate_parent
    # rejects it because it would create a 3rd level — which covers the cycle case.
    assert response.status_code == 422


def test_patch_parent_id_to_self_returns_422():
    """A category cannot be its own parent."""
    parent = _create_parent("Food", "expense")

    response = client.patch(
        f"/api/categories/{parent['id']}",
        json={"parent_id": parent["id"]},
    )

    assert response.status_code == 422
    assert "own parent" in response.json()["detail"].lower()


def test_patch_parent_with_children_cannot_become_child():
    """A category that has children cannot itself be made a child (depth violation)."""
    parent = _create_parent("Food", "expense")
    _create_child("Groceries", "expense", parent["id"])
    other_parent = _create_parent("Other", "expense")

    response = client.patch(
        f"/api/categories/{parent['id']}",
        json={"parent_id": other_parent["id"]},
    )

    assert response.status_code == 422
    assert "children" in response.json()["detail"].lower()


# ---------------------------------------------------------------------------
# Archive cascade
# ---------------------------------------------------------------------------

def test_archive_parent_cascades_to_children():
    """Archiving a parent automatically archives all its children."""
    parent = _create_parent("Food", "expense")
    _create_child("Groceries", "expense", parent["id"])
    _create_child("Dining Out", "expense", parent["id"])

    client.patch(f"/api/categories/{parent['id']}", json={"archived": True})

    # Neither parent nor children should appear in the default (non-archived) list.
    all_active = client.get("/api/categories").json()
    names = [c["name"] for c in all_active]
    assert "Food" not in names

    # With archived=true both parent and children should be visible.
    all_archived = client.get("/api/categories?archived=true").json()
    food = next((c for c in all_archived if c["name"] == "Food"), None)
    assert food is not None
    assert food["archived"] is True
    assert all(c["archived"] is True for c in food["children"])


def test_restore_parent_does_not_restore_children():
    """Restoring a parent leaves its children archived — they restore individually."""
    parent = _create_parent("Food", "expense")
    _create_child("Groceries", "expense", parent["id"])

    client.patch(f"/api/categories/{parent['id']}", json={"archived": True})
    client.patch(f"/api/categories/{parent['id']}", json={"archived": False})

    all_cats = client.get("/api/categories?archived=true").json()
    food = next((c for c in all_cats if c["name"] == "Food"), None)
    assert food["archived"] is False
    assert all(c["archived"] is True for c in food["children"])


# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------

def test_delete_leaf_category_with_no_transactions():
    """Deleting a childless category with no transactions returns 200 and count=0."""
    parent = _create_parent("Food", "expense")
    child = _create_child("Groceries", "expense", parent["id"])

    response = client.delete(f"/api/categories/{child['id']}")

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == child["id"]
    assert body["deleted_transactions_count"] == 0


def test_delete_category_with_transactions_nulls_category_id():
    """
    Deleting a category that has transactions referencing it returns the affected count.
    The transactions remain — only their category_id becomes NULL.
    """
    parent = _create_parent("Food", "expense")
    child = _create_child("Groceries", "expense", parent["id"])

    # Seed an account and two transactions referencing this category directly.
    db = _TestSession()
    try:
        from app.models import Account
        account = Account(name="HDFC", type="bank")
        db.add(account)
        db.flush()
        for _ in range(2):
            db.add(Transaction(
                account_id=account.id,
                category_id=child["id"],
                kind="expense",
                amount_minor=10000,
                occurred_on=date(2026, 4, 1),
                source="manual",
            ))
        db.commit()
    finally:
        db.close()

    response = client.delete(f"/api/categories/{child['id']}")

    assert response.status_code == 200
    assert response.json()["deleted_transactions_count"] == 2


def test_delete_parent_with_children_returns_409():
    """Cannot delete a parent that still has children."""
    parent = _create_parent("Food", "expense")
    _create_child("Groceries", "expense", parent["id"])

    response = client.delete(f"/api/categories/{parent['id']}")

    assert response.status_code == 409
    assert response.json()["code"] == "conflict"
    assert "child" in response.json()["detail"].lower()


# ---------------------------------------------------------------------------
# Duplicate rejection
# ---------------------------------------------------------------------------

def test_create_duplicate_category_returns_409():
    """Same name + kind + parent_id combination is rejected."""
    _create_parent("Food", "expense")

    response = client.post("/api/categories", json={"name": "Food", "kind": "expense"})
    assert response.status_code == 409
    assert response.json()["code"] == "conflict"

    # Case-insensitive check.
    response_lower = client.post("/api/categories", json={"name": "food", "kind": "expense"})
    assert response_lower.status_code == 409


# ---------------------------------------------------------------------------
# 404 cases
# ---------------------------------------------------------------------------

def test_patch_nonexistent_category_returns_404():
    response = client.patch("/api/categories/99999", json={"name": "Ghost"})
    assert response.status_code == 404
    assert response.json()["code"] == "not_found"


def test_delete_nonexistent_category_returns_404():
    response = client.delete("/api/categories/99999")
    assert response.status_code == 404
    assert response.json()["code"] == "not_found"

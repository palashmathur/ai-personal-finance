# Tests for the Accounts CRUD endpoints.
#
# We use an in-memory SQLite database for tests so each run is fast and fully isolated —
# nothing touches data/finance.db. The `setup_db` fixture wires this test DB into the
# app by overriding FastAPI's get_db dependency before every test.
#
# Think of dependency_overrides like Spring Boot's @MockBean — it replaces a real bean
# with a test double for the duration of the test, then restores the original.

from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.session import get_db
from app.main import app
from app.models import Base, Transaction

# In-memory SQLite with StaticPool — forces every session to reuse the same underlying
# connection, so Base.metadata.create_all() and the test sessions all see the same DB.
# Without StaticPool, sqlite:///:memory: gives each new connection its own empty database,
# which means the tables created in setup would be invisible to the test sessions.
_TEST_ENGINE = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)


@event.listens_for(_TEST_ENGINE, "connect")
def _set_pragmas(dbapi_conn, _):
    """Apply the same PRAGMAs as production so test behaviour matches exactly."""
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


_TestSession = sessionmaker(bind=_TEST_ENGINE, autoflush=False, autocommit=False)


def _override_get_db():
    """Replacement for get_db that uses the in-memory test DB."""
    db = _TestSession()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(autouse=True)
def setup_db():
    """
    Run before every test in this file (autouse=True).
    Creates all tables, installs the test DB override, then tears down after the test.
    This gives each test a completely clean slate — no data bleeds between tests.
    """
    Base.metadata.create_all(bind=_TEST_ENGINE)
    app.dependency_overrides[get_db] = _override_get_db
    yield
    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=_TEST_ENGINE)


client = TestClient(app)


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------

def test_create_account_returns_201():
    """POST with valid data should create the account and return 201."""
    response = client.post("/api/accounts", json={
        "name": "HDFC Savings",
        "type": "bank",
        "opening_balance_minor": 500000,  # ₹5,000
    })

    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "HDFC Savings"
    assert body["type"] == "bank"
    assert body["opening_balance_minor"] == 500000
    assert body["archived"] is False
    assert "id" in body


def test_list_accounts_excludes_archived_by_default():
    """GET /api/accounts should return only non-archived accounts unless ?archived=true."""
    client.post("/api/accounts", json={"name": "Active Account", "type": "cash"})
    client.post("/api/accounts", json={"name": "Old Account", "type": "bank"})

    # Archive the second account.
    accounts = client.get("/api/accounts").json()
    old_id = next(a["id"] for a in accounts if a["name"] == "Old Account")
    client.patch(f"/api/accounts/{old_id}", json={"archived": True})

    # Default list should only show the active one.
    response = client.get("/api/accounts")
    assert response.status_code == 200
    names = [a["name"] for a in response.json()]
    assert "Active Account" in names
    assert "Old Account" not in names

    # With ?archived=true both should appear.
    response_all = client.get("/api/accounts?archived=true")
    names_all = [a["name"] for a in response_all.json()]
    assert "Active Account" in names_all
    assert "Old Account" in names_all


def test_patch_rename_account():
    """PATCH should update only the fields sent, leaving others unchanged."""
    create_resp = client.post("/api/accounts", json={"name": "Original Name", "type": "wallet"})
    account_id = create_resp.json()["id"]

    response = client.patch(f"/api/accounts/{account_id}", json={"name": "New Name"})

    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "New Name"
    assert body["type"] == "wallet"  # unchanged


def test_patch_archive_and_restore():
    """Archiving hides the account; restoring brings it back to the default list."""
    account_id = client.post(
        "/api/accounts", json={"name": "Zerodha", "type": "broker"}
    ).json()["id"]

    # Archive it.
    client.patch(f"/api/accounts/{account_id}", json={"archived": True})
    active_ids = [a["id"] for a in client.get("/api/accounts").json()]
    assert account_id not in active_ids

    # Restore it.
    client.patch(f"/api/accounts/{account_id}", json={"archived": False})
    active_ids_after = [a["id"] for a in client.get("/api/accounts").json()]
    assert account_id in active_ids_after


def test_delete_account_with_no_references():
    """An account with no transactions can be hard-deleted; returns 204."""
    account_id = client.post(
        "/api/accounts", json={"name": "Empty Account", "type": "cash"}
    ).json()["id"]

    response = client.delete(f"/api/accounts/{account_id}")
    assert response.status_code == 204

    # Should be gone even with archived=true.
    all_accounts = client.get("/api/accounts?archived=true").json()
    assert not any(a["id"] == account_id for a in all_accounts)


# ---------------------------------------------------------------------------
# FK violation — cannot delete an account that has transactions
# ---------------------------------------------------------------------------

def test_delete_account_with_transactions_returns_409():
    """
    If an account has transactions referencing it, DELETE must return 409 Conflict.
    We insert a Transaction row directly via SQLAlchemy to simulate this without
    needing the transactions endpoint (which isn't built yet).
    """
    account_id = client.post(
        "/api/accounts", json={"name": "HDFC CC", "type": "credit_card"}
    ).json()["id"]

    # Seed a transaction that references this account directly in the test DB.
    db = _TestSession()
    try:
        txn = Transaction(
            account_id=account_id,
            kind="expense",
            amount_minor=10000,
            occurred_on=date(2026, 4, 1),
            source="manual",
        )
        db.add(txn)
        db.commit()
    finally:
        db.close()

    response = client.delete(f"/api/accounts/{account_id}")

    assert response.status_code == 409
    body = response.json()
    assert body["code"] == "conflict"
    assert "transaction" in body["detail"].lower()


# ---------------------------------------------------------------------------
# Validation — bad type enum
# ---------------------------------------------------------------------------

def test_create_duplicate_account_returns_409():
    """Creating a second account with the same name (case-insensitive) and type is rejected."""
    client.post("/api/accounts", json={"name": "ICICI", "type": "cash"})

    # Exact same name and type — should conflict.
    response = client.post("/api/accounts", json={"name": "ICICI", "type": "cash"})
    assert response.status_code == 409
    assert response.json()["code"] == "conflict"

    # Different casing — should also conflict (case-insensitive check).
    response_lower = client.post("/api/accounts", json={"name": "icici", "type": "cash"})
    assert response_lower.status_code == 409

    # Same name but different type — should succeed (ICICI cash vs ICICI bank are different accounts).
    response_diff_type = client.post("/api/accounts", json={"name": "ICICI", "type": "bank"})
    assert response_diff_type.status_code == 201


def test_create_account_with_invalid_type_returns_422():
    """Sending an unknown account type should be rejected at the schema level."""
    response = client.post("/api/accounts", json={
        "name": "Mystery Account",
        "type": "savings_account",  # not a valid AccountType value
    })

    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "validation_error"


def test_create_account_with_negative_opening_balance_returns_422():
    """opening_balance_minor must be >= 0."""
    response = client.post("/api/accounts", json={
        "name": "Bad Account",
        "type": "bank",
        "opening_balance_minor": -100,
    })

    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "validation_error"


# ---------------------------------------------------------------------------
# 404 cases
# ---------------------------------------------------------------------------

def test_patch_nonexistent_account_returns_404():
    response = client.patch("/api/accounts/99999", json={"name": "Ghost"})
    assert response.status_code == 404
    assert response.json()["code"] == "not_found"


def test_delete_nonexistent_account_returns_404():
    response = client.delete("/api/accounts/99999")
    assert response.status_code == 404
    assert response.json()["code"] == "not_found"

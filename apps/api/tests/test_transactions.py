# Tests for the Transactions CRUD endpoints.
#
# Uses the same in-memory SQLite + StaticPool pattern as test_accounts.py and
# test_categories.py — every test gets a clean, isolated DB with no data from finance.db.
#
# Most tests create the required accounts and categories directly into the DB via
# seed helpers (rather than going through the API) to keep tests focused and fast.

import re
from datetime import date
from typing import Optional

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.session import get_db
from app.main import app
from app.models import Account, Base, Category

_TEST_ENGINE = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)


@event.listens_for(_TEST_ENGINE, "connect")
def _set_pragmas(dbapi_conn, _):
    """Apply the same PRAGMAs as production so FK enforcement matches the real DB exactly."""
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

    We turn off FK enforcement before drop_all because SQLite would otherwise refuse
    to drop accounts/categories while transactions still references them (StaticPool
    shares one connection, so the pragma applies to the drop step too).
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


client = TestClient(app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# Seed helpers — insert fixtures directly into the test DB (no HTTP round-trip)
# ---------------------------------------------------------------------------


def _seed_account(name: str = "HDFC", type_: str = "bank") -> int:
    """Create an account row and return its id."""
    db = _TestSession()
    try:
        acc = Account(name=name, type=type_)
        db.add(acc)
        db.commit()
        db.refresh(acc)
        return acc.id
    finally:
        db.close()


def _seed_category(name: str = "Groceries", kind: str = "expense") -> int:
    """Create a top-level category row and return its id."""
    db = _TestSession()
    try:
        cat = Category(name=name, kind=kind)
        db.add(cat)
        db.commit()
        db.refresh(cat)
        return cat.id
    finally:
        db.close()


def _extract_transfer_uuid(note: str) -> Optional[str]:
    """Pull the UUID out of a note like 'Moving cash #transfer:abc-123...'."""
    match = re.search(r"#transfer:([a-f0-9\-]+)", note)
    return match.group(1) if match else None


# ---------------------------------------------------------------------------
# POST — income/expense happy path
# ---------------------------------------------------------------------------


def test_create_expense_returns_201_single_item():
    """Creating an expense returns 201 with a list of exactly one item."""
    acc_id = _seed_account()
    cat_id = _seed_category("Groceries", "expense")

    resp = client.post("/api/transactions", json={
        "kind": "expense",
        "account_id": acc_id,
        "category_id": cat_id,
        "amount_minor": 50000,
        "occurred_on": "2026-05-01",
    })

    assert resp.status_code == 201
    body = resp.json()
    assert isinstance(body, list)
    assert len(body) == 1
    txn = body[0]
    assert txn["kind"] == "expense"
    assert txn["amount_minor"] == 50000
    assert txn["account_id"] == acc_id
    assert txn["category_id"] == cat_id
    assert txn["account_name"] == "HDFC"
    assert txn["category_name"] == "Groceries"


def test_create_income_returns_201():
    """Creating an income transaction with an income-kind category returns 201."""
    acc_id = _seed_account()
    cat_id = _seed_category("Salary", "income")

    resp = client.post("/api/transactions", json={
        "kind": "income",
        "account_id": acc_id,
        "category_id": cat_id,
        "amount_minor": 8500000,
        "occurred_on": "2026-05-01",
    })

    assert resp.status_code == 201
    assert resp.json()[0]["kind"] == "income"


def test_create_stores_occurred_on_correctly():
    """The occurred_on date is persisted as-is and returned in the response."""
    acc_id = _seed_account()
    cat_id = _seed_category()

    resp = client.post("/api/transactions", json={
        "kind": "expense",
        "account_id": acc_id,
        "category_id": cat_id,
        "amount_minor": 10000,
        "occurred_on": "2026-04-15",
    })

    assert resp.json()[0]["occurred_on"] == "2026-04-15"


def test_create_with_note_persisted():
    """The note field is stored and returned in the response."""
    acc_id = _seed_account()
    cat_id = _seed_category()

    resp = client.post("/api/transactions", json={
        "kind": "expense",
        "account_id": acc_id,
        "category_id": cat_id,
        "amount_minor": 18000,
        "occurred_on": "2026-05-01",
        "note": "Zara shirt",
    })

    assert resp.json()[0]["note"] == "Zara shirt"


def test_create_defaults_source_to_manual():
    """Omitting source defaults to 'manual'."""
    acc_id = _seed_account()
    cat_id = _seed_category()

    resp = client.post("/api/transactions", json={
        "kind": "expense",
        "account_id": acc_id,
        "category_id": cat_id,
        "amount_minor": 5000,
        "occurred_on": "2026-05-01",
    })

    assert resp.json()[0]["source"] == "manual"


# ---------------------------------------------------------------------------
# POST — transfer happy path
# ---------------------------------------------------------------------------


def test_create_transfer_returns_201_two_rows():
    """Creating a transfer returns 201 with exactly two rows."""
    acc1 = _seed_account("HDFC", "bank")
    acc2 = _seed_account("Savings", "bank")

    resp = client.post("/api/transactions", json={
        "kind": "transfer",
        "from_account_id": acc1,
        "to_account_id": acc2,
        "amount_minor": 100000,
        "occurred_on": "2026-05-01",
    })

    assert resp.status_code == 201
    rows = resp.json()
    assert isinstance(rows, list)
    assert len(rows) == 2


def test_create_transfer_debit_row_is_expense_on_source_account():
    """First returned row (debit) has kind=expense and account=from_account_id."""
    acc1 = _seed_account("HDFC", "bank")
    acc2 = _seed_account("Savings", "bank")

    rows = client.post("/api/transactions", json={
        "kind": "transfer",
        "from_account_id": acc1,
        "to_account_id": acc2,
        "amount_minor": 100000,
        "occurred_on": "2026-05-01",
    }).json()

    debit = rows[0]
    assert debit["kind"] == "expense"
    assert debit["account_id"] == acc1


def test_create_transfer_credit_row_is_income_on_destination_account():
    """Second returned row (credit) has kind=income and account=to_account_id."""
    acc1 = _seed_account("HDFC", "bank")
    acc2 = _seed_account("Savings", "bank")

    rows = client.post("/api/transactions", json={
        "kind": "transfer",
        "from_account_id": acc1,
        "to_account_id": acc2,
        "amount_minor": 100000,
        "occurred_on": "2026-05-01",
    }).json()

    credit = rows[1]
    assert credit["kind"] == "income"
    assert credit["account_id"] == acc2


def test_create_transfer_both_rows_share_transfer_uuid():
    """Both rows of a transfer share the same #transfer:{uuid} tag in their note field."""
    acc1 = _seed_account("HDFC", "bank")
    acc2 = _seed_account("Savings", "bank")

    rows = client.post("/api/transactions", json={
        "kind": "transfer",
        "from_account_id": acc1,
        "to_account_id": acc2,
        "amount_minor": 100000,
        "occurred_on": "2026-05-01",
    }).json()

    uuid1 = _extract_transfer_uuid(rows[0]["note"])
    uuid2 = _extract_transfer_uuid(rows[1]["note"])
    assert uuid1 is not None
    assert uuid1 == uuid2


def test_create_transfer_user_note_preserved_alongside_tag():
    """When a note is supplied, it appears in the note field alongside the #transfer tag."""
    acc1 = _seed_account("HDFC", "bank")
    acc2 = _seed_account("Savings", "bank")

    rows = client.post("/api/transactions", json={
        "kind": "transfer",
        "from_account_id": acc1,
        "to_account_id": acc2,
        "amount_minor": 100000,
        "occurred_on": "2026-05-01",
        "note": "Monthly move",
    }).json()

    assert "Monthly move" in rows[0]["note"]
    assert "#transfer:" in rows[0]["note"]


def test_create_transfer_category_id_is_null_on_both_rows():
    """Transfer rows never have a category — both halves should have category_id=None."""
    acc1 = _seed_account("HDFC", "bank")
    acc2 = _seed_account("Savings", "bank")

    rows = client.post("/api/transactions", json={
        "kind": "transfer",
        "from_account_id": acc1,
        "to_account_id": acc2,
        "amount_minor": 100000,
        "occurred_on": "2026-05-01",
    }).json()

    assert rows[0]["category_id"] is None
    assert rows[1]["category_id"] is None


# ---------------------------------------------------------------------------
# POST — validation errors
# ---------------------------------------------------------------------------


def test_create_with_nonexistent_account_returns_404():
    cat_id = _seed_category()

    resp = client.post("/api/transactions", json={
        "kind": "expense",
        "account_id": 99999,
        "category_id": cat_id,
        "amount_minor": 5000,
        "occurred_on": "2026-05-01",
    })

    assert resp.status_code == 404
    assert resp.json()["code"] == "not_found"


def test_create_with_archived_account_returns_409():
    """Transactions cannot be created on an archived account."""
    db = _TestSession()
    try:
        acc = Account(name="Old Bank", type="bank", archived=True)
        db.add(acc)
        db.commit()
        db.refresh(acc)
        acc_id = acc.id
    finally:
        db.close()

    cat_id = _seed_category()

    resp = client.post("/api/transactions", json={
        "kind": "expense",
        "account_id": acc_id,
        "category_id": cat_id,
        "amount_minor": 5000,
        "occurred_on": "2026-05-01",
    })

    assert resp.status_code == 409
    assert resp.json()["code"] == "conflict"


def test_create_with_nonexistent_category_returns_404():
    acc_id = _seed_account()

    resp = client.post("/api/transactions", json={
        "kind": "expense",
        "account_id": acc_id,
        "category_id": 99999,
        "amount_minor": 5000,
        "occurred_on": "2026-05-01",
    })

    assert resp.status_code == 404
    assert resp.json()["code"] == "not_found"


def test_create_income_with_expense_category_returns_422():
    """Kind mismatch: income transaction + expense category is rejected."""
    acc_id = _seed_account()
    cat_id = _seed_category("Groceries", "expense")  # expense category

    resp = client.post("/api/transactions", json={
        "kind": "income",  # but income transaction
        "account_id": acc_id,
        "category_id": cat_id,
        "amount_minor": 5000,
        "occurred_on": "2026-05-01",
    })

    assert resp.status_code == 422
    assert "mismatch" in resp.json()["detail"].lower()


def test_create_expense_with_income_category_returns_422():
    """Kind mismatch (reverse): expense transaction + income category is rejected."""
    acc_id = _seed_account()
    cat_id = _seed_category("Salary", "income")  # income category

    resp = client.post("/api/transactions", json={
        "kind": "expense",  # but expense transaction
        "account_id": acc_id,
        "category_id": cat_id,
        "amount_minor": 5000,
        "occurred_on": "2026-05-01",
    })

    assert resp.status_code == 422
    assert "mismatch" in resp.json()["detail"].lower()


def test_create_income_without_category_returns_422():
    """income/expense requires category_id — omitting it is rejected by the schema validator."""
    acc_id = _seed_account()

    resp = client.post("/api/transactions", json={
        "kind": "expense",
        "account_id": acc_id,
        "amount_minor": 5000,
        "occurred_on": "2026-05-01",
    })

    assert resp.status_code == 422


def test_create_income_without_account_returns_422():
    """income/expense requires account_id — omitting it is rejected by the schema validator."""
    cat_id = _seed_category()

    resp = client.post("/api/transactions", json={
        "kind": "expense",
        "category_id": cat_id,
        "amount_minor": 5000,
        "occurred_on": "2026-05-01",
    })

    assert resp.status_code == 422


def test_create_with_zero_amount_returns_422():
    """amount_minor must be > 0 — zero is rejected at schema level."""
    acc_id = _seed_account()
    cat_id = _seed_category()

    resp = client.post("/api/transactions", json={
        "kind": "expense",
        "account_id": acc_id,
        "category_id": cat_id,
        "amount_minor": 0,
        "occurred_on": "2026-05-01",
    })

    assert resp.status_code == 422


def test_create_with_negative_amount_returns_422():
    """Negative amount_minor is also rejected at schema level."""
    acc_id = _seed_account()
    cat_id = _seed_category()

    resp = client.post("/api/transactions", json={
        "kind": "expense",
        "account_id": acc_id,
        "category_id": cat_id,
        "amount_minor": -100,
        "occurred_on": "2026-05-01",
    })

    assert resp.status_code == 422


def test_create_transfer_same_from_to_account_returns_422():
    """Transferring to and from the same account is meaningless — rejected by schema."""
    acc_id = _seed_account()

    resp = client.post("/api/transactions", json={
        "kind": "transfer",
        "from_account_id": acc_id,
        "to_account_id": acc_id,  # same!
        "amount_minor": 100000,
        "occurred_on": "2026-05-01",
    })

    assert resp.status_code == 422


def test_create_transfer_missing_from_account_returns_422():
    acc2 = _seed_account("Savings", "bank")

    resp = client.post("/api/transactions", json={
        "kind": "transfer",
        "to_account_id": acc2,
        "amount_minor": 100000,
        "occurred_on": "2026-05-01",
    })

    assert resp.status_code == 422


def test_create_transfer_missing_to_account_returns_422():
    acc1 = _seed_account()

    resp = client.post("/api/transactions", json={
        "kind": "transfer",
        "from_account_id": acc1,
        "amount_minor": 100000,
        "occurred_on": "2026-05-01",
    })

    assert resp.status_code == 422


def test_create_transfer_with_category_id_returns_422():
    """Transfers must not have category_id — rejected by schema validator."""
    acc1 = _seed_account("HDFC", "bank")
    acc2 = _seed_account("Savings", "bank")
    cat_id = _seed_category()

    resp = client.post("/api/transactions", json={
        "kind": "transfer",
        "from_account_id": acc1,
        "to_account_id": acc2,
        "category_id": cat_id,  # not allowed on transfers
        "amount_minor": 100000,
        "occurred_on": "2026-05-01",
    })

    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# GET — list and filters
# ---------------------------------------------------------------------------


def test_list_returns_all_transactions():
    """GET /api/transactions returns all rows when no filters are applied."""
    acc_id = _seed_account()
    cat_id = _seed_category()

    client.post("/api/transactions", json={
        "kind": "expense", "account_id": acc_id, "category_id": cat_id,
        "amount_minor": 10000, "occurred_on": "2026-05-01",
    })
    client.post("/api/transactions", json={
        "kind": "expense", "account_id": acc_id, "category_id": cat_id,
        "amount_minor": 20000, "occurred_on": "2026-05-02",
    })

    resp = client.get("/api/transactions")
    assert resp.status_code == 200
    assert len(resp.json()) == 2


def test_list_filter_by_kind():
    """?kind=expense returns only expense rows."""
    acc_id = _seed_account()
    exp_cat = _seed_category("Groceries", "expense")
    inc_cat = _seed_category("Salary", "income")

    client.post("/api/transactions", json={
        "kind": "expense", "account_id": acc_id, "category_id": exp_cat,
        "amount_minor": 10000, "occurred_on": "2026-05-01",
    })
    client.post("/api/transactions", json={
        "kind": "income", "account_id": acc_id, "category_id": inc_cat,
        "amount_minor": 80000, "occurred_on": "2026-05-01",
    })

    resp = client.get("/api/transactions?kind=expense")
    rows = resp.json()
    assert all(r["kind"] == "expense" for r in rows)
    assert len(rows) == 1


def test_list_filter_by_date_range():
    """?from=X&to=Y returns only transactions whose occurred_on falls in the range (inclusive)."""
    acc_id = _seed_account()
    cat_id = _seed_category()

    client.post("/api/transactions", json={
        "kind": "expense", "account_id": acc_id, "category_id": cat_id,
        "amount_minor": 10000, "occurred_on": "2026-04-01",
    })
    client.post("/api/transactions", json={
        "kind": "expense", "account_id": acc_id, "category_id": cat_id,
        "amount_minor": 20000, "occurred_on": "2026-05-15",
    })

    resp = client.get("/api/transactions?from=2026-05-01&to=2026-05-31")
    rows = resp.json()
    assert len(rows) == 1
    assert rows[0]["occurred_on"] == "2026-05-15"


def test_list_filter_by_account_id():
    """?account_id=X returns only transactions on that account."""
    acc1 = _seed_account("HDFC", "bank")
    acc2 = _seed_account("Savings", "bank")
    cat_id = _seed_category()

    client.post("/api/transactions", json={
        "kind": "expense", "account_id": acc1, "category_id": cat_id,
        "amount_minor": 10000, "occurred_on": "2026-05-01",
    })
    client.post("/api/transactions", json={
        "kind": "expense", "account_id": acc2, "category_id": cat_id,
        "amount_minor": 20000, "occurred_on": "2026-05-01",
    })

    resp = client.get(f"/api/transactions?account_id={acc1}")
    rows = resp.json()
    assert len(rows) == 1
    assert rows[0]["account_id"] == acc1


def test_list_filter_q_partial_note_match():
    """?q=swiggy returns only transactions whose note contains 'swiggy' (case-insensitive)."""
    acc_id = _seed_account()
    cat_id = _seed_category()

    client.post("/api/transactions", json={
        "kind": "expense", "account_id": acc_id, "category_id": cat_id,
        "amount_minor": 15000, "occurred_on": "2026-05-01", "note": "Swiggy dinner",
    })
    client.post("/api/transactions", json={
        "kind": "expense", "account_id": acc_id, "category_id": cat_id,
        "amount_minor": 8000, "occurred_on": "2026-05-01", "note": "Zomato lunch",
    })

    resp = client.get("/api/transactions?q=swiggy")
    rows = resp.json()
    assert len(rows) == 1
    assert "Swiggy" in rows[0]["note"]


def test_list_pagination_limit_and_offset():
    """limit and offset control the page of results returned."""
    acc_id = _seed_account()
    cat_id = _seed_category()

    for i in range(5):
        client.post("/api/transactions", json={
            "kind": "expense", "account_id": acc_id, "category_id": cat_id,
            "amount_minor": 1000 * (i + 1), "occurred_on": f"2026-05-0{i + 1}",
        })

    page1 = client.get("/api/transactions?limit=2&offset=0").json()
    page2 = client.get("/api/transactions?limit=2&offset=2").json()

    assert len(page1) == 2
    assert len(page2) == 2
    # No overlap between pages
    ids_p1 = {r["id"] for r in page1}
    ids_p2 = {r["id"] for r in page2}
    assert ids_p1.isdisjoint(ids_p2)


def test_list_ordered_by_occurred_on_desc():
    """Results are returned most-recent-first based on occurred_on."""
    acc_id = _seed_account()
    cat_id = _seed_category()

    client.post("/api/transactions", json={
        "kind": "expense", "account_id": acc_id, "category_id": cat_id,
        "amount_minor": 10000, "occurred_on": "2026-04-01",
    })
    client.post("/api/transactions", json={
        "kind": "expense", "account_id": acc_id, "category_id": cat_id,
        "amount_minor": 20000, "occurred_on": "2026-05-01",
    })

    rows = client.get("/api/transactions").json()
    assert rows[0]["occurred_on"] == "2026-05-01"
    assert rows[1]["occurred_on"] == "2026-04-01"


def test_list_includes_account_name_and_category_name():
    """Response rows include denormalized account_name and category_name for display."""
    acc_id = _seed_account("My HDFC", "bank")
    cat_id = _seed_category("Groceries", "expense")

    client.post("/api/transactions", json={
        "kind": "expense", "account_id": acc_id, "category_id": cat_id,
        "amount_minor": 10000, "occurred_on": "2026-05-01",
    })

    row = client.get("/api/transactions").json()[0]
    assert row["account_name"] == "My HDFC"
    assert row["category_name"] == "Groceries"


# ---------------------------------------------------------------------------
# PATCH
# ---------------------------------------------------------------------------


def test_patch_amount_updates_correctly():
    acc_id = _seed_account()
    cat_id = _seed_category()

    txn_id = client.post("/api/transactions", json={
        "kind": "expense", "account_id": acc_id, "category_id": cat_id,
        "amount_minor": 10000, "occurred_on": "2026-05-01",
    }).json()[0]["id"]

    resp = client.patch(f"/api/transactions/{txn_id}", json={"amount_minor": 99000})

    assert resp.status_code == 200
    assert resp.json()[0]["amount_minor"] == 99000


def test_patch_note_updates_correctly():
    acc_id = _seed_account()
    cat_id = _seed_category()

    txn_id = client.post("/api/transactions", json={
        "kind": "expense", "account_id": acc_id, "category_id": cat_id,
        "amount_minor": 10000, "occurred_on": "2026-05-01", "note": "Old note",
    }).json()[0]["id"]

    resp = client.patch(f"/api/transactions/{txn_id}", json={"note": "New note"})

    assert resp.status_code == 200
    assert resp.json()[0]["note"] == "New note"


def test_patch_transfer_amount_updates_both_rows():
    """Patching amount_minor on one transfer half propagates to the partner row."""
    acc1 = _seed_account("HDFC", "bank")
    acc2 = _seed_account("Savings", "bank")

    rows = client.post("/api/transactions", json={
        "kind": "transfer",
        "from_account_id": acc1,
        "to_account_id": acc2,
        "amount_minor": 100000,
        "occurred_on": "2026-05-01",
    }).json()

    txn_id = rows[0]["id"]
    partner_id = rows[1]["id"]

    resp = client.patch(f"/api/transactions/{txn_id}", json={"amount_minor": 200000})

    assert resp.status_code == 200
    returned_ids = {r["id"] for r in resp.json()}
    assert txn_id in returned_ids
    assert partner_id in returned_ids
    for row in resp.json():
        assert row["amount_minor"] == 200000


def test_patch_transfer_note_preserves_transfer_tag():
    """Updating the note on a transfer row keeps the #transfer:{uuid} tag intact."""
    acc1 = _seed_account("HDFC", "bank")
    acc2 = _seed_account("Savings", "bank")

    rows = client.post("/api/transactions", json={
        "kind": "transfer",
        "from_account_id": acc1,
        "to_account_id": acc2,
        "amount_minor": 100000,
        "occurred_on": "2026-05-01",
        "note": "Original note",
    }).json()

    original_uuid = _extract_transfer_uuid(rows[0]["note"])
    txn_id = rows[0]["id"]

    updated_rows = client.patch(f"/api/transactions/{txn_id}", json={"note": "Updated note"}).json()

    for row in updated_rows:
        assert "Updated note" in row["note"]
        assert f"#transfer:{original_uuid}" in row["note"]


def test_patch_transfer_from_account_id_updates_debit_row():
    """from_account_id in PATCH updates only the debit (expense) half of the transfer."""
    acc1 = _seed_account("HDFC", "bank")
    acc2 = _seed_account("Savings", "bank")
    acc3 = _seed_account("New Source", "bank")

    rows = client.post("/api/transactions", json={
        "kind": "transfer",
        "from_account_id": acc1,
        "to_account_id": acc2,
        "amount_minor": 100000,
        "occurred_on": "2026-05-01",
    }).json()

    debit_id = rows[0]["id"]  # kind=expense row
    resp = client.patch(f"/api/transactions/{debit_id}", json={"from_account_id": acc3})

    updated = {r["kind"]: r for r in resp.json()}
    assert updated["expense"]["account_id"] == acc3
    assert updated["income"]["account_id"] == acc2  # unchanged


def test_patch_transfer_to_account_id_updates_credit_row():
    """to_account_id in PATCH updates only the credit (income) half of the transfer."""
    acc1 = _seed_account("HDFC", "bank")
    acc2 = _seed_account("Savings", "bank")
    acc3 = _seed_account("New Dest", "bank")

    rows = client.post("/api/transactions", json={
        "kind": "transfer",
        "from_account_id": acc1,
        "to_account_id": acc2,
        "amount_minor": 100000,
        "occurred_on": "2026-05-01",
    }).json()

    credit_id = rows[1]["id"]  # kind=income row
    resp = client.patch(f"/api/transactions/{credit_id}", json={"to_account_id": acc3})

    updated = {r["kind"]: r for r in resp.json()}
    assert updated["income"]["account_id"] == acc3
    assert updated["expense"]["account_id"] == acc1  # unchanged


def test_patch_nonexistent_transaction_returns_404():
    resp = client.patch("/api/transactions/99999", json={"amount_minor": 5000})
    assert resp.status_code == 404
    assert resp.json()["code"] == "not_found"


def test_patch_category_kind_mismatch_returns_422():
    """Patching category_id with a wrong-kind category is rejected."""
    acc_id = _seed_account()
    expense_cat = _seed_category("Groceries", "expense")
    income_cat = _seed_category("Salary", "income")

    txn_id = client.post("/api/transactions", json={
        "kind": "expense", "account_id": acc_id, "category_id": expense_cat,
        "amount_minor": 10000, "occurred_on": "2026-05-01",
    }).json()[0]["id"]

    # Try to patch an expense transaction with an income category
    resp = client.patch(f"/api/transactions/{txn_id}", json={"category_id": income_cat})

    assert resp.status_code == 422
    assert "mismatch" in resp.json()["detail"].lower()


# ---------------------------------------------------------------------------
# DELETE
# ---------------------------------------------------------------------------


def test_delete_single_transaction_returns_204():
    acc_id = _seed_account()
    cat_id = _seed_category()

    txn_id = client.post("/api/transactions", json={
        "kind": "expense", "account_id": acc_id, "category_id": cat_id,
        "amount_minor": 10000, "occurred_on": "2026-05-01",
    }).json()[0]["id"]

    resp = client.delete(f"/api/transactions/{txn_id}")
    assert resp.status_code == 204


def test_delete_nonexistent_transaction_returns_404():
    resp = client.delete("/api/transactions/99999")
    assert resp.status_code == 404
    assert resp.json()["code"] == "not_found"


def test_delete_transfer_deletes_both_rows():
    """Deleting either half of a transfer removes both rows atomically."""
    acc1 = _seed_account("HDFC", "bank")
    acc2 = _seed_account("Savings", "bank")

    rows = client.post("/api/transactions", json={
        "kind": "transfer",
        "from_account_id": acc1,
        "to_account_id": acc2,
        "amount_minor": 100000,
        "occurred_on": "2026-05-01",
    }).json()

    debit_id = rows[0]["id"]
    partner_id = rows[1]["id"]

    # Delete one half — both should disappear
    client.delete(f"/api/transactions/{debit_id}")

    all_txns = client.get("/api/transactions").json()
    all_ids = {r["id"] for r in all_txns}
    assert debit_id not in all_ids
    assert partner_id not in all_ids


def test_deleted_transaction_absent_from_list():
    """After deletion, the transaction no longer appears in GET /api/transactions."""
    acc_id = _seed_account()
    cat_id = _seed_category()

    txn_id = client.post("/api/transactions", json={
        "kind": "expense", "account_id": acc_id, "category_id": cat_id,
        "amount_minor": 10000, "occurred_on": "2026-05-01",
    }).json()[0]["id"]

    client.delete(f"/api/transactions/{txn_id}")

    rows = client.get("/api/transactions").json()
    assert all(r["id"] != txn_id for r in rows)

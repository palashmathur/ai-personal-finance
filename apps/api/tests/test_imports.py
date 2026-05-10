# Tests for the CSV Import endpoints.
#
# Covers the three cases from the AC:
#   1. Happy path — valid CSV previews correctly, confirm inserts all rows.
#   2. Duplicate detection — confirming the same rows twice skips them all.
#   3. Malformed CSV — missing column, bad date, bad type all return 422.
#
# Also tests:
#   4. Category name hint in CSV maps to suggested_category_id.
#   5. Blank category column → suggested_category_id is None.
#   6. Empty confirm body returns 422.

import io

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.session import get_db
from app.main import app
from app.models import Base

_TEST_ENGINE = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)


@event.listens_for(_TEST_ENGINE, "connect")
def _set_pragmas(dbapi_conn, _):
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
    Base.metadata.create_all(bind=_TEST_ENGINE)
    app.dependency_overrides[get_db] = _override_get_db
    yield
    app.dependency_overrides.clear()
    with _TEST_ENGINE.connect() as conn:
        conn.execute(__import__("sqlalchemy").text("PRAGMA foreign_keys=OFF"))
    Base.metadata.drop_all(bind=_TEST_ENGINE)
    with _TEST_ENGINE.connect() as conn:
        conn.execute(__import__("sqlalchemy").text("PRAGMA foreign_keys=ON"))


client = TestClient(app, raise_server_exceptions=False)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_VALID_CSV = """\
date,amount,type,narration,category
09/05/2026,450.00,debit,UPI-SWIGGY-FOOD,Food
08/05/2026,85000.00,credit,SALARY MAY 2026,Salary
07/05/2026,320.00,debit,UPI-ZOMATO-ORDER,
06/05/2026,2000.00,debit,ATM CASH WITHDRAWAL,
"""


def _upload_preview(csv_content: str):
    """Helper that posts a CSV string to the preview endpoint."""
    return client.post(
        "/api/imports/transactions/preview",
        files={"file": ("transactions.csv", io.BytesIO(csv_content.encode()), "text/csv")},
    )


def _seed_account():
    resp = client.post("/api/accounts", json={"name": "HDFC Savings", "type": "bank"})
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def _seed_category(name, kind):
    resp = client.post("/api/categories", json={"name": name, "kind": kind})
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


# ---------------------------------------------------------------------------
# Happy path — preview
# ---------------------------------------------------------------------------

def test_preview_returns_correct_row_count():
    """4 data rows in the CSV → preview returns 4 rows and total=4."""
    resp = _upload_preview(_VALID_CSV)
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 4
    assert len(body["rows"]) == 4


def test_preview_parses_debit_as_expense():
    resp = _upload_preview(_VALID_CSV)
    rows = {r["note"]: r for r in resp.json()["rows"]}
    assert rows["UPI-SWIGGY-FOOD"]["kind"] == "expense"
    assert rows["UPI-SWIGGY-FOOD"]["amount_minor"] == 45000   # 450.00 × 100
    assert rows["UPI-SWIGGY-FOOD"]["occurred_on"] == "2026-05-09"  # stored as ISO in DB


def test_preview_parses_credit_as_income():
    resp = _upload_preview(_VALID_CSV)
    rows = {r["note"]: r for r in resp.json()["rows"]}
    assert rows["SALARY MAY 2026"]["kind"] == "income"
    assert rows["SALARY MAY 2026"]["amount_minor"] == 8_500_000  # 85000.00 × 100


def test_preview_writes_nothing_to_db():
    """Preview must not insert any rows — the transactions table stays empty."""
    _upload_preview(_VALID_CSV)
    resp = client.get("/api/transactions")
    assert resp.status_code == 200
    assert resp.json() == []


# ---------------------------------------------------------------------------
# Category suggestion
# ---------------------------------------------------------------------------

def test_preview_suggests_category_when_name_matches():
    """Text category hint matched case-insensitively to a category name."""
    food_id = _seed_category("Food", "expense")
    resp = _upload_preview(_VALID_CSV)
    rows = {r["note"]: r for r in resp.json()["rows"]}
    assert rows["UPI-SWIGGY-FOOD"]["suggested_category_id"] == food_id



def test_preview_blank_category_returns_none():
    """Rows with no category hint must have suggested_category_id=None."""
    _seed_category("Food", "expense")
    resp = _upload_preview(_VALID_CSV)
    rows = {r["note"]: r for r in resp.json()["rows"]}
    assert rows["ATM CASH WITHDRAWAL"]["suggested_category_id"] is None


def test_preview_unmatched_category_returns_none():
    """A category hint that doesn't match any DB category returns None."""
    resp = _upload_preview(_VALID_CSV)
    rows = {r["note"]: r for r in resp.json()["rows"]}
    assert rows["UPI-SWIGGY-FOOD"]["suggested_category_id"] is None


# ---------------------------------------------------------------------------
# Happy path — confirm
# ---------------------------------------------------------------------------

def test_confirm_inserts_all_rows():
    """Confirming 3 rows against an empty DB should insert all 3."""
    account_id = _seed_account()
    food_id = _seed_category("Food", "expense")
    salary_id = _seed_category("Salary", "income")

    body = {
        "account_id": account_id,
        "rows": [
            {"occurred_on": "2026-05-09", "amount_minor": 45000,
             "kind": "expense", "note": "UPI-SWIGGY", "category_id": food_id},
            {"occurred_on": "2026-05-08", "amount_minor": 8_500_000,
             "kind": "income", "note": "SALARY", "category_id": salary_id},
            {"occurred_on": "2026-05-07", "amount_minor": 32000,
             "kind": "expense", "note": "UPI-ZOMATO", "category_id": food_id},
        ],
    }

    resp = client.post("/api/imports/transactions/confirm", json=body)
    assert resp.status_code == 200
    assert resp.json()["inserted"] == 3
    assert resp.json()["skipped"] == 0


def test_confirm_sets_source_to_csv():
    """All imported rows must have source='csv' not 'manual'."""
    account_id = _seed_account()
    food_id = _seed_category("Food", "expense")

    body = {
        "account_id": account_id,
        "rows": [{"occurred_on": "2026-05-09", "amount_minor": 45000,
                  "kind": "expense", "note": "UPI-SWIGGY", "category_id": food_id}],
    }
    client.post("/api/imports/transactions/confirm", json=body)

    txns = client.get("/api/transactions").json()
    assert txns[0]["source"] == "csv"


# ---------------------------------------------------------------------------
# Duplicate detection
# ---------------------------------------------------------------------------

def test_duplicate_rows_are_skipped_on_second_confirm():
    """Confirming the same rows twice: first run inserts, second run skips all."""
    account_id = _seed_account()
    salary_id = _seed_category("Salary", "income")

    body = {
        "account_id": account_id,
        "rows": [{"occurred_on": "2026-05-08", "amount_minor": 8_500_000,
                  "kind": "income", "note": "SALARY MAY", "category_id": salary_id}],
    }

    first = client.post("/api/imports/transactions/confirm", json=body)
    assert first.json()["inserted"] == 1
    assert first.json()["skipped"] == 0

    second = client.post("/api/imports/transactions/confirm", json=body)
    assert second.json()["inserted"] == 0
    assert second.json()["skipped"] == 1


def test_duplicate_within_same_upload_skipped():
    """If the same row appears twice in one confirm call, the second occurrence is skipped."""
    account_id = _seed_account()
    food_id = _seed_category("Food", "expense")

    row = {"occurred_on": "2026-05-09", "amount_minor": 45000,
           "kind": "expense", "note": "UPI-SWIGGY", "category_id": food_id}

    body = {"account_id": account_id, "rows": [row, row]}
    resp = client.post("/api/imports/transactions/confirm", json=body)
    assert resp.json()["inserted"] == 1
    assert resp.json()["skipped"] == 1


# ---------------------------------------------------------------------------
# Malformed CSV — 422 cases
# ---------------------------------------------------------------------------

def test_missing_required_column_returns_422():
    """CSV missing the 'amount' column should return 422."""
    bad_csv = "date,type,narration,category\n2026-05-09,debit,SWIGGY,\n"
    resp = _upload_preview(bad_csv)
    assert resp.status_code == 422
    assert "amount" in resp.json()["detail"].lower()


def test_bad_date_format_returns_422():
    """Date not in DD/MM/YYYY format should return 422 with the row number."""
    bad_csv = "date,amount,type,narration,category\n2026-05-09,450.00,debit,SWIGGY,\n"
    resp = _upload_preview(bad_csv)
    assert resp.status_code == 422
    assert "date" in resp.json()["detail"].lower()


def test_invalid_type_returns_422():
    """type value other than debit/credit should return 422."""
    bad_csv = "date,amount,type,narration,category\n09/05/2026,450.00,withdrawal,SWIGGY,\n"
    resp = _upload_preview(bad_csv)
    assert resp.status_code == 422
    assert "debit" in resp.json()["detail"].lower() or "credit" in resp.json()["detail"].lower()


def test_negative_amount_returns_422():
    """Negative amount should return 422."""
    bad_csv = "date,amount,type,narration,category\n09/05/2026,-450.00,debit,SWIGGY,\n"
    resp = _upload_preview(bad_csv)
    assert resp.status_code == 422
    assert "amount" in resp.json()["detail"].lower()


def test_empty_csv_returns_422():
    """A CSV with only a header and no data rows should return 422."""
    empty_csv = "date,amount,type,narration,category\n"
    resp = _upload_preview(empty_csv)
    assert resp.status_code == 422


def test_empty_confirm_body_returns_422():
    """Confirm with an empty rows list should return 422."""
    account_id = _seed_account()
    resp = client.post("/api/imports/transactions/confirm",
                       json={"account_id": account_id, "rows": []})
    assert resp.status_code == 422

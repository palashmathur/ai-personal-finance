# Tests for the CSV Import endpoints.
#
# Covers the three cases from the AC:
#   1. Happy path — valid CSV previews correctly, confirm inserts all rows.
#   2. Duplicate detection — confirming the same rows twice skips them all.
#   3. Malformed CSV — missing column, bad date, bad type all return 422.
#
# Also tests:
#   4. Category name hint in CSV → category_id + category_name + source="csv" (no LLM).
#   5. Blank category column + no rule → suggest_batch fills it in (source="rule" or "llm").
#   6. Empty confirm body returns 422.
#
# LLM mock strategy: an autouse fixture patches call_llm with a no-match response
# so tests that don't care about categorization never hit the real Anthropic API.
# Tests that specifically assert categorization behaviour set their own mock.

import dataclasses
import io
from unittest.mock import patch

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


# ---------------------------------------------------------------------------
# Fake LLM response objects (same duck-typing pattern as test_categorize.py)
# ---------------------------------------------------------------------------

@dataclasses.dataclass
class _FakeToolUseBlock:
    name: str
    input: dict
    type: str = "tool_use"
    id: str = "toolu_01"


@dataclasses.dataclass
class _FakeMessage:
    stop_reason: str
    content: list
    usage: object = dataclasses.field(
        default_factory=lambda: type("U", (), {
            "input_tokens": 10,
            "output_tokens": 5,
            "cache_read_input_tokens": 0,
            "cache_creation_input_tokens": 0,
        })()
    )


def _llm_no_match() -> _FakeMessage:
    """LLM returns null — no category fits. Used as the default mock."""
    return _FakeMessage(
        stop_reason="tool_use",
        content=[_FakeToolUseBlock(
            name="suggest_category",
            input={"category_id": None, "confidence": 0.0, "suggested_rule": None},
        )],
    )


def _llm_match(category_id: int) -> _FakeMessage:
    """LLM returns a specific category."""
    return _FakeMessage(
        stop_reason="tool_use",
        content=[_FakeToolUseBlock(
            name="suggest_category",
            input={"category_id": category_id, "confidence": 0.9, "suggested_rule": None},
        )],
    )


@pytest.fixture(autouse=True)
def mock_llm():
    """
    Default: LLM returns no match for every call.
    This prevents any test from hitting the real Anthropic API accidentally.
    Tests that want specific LLM behaviour can override mock_llm.return_value.
    """
    with patch("app.services.categorize.call_llm") as m:
        m.return_value = _llm_no_match()
        yield m


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
    assert rows["UPI-SWIGGY-FOOD"]["occurred_on"] == "2026-05-09"


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

def test_preview_suggests_category_when_csv_name_matches():
    """
    When the CSV category column matches a DB category name, the row gets
    category_id + category_name immediately — no rule/LLM needed.
    """
    food_id = _seed_category("Food", "expense")
    _seed_category("Salary", "income")

    resp = _upload_preview(_VALID_CSV)
    rows = {r["note"]: r for r in resp.json()["rows"]}

    assert rows["UPI-SWIGGY-FOOD"]["category_id"] == food_id
    assert rows["UPI-SWIGGY-FOOD"]["category_name"] == "Food"
    assert rows["UPI-SWIGGY-FOOD"]["category_source"] == "csv"


def test_preview_csv_category_does_not_call_llm_for_matched_rows(mock_llm):
    """Rows matched by CSV category name must not trigger an LLM call."""
    _seed_category("Food", "expense")
    _seed_category("Salary", "income")

    _upload_preview(_VALID_CSV)

    # Only the 2 rows without a CSV category hint (Zomato and ATM) should hit the LLM.
    # The LLM returns no-match for both, so call_count should be 2 not 4.
    assert mock_llm.call_count == 2


def test_preview_blank_category_falls_back_to_suggest(mock_llm):
    """Rows with no CSV category column go through suggest_batch (rule or LLM)."""
    food_id = _seed_category("Food", "expense")
    _seed_category("Salary", "income")
    mock_llm.return_value = _llm_match(food_id)

    resp = _upload_preview(_VALID_CSV)
    rows = {r["note"]: r for r in resp.json()["rows"]}

    # ATM CASH WITHDRAWAL has no CSV category → LLM suggested Food
    assert rows["ATM CASH WITHDRAWAL"]["category_id"] == food_id
    assert rows["ATM CASH WITHDRAWAL"]["category_source"] == "llm"


def test_preview_unmatched_csv_category_returns_none():
    """A CSV category hint that doesn't match any DB category → category_id is None."""
    # No categories seeded → lookup fails → falls back to LLM (mocked no-match)
    resp = _upload_preview(_VALID_CSV)
    rows = {r["note"]: r for r in resp.json()["rows"]}
    assert rows["UPI-SWIGGY-FOOD"]["category_id"] is None


def test_preview_rule_match_skips_llm(mock_llm):
    """When a categorization rule covers a note, the LLM is not called for that row."""
    food_id = _seed_category("Food", "expense")
    _seed_category("Salary", "income")  # needed so Salary CSV hint resolves → skips suggest_batch
    # Seed a rule that covers Zomato
    client.post("/api/categorize/accept", json={
        "pattern": "(?i)zomato",
        "category_id": food_id,
    })

    _upload_preview(_VALID_CSV)

    # Swiggy → CSV name match (Food seeded) → skips suggest_batch
    # Salary → CSV name match (Salary seeded) → skips suggest_batch
    # Zomato → no CSV category, but rule matches → no LLM
    # ATM → no CSV category, no rule → LLM called once
    assert mock_llm.call_count == 1


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

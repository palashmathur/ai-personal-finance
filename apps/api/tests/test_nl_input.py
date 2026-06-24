# Tests for the NL input endpoint: POST /api/ai/nl-input (app/services/nl_input.py).
#
# All LLM calls are mocked — no API key or network. We patch the get_llm() factory and
# drive the with_structured_output(...).invoke(...) chain so it returns a validated
# _NLParse, exactly like the real LangChain path does. The category fallback is rules-only
# (no LLM), so there's nothing extra to patch for it. Nothing here names a concrete LLM
# provider; the feature stays provider-agnostic.
#
# Coverage:
#   1. Happy path — sentence parsed into a draft (amount→paise, matched account/category).
#   2. Amount resolution done in Python (rupees → paise).
#   3. Dates — relative/ISO passthrough, missing → today, malformed → today.
#   4. Account — matched by name, unknown/missing → default_account_id.
#   5. Category — exact match, kind mismatch dropped, fallback to rule, fallback to null.
#   6. Errors — missing amount → 422, bad default account → 422.
#   7. Kind — income parsed, invalid kind coerced to expense.
#   8. Golden set — 10 phrases parsed to the right amount/kind.

from datetime import date
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.session import get_db
from app.main import app
from app.models import Account, Base, CategorizationRule, Category
from app.services.nl_input import _NLParse

# ---------------------------------------------------------------------------
# Test DB setup (same pattern as the other test files)
# ---------------------------------------------------------------------------

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
    Base.metadata.drop_all(bind=_TEST_ENGINE)


client = TestClient(app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# Mock + seed helpers
# ---------------------------------------------------------------------------


def _nl_output(
    kind="expense",
    amount=1200.0,
    occurred_on=None,
    account_name=None,
    category_name=None,
    note="groceries",
) -> _NLParse:
    """Build the structured object the NL parser chain returns for one sentence."""
    return _NLParse(
        kind=kind,
        amount=amount,
        occurred_on=occurred_on,
        account_name=account_name,
        category_name=category_name,
        note=note,
    )


def _invoke_mock(mock_get_llm):
    """Return the .invoke mock at the end of the get_llm(...).with_structured_output(...) chain."""
    return mock_get_llm.return_value.with_structured_output.return_value.invoke


def _seed_account(name="Cash", type="cash") -> int:
    db = _TestSession()
    acc = Account(name=name, type=type)
    db.add(acc)
    db.commit()
    db.refresh(acc)
    db.close()
    return acc.id


def _seed_category(name="Groceries", kind="expense", parent_id=None) -> int:
    db = _TestSession()
    cat = Category(name=name, kind=kind, parent_id=parent_id)
    db.add(cat)
    db.commit()
    db.refresh(cat)
    db.close()
    return cat.id


def _seed_rule(pattern: str, category_id: int, priority: int = 0) -> int:
    db = _TestSession()
    rule = CategorizationRule(
        pattern=pattern, field="note", category_id=category_id, priority=priority
    )
    db.add(rule)
    db.commit()
    db.refresh(rule)
    db.close()
    return rule.id


def _post(text="spent 1200 on groceries", default_account_id=1):
    return client.post(
        "/api/ai/nl-input",
        json={"text": text, "default_account_id": default_account_id},
    )


# ---------------------------------------------------------------------------
# 1. Happy path
# ---------------------------------------------------------------------------


def test_basic_expense_parsed():
    """A simple sentence parses into a draft with matched account + category."""
    acc_id = _seed_account("HDFC", "bank")
    cat_id = _seed_category("Groceries", "expense")

    with patch("app.services.nl_input.get_llm") as mock_llm:
        _invoke_mock(mock_llm).return_value = _nl_output(
            kind="expense",
            amount=1200.0,
            occurred_on="2026-06-20",
            account_name="HDFC",
            category_name="Groceries",
            note="DMart groceries",
        )
        resp = _post(default_account_id=acc_id)

    assert resp.status_code == 200
    data = resp.json()
    assert data["kind"] == "expense"
    assert data["amount_minor"] == 120000
    assert data["occurred_on"] == "2026-06-20"
    assert data["account_id"] == acc_id
    assert data["account_name"] == "HDFC"
    assert data["category_id"] == cat_id
    assert data["category_name"] == "Groceries"
    assert data["category_source"] == "matched"
    assert data["note"] == "DMart groceries"


def test_nothing_is_inserted():
    """The endpoint only drafts — it must not create a transaction row."""
    acc_id = _seed_account()
    _seed_category("Groceries")

    with patch("app.services.nl_input.get_llm") as mock_llm:
        _invoke_mock(mock_llm).return_value = _nl_output(category_name="Groceries")
        _post(default_account_id=acc_id)

    db = _TestSession()
    from app.models import Transaction

    assert db.query(Transaction).count() == 0
    db.close()


# ---------------------------------------------------------------------------
# 2. Amount resolution (Python, not the model)
# ---------------------------------------------------------------------------


def test_amount_converted_to_paise():
    """Rupees from the model become paise via round(amount * 100)."""
    acc_id = _seed_account()

    with patch("app.services.nl_input.get_llm") as mock_llm:
        _invoke_mock(mock_llm).return_value = _nl_output(amount=12.10)
        resp = _post(default_account_id=acc_id)

    assert resp.status_code == 200
    # 12.10 * 100 = 1209.9999… in float; round() must give exactly 1210.
    assert resp.json()["amount_minor"] == 1210


def test_missing_amount_returns_422():
    """No amount in the text → 422, since we can't draft a transaction without one."""
    acc_id = _seed_account()

    with patch("app.services.nl_input.get_llm") as mock_llm:
        _invoke_mock(mock_llm).return_value = _nl_output(amount=None)
        resp = _post(text="bought groceries yesterday", default_account_id=acc_id)

    assert resp.status_code == 422
    assert "amount" in resp.json()["detail"].lower()


# ---------------------------------------------------------------------------
# 3. Dates
# ---------------------------------------------------------------------------


def test_relative_date_resolved_to_iso():
    """The model resolves 'yesterday' to an ISO date; the service passes it through."""
    acc_id = _seed_account()

    with patch("app.services.nl_input.get_llm") as mock_llm:
        _invoke_mock(mock_llm).return_value = _nl_output(occurred_on="2026-05-15")
        resp = _post(default_account_id=acc_id)

    assert resp.json()["occurred_on"] == "2026-05-15"


def test_missing_date_defaults_to_today():
    """No date from the model → default to today."""
    acc_id = _seed_account()

    with patch("app.services.nl_input.get_llm") as mock_llm:
        _invoke_mock(mock_llm).return_value = _nl_output(occurred_on=None)
        resp = _post(default_account_id=acc_id)

    assert resp.json()["occurred_on"] == date.today().isoformat()


def test_malformed_date_defaults_to_today():
    """A garbage date from the model must never crash — fall back to today."""
    acc_id = _seed_account()

    with patch("app.services.nl_input.get_llm") as mock_llm:
        _invoke_mock(mock_llm).return_value = _nl_output(occurred_on="not-a-date")
        resp = _post(default_account_id=acc_id)

    assert resp.status_code == 200
    assert resp.json()["occurred_on"] == date.today().isoformat()


# ---------------------------------------------------------------------------
# 4. Account resolution
# ---------------------------------------------------------------------------


def test_account_matched_by_name():
    """A named account in the list resolves to that account, not the default."""
    default_id = _seed_account("Cash", "cash")
    hdfc_id = _seed_account("HDFC", "bank")

    with patch("app.services.nl_input.get_llm") as mock_llm:
        _invoke_mock(mock_llm).return_value = _nl_output(account_name="hdfc")  # case-insensitive
        resp = _post(default_account_id=default_id)

    assert resp.json()["account_id"] == hdfc_id


def test_missing_account_uses_default():
    """No account named → fall back to default_account_id."""
    default_id = _seed_account("Cash", "cash")
    _seed_account("HDFC", "bank")

    with patch("app.services.nl_input.get_llm") as mock_llm:
        _invoke_mock(mock_llm).return_value = _nl_output(account_name=None)
        resp = _post(default_account_id=default_id)

    assert resp.json()["account_id"] == default_id


def test_unknown_account_name_uses_default():
    """An account name that isn't in the list → fall back to default_account_id."""
    default_id = _seed_account("Cash", "cash")

    with patch("app.services.nl_input.get_llm") as mock_llm:
        _invoke_mock(mock_llm).return_value = _nl_output(account_name="Some Random Bank")
        resp = _post(default_account_id=default_id)

    assert resp.json()["account_id"] == default_id


def test_bad_default_account_returns_422():
    """A default_account_id that doesn't exist → 422 (nothing safe to draft against)."""
    with patch("app.services.nl_input.get_llm") as mock_llm:
        _invoke_mock(mock_llm).return_value = _nl_output()
        resp = _post(default_account_id=999)

    assert resp.status_code == 422
    assert "default_account_id" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# 5. Category resolution
# ---------------------------------------------------------------------------


def test_unknown_category_falls_back_to_rule():
    """An unmatched category routes to categorize.suggest; a saved rule fires (source=rule)."""
    acc_id = _seed_account()
    cat_id = _seed_category("Dining Out", "expense")
    _seed_rule("(?i)swiggy", cat_id)

    with patch("app.services.nl_input.get_llm") as mock_llm:
        _invoke_mock(mock_llm).return_value = _nl_output(
            category_name=None, note="Swiggy dinner order"
        )
        resp = _post(default_account_id=acc_id)

    data = resp.json()
    assert data["category_id"] == cat_id
    assert data["category_name"] == "Dining Out"
    assert data["category_source"] == "rule"


def test_unknown_category_no_match_returns_null():
    """No category match and no rule → category left blank; card shows an empty category."""
    acc_id = _seed_account()
    _seed_category("Groceries", "expense")  # exists but the model didn't pick it

    with patch("app.services.nl_input.get_llm") as mock_llm:
        _invoke_mock(mock_llm).return_value = _nl_output(
            category_name=None, note="mystery purchase"
        )
        resp = _post(default_account_id=acc_id)

    data = resp.json()
    assert data["category_id"] is None
    assert data["category_name"] is None
    assert data["category_source"] == "none"  # no exact match, no rule fired


def test_category_kind_mismatch_is_not_matched():
    """A category name matching the wrong kind must not be exact-matched (save would reject it)."""
    acc_id = _seed_account()
    # "Bonus" is income; the draft is an expense, so the exact match must be skipped.
    _seed_category("Bonus", "income")

    with patch("app.services.nl_input.get_llm") as mock_llm:
        _invoke_mock(mock_llm).return_value = _nl_output(
            kind="expense", category_name="Bonus", note="something"
        )
        resp = _post(default_account_id=acc_id)

    data = resp.json()
    # No exact match (kind mismatch) and no rule → falls through to null.
    assert data["category_source"] != "matched"
    assert data["category_id"] is None


# ---------------------------------------------------------------------------
# 6. Kind
# ---------------------------------------------------------------------------


def test_income_kind_parsed():
    """An income sentence resolves to kind=income with an income category matched."""
    acc_id = _seed_account()
    cat_id = _seed_category("Salary", "income")

    with patch("app.services.nl_input.get_llm") as mock_llm:
        _invoke_mock(mock_llm).return_value = _nl_output(
            kind="income", amount=85000.0, category_name="Salary", note="June salary"
        )
        resp = _post(text="got salary of 85000 today", default_account_id=acc_id)

    data = resp.json()
    assert data["kind"] == "income"
    assert data["amount_minor"] == 8500000
    assert data["category_id"] == cat_id


def test_invalid_kind_coerced_to_expense():
    """An unexpected kind from the model is coerced to 'expense' (the common case)."""
    acc_id = _seed_account()

    with patch("app.services.nl_input.get_llm") as mock_llm:
        _invoke_mock(mock_llm).return_value = _nl_output(kind="transfer")
        resp = _post(default_account_id=acc_id)

    assert resp.json()["kind"] == "expense"


# ---------------------------------------------------------------------------
# 7. Golden set — 10 phrases parse to the right amount + kind
# ---------------------------------------------------------------------------

# Each entry: (text, parsed _NLParse fields, expected amount_minor, expected kind).
_GOLDEN = [
    ("groceries at DMart 1200 yesterday", dict(kind="expense", amount=1200.0), 120000, "expense"),
    ("got salary of 85000 today", dict(kind="income", amount=85000.0), 8500000, "income"),
    ("paid 15000 rent for May", dict(kind="expense", amount=15000.0), 1500000, "expense"),
    ("coffee for 180 at Blue Tokai", dict(kind="expense", amount=180.0), 18000, "expense"),
    ("uber back from airport 450", dict(kind="expense", amount=450.0), 45000, "expense"),
    ("received 2000 refund from Amazon", dict(kind="income", amount=2000.0), 200000, "income"),
    ("electricity bill 2340", dict(kind="expense", amount=2340.0), 234000, "expense"),
    ("dividend of 560 credited", dict(kind="income", amount=560.0), 56000, "income"),
    ("movie tickets 750.50", dict(kind="expense", amount=750.50), 75050, "expense"),
    ("gym membership 1499", dict(kind="expense", amount=1499.0), 149900, "expense"),
]


@pytest.mark.parametrize("text,fields,expected_minor,expected_kind", _GOLDEN)
def test_golden_set(text, fields, expected_minor, expected_kind):
    """10 realistic phrases each resolve to the correct paise amount and kind."""
    acc_id = _seed_account()

    with patch("app.services.nl_input.get_llm") as mock_llm:
        _invoke_mock(mock_llm).return_value = _nl_output(note=text, **fields)
        resp = _post(text=text, default_account_id=acc_id)

    assert resp.status_code == 200
    data = resp.json()
    assert data["amount_minor"] == expected_minor
    assert data["kind"] == expected_kind

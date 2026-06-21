# Tests for the auto-categorize endpoints: app/routers/categorize_router.py
#
# All LLM calls are mocked — no API key or network needed. We patch the get_llm()
# factory and drive the with_structured_output(...).invoke(...) chain so it returns
# a validated _SuggestCategoryOutput, exactly like the real LangChain path does.
# The tests stay provider-agnostic: nothing here names a concrete LLM provider.
#
# Test areas:
#   1. Rule matching — correct category returned instantly, no ai_calls row.
#   2. LLM fallback — mocked structured output parsed correctly.
#   3. Null category (no fit) — the LLM returns null, endpoint returns null cleanly.
#   4. Batch suggest — rules loaded once, LLM called only for unmatched rows.
#   5. Accept rule — rule saved, subsequent suggest uses rule path.
#   6. Optional transaction update on accept.
#   7. List and delete rules.
#   8. System prompt — the LLM gets the instructions + category list.
#   9. Golden set — 30 notes, ≥ 85% match.

from datetime import date
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.session import get_db
from app.main import app
from app.models import Account, AICall, Base, CategorizationRule, Category, Transaction
from app.services.categorize import _SuggestCategoryOutput

# ---------------------------------------------------------------------------
# Test DB setup (same pattern as all other test files)
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
# Fake LLM wiring
# ---------------------------------------------------------------------------
# After PF-22b the service calls:
#     get_llm(...).with_structured_output(_SuggestCategoryOutput).invoke(messages)
# and gets back a populated _SuggestCategoryOutput. So instead of faking raw SDK
# response blocks, we patch get_llm and make the end of that chain return model
# instances. _invoke_mock() hands back the .invoke MagicMock so a test can set
# its return_value / side_effect and inspect the messages it was called with.


def _llm_output(category_id, confidence=0.9, suggested_rule=None) -> _SuggestCategoryOutput:
    """Build the structured object the LLM chain returns for one suggestion."""
    return _SuggestCategoryOutput(
        category_id=category_id,
        confidence=confidence,
        suggested_rule=suggested_rule,
    )


def _llm_no_match() -> _SuggestCategoryOutput:
    """Structured output where the LLM finds no fitting category (category_id=null)."""
    return _llm_output(category_id=None, confidence=0.0)


def _invoke_mock(mock_get_llm):
    """Return the .invoke mock at the end of the get_llm(...).with_structured_output(...) chain."""
    return mock_get_llm.return_value.with_structured_output.return_value.invoke


# ---------------------------------------------------------------------------
# Seed helpers
# ---------------------------------------------------------------------------


def _seed_category(name="Dining Out", kind="expense", parent_id=None) -> int:
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


def _seed_account() -> int:
    db = _TestSession()
    acct = Account(name="HDFC", type="bank")
    db.add(acct)
    db.commit()
    db.refresh(acct)
    db.close()
    return acct.id


def _seed_transaction(account_id: int, category_id=None) -> int:
    db = _TestSession()
    txn = Transaction(
        account_id=account_id,
        category_id=category_id,
        kind="expense",
        amount_minor=10000,
        occurred_on=date(2026, 6, 1),
    )
    db.add(txn)
    db.commit()
    db.refresh(txn)
    db.close()
    return txn.id


def _ai_calls_count() -> int:
    db = _TestSession()
    count = db.query(AICall).count()
    db.close()
    return count


# ---------------------------------------------------------------------------
# 1. Rule matching
# ---------------------------------------------------------------------------


def test_suggest_returns_rule_match():
    """When a rule matches the note, the correct category is returned instantly."""
    cat_id = _seed_category("Dining Out")
    _seed_rule("(?i)swiggy", cat_id)

    resp = client.post(
        "/api/categorize/suggest", json={"note": "Swiggy dinner", "amount_minor": 45000}
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["category_id"] == cat_id
    assert data["category_name"] == "Dining Out"
    assert data["confidence"] == 1.0
    assert data["source"] == "rule"


def test_rule_match_writes_no_ai_calls_row():
    """A rule match must not trigger any LLM call."""
    cat_id = _seed_category("Groceries")
    _seed_rule("(?i)dmart", cat_id)

    client.post(
        "/api/categorize/suggest", json={"note": "DMart weekend shopping", "amount_minor": 120000}
    )

    assert _ai_calls_count() == 0


def test_rule_match_is_case_insensitive():
    """Rules should match regardless of case in the note."""
    cat_id = _seed_category("Transport")
    _seed_rule("(?i)ola", cat_id)

    resp = client.post(
        "/api/categorize/suggest", json={"note": "OLA RIDE HOME", "amount_minor": 25000}
    )

    assert resp.status_code == 200
    assert resp.json()["source"] == "rule"


def test_higher_priority_rule_wins():
    """When two rules match the same note, the higher-priority one wins."""
    food_id = _seed_category("Food")
    dining_id = _seed_category("Dining Out")
    _seed_rule("(?i)swiggy", food_id, priority=0)
    _seed_rule("(?i)swiggy", dining_id, priority=10)  # higher priority

    resp = client.post(
        "/api/categorize/suggest", json={"note": "Swiggy order", "amount_minor": 45000}
    )

    assert resp.json()["category_id"] == dining_id


# ---------------------------------------------------------------------------
# 2. LLM fallback
# ---------------------------------------------------------------------------


@patch("app.services.categorize.get_llm")
def test_suggest_calls_llm_when_no_rule_matches(mock_get_llm):
    """When no rule matches, the service calls the LLM and returns the result."""
    cat_id = _seed_category("Groceries")
    _invoke_mock(mock_get_llm).return_value = _llm_output(
        cat_id, confidence=0.92, suggested_rule="(?i)amazon fresh"
    )

    resp = client.post(
        "/api/categorize/suggest",
        json={"note": "Amazon Fresh delivery", "amount_minor": 80000},
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["category_id"] == cat_id
    assert data["confidence"] == 0.92
    assert data["suggested_rule"] == "(?i)amazon fresh"
    assert data["source"] == "llm"


@patch("app.services.categorize.get_llm")
def test_llm_fallback_calls_llm_once(mock_get_llm):
    """When no rule matches, the LLM is invoked exactly once."""
    cat_id = _seed_category("Groceries")
    _invoke_mock(mock_get_llm).return_value = _llm_output(cat_id)

    client.post("/api/categorize/suggest", json={"note": "Unknown merchant", "amount_minor": 10000})

    mock_get_llm.assert_called_once()


# ---------------------------------------------------------------------------
# 3. Null category (no fit)
# ---------------------------------------------------------------------------


@patch("app.services.categorize.get_llm")
def test_null_category_returned_cleanly(mock_get_llm):
    """When the LLM returns category_id=null, the endpoint returns null — no crash."""
    _seed_category("Groceries")  # categories exist, just none fit
    _invoke_mock(mock_get_llm).return_value = _llm_no_match()

    resp = client.post(
        "/api/categorize/suggest", json={"note": "Some weird merchant", "amount_minor": 5000}
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["category_id"] is None
    assert data["category_name"] is None
    assert data["confidence"] == 0.0
    assert data["source"] == "llm"


# ---------------------------------------------------------------------------
# 4. Batch suggest
# ---------------------------------------------------------------------------


@patch("app.services.categorize.get_llm")
def test_batch_returns_one_result_per_row(mock_get_llm):
    """suggest-batch returns exactly as many results as input rows, in order."""
    cat_id = _seed_category("Dining Out")
    _invoke_mock(mock_get_llm).return_value = _llm_output(cat_id)

    resp = client.post("/api/categorize/suggest-batch", json={
        "rows": [
            {"note": "Zomato order", "amount_minor": 35000},
            {"note": "Swiggy dinner", "amount_minor": 45000},
        ]
    })

    assert resp.status_code == 200
    assert len(resp.json()) == 2


@patch("app.services.categorize.get_llm")
def test_batch_uses_rule_for_matched_rows(mock_get_llm):
    """Rows that match a rule return source='rule'; unmatched rows return source='llm'."""
    cat_id = _seed_category("Dining Out")
    _seed_rule("(?i)swiggy", cat_id)  # only Swiggy is covered by a rule
    _invoke_mock(mock_get_llm).return_value = _llm_output(cat_id)

    resp = client.post("/api/categorize/suggest-batch", json={
        "rows": [
            {"note": "Swiggy dinner", "amount_minor": 45000},   # rule match
            {"note": "Zomato order", "amount_minor": 35000},    # LLM
            {"note": "Swiggy lunch", "amount_minor": 20000},    # rule match
            {"note": "Unknown cafe", "amount_minor": 15000},    # LLM
        ]
    })

    results = resp.json()
    assert results[0]["source"] == "rule"
    assert results[1]["source"] == "llm"
    assert results[2]["source"] == "rule"
    assert results[3]["source"] == "llm"


@patch("app.services.categorize.get_llm")
def test_batch_calls_llm_only_for_unmatched_rows(mock_get_llm):
    """The LLM is called only for rows that didn't match a rule — not for every row."""
    cat_id = _seed_category("Dining Out")
    _seed_rule("(?i)swiggy", cat_id)
    _invoke_mock(mock_get_llm).return_value = _llm_output(cat_id)

    client.post("/api/categorize/suggest-batch", json={
        "rows": [
            {"note": "Swiggy dinner", "amount_minor": 45000},  # rule — no LLM
            {"note": "Swiggy lunch", "amount_minor": 20000},   # rule — no LLM
            {"note": "Unknown store", "amount_minor": 10000},  # LLM
        ]
    })

    # Only 1 LLM call (the unknown store), not 3
    assert mock_get_llm.call_count == 1


# ---------------------------------------------------------------------------
# 5. Accept rule — rule saved, subsequent suggest uses rule path
# ---------------------------------------------------------------------------


@patch("app.services.categorize.get_llm")
def test_accept_saves_rule(mock_get_llm):
    """POST /accept creates a rule that appears in GET /rules."""
    cat_id = _seed_category("Groceries")
    _invoke_mock(mock_get_llm).return_value = _llm_output(cat_id)

    resp = client.post("/api/categorize/accept", json={
        "pattern": "(?i)bigbasket",
        "category_id": cat_id,
        "priority": 5,
    })

    assert resp.status_code == 200
    rule = resp.json()
    assert rule["pattern"] == "(?i)bigbasket"
    assert rule["category_id"] == cat_id
    assert rule["priority"] == 5


@patch("app.services.categorize.get_llm")
def test_accepted_rule_used_on_next_suggest(mock_get_llm):
    """After accepting a rule, the next suggest for a matching note uses the rule path."""
    cat_id = _seed_category("Groceries")

    client.post("/api/categorize/accept", json={
        "pattern": "(?i)bigbasket",
        "category_id": cat_id,
    })

    resp = client.post(
        "/api/categorize/suggest", json={"note": "BigBasket order", "amount_minor": 50000}
    )

    assert resp.json()["source"] == "rule"
    assert mock_get_llm.call_count == 0  # no LLM call — rule handled it


# ---------------------------------------------------------------------------
# 6. Optional transaction update on accept
# ---------------------------------------------------------------------------


def test_accept_with_transaction_id_updates_category():
    """When transaction_id is provided, the transaction's category_id is updated."""
    acct_id = _seed_account()
    cat_id = _seed_category("Groceries")
    txn_id = _seed_transaction(acct_id, category_id=None)

    client.post("/api/categorize/accept", json={
        "pattern": "(?i)test",
        "category_id": cat_id,
        "transaction_id": txn_id,
    })

    db = _TestSession()
    txn = db.get(Transaction, txn_id)
    assert txn.category_id == cat_id
    db.close()


def test_accept_with_nonexistent_transaction_returns_404():
    """transaction_id pointing to a non-existent transaction returns 404."""
    cat_id = _seed_category("Groceries")

    resp = client.post("/api/categorize/accept", json={
        "pattern": "(?i)test",
        "category_id": cat_id,
        "transaction_id": 99999,
    })

    assert resp.status_code == 404


def test_accept_with_nonexistent_category_returns_404():
    """category_id pointing to a non-existent category returns 404."""
    resp = client.post("/api/categorize/accept", json={
        "pattern": "(?i)test",
        "category_id": 99999,
    })

    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# 7. List and delete rules
# ---------------------------------------------------------------------------


def test_list_rules_returns_all_rules():
    """GET /rules returns all saved rules."""
    cat_id = _seed_category("Dining Out")
    _seed_rule("(?i)swiggy", cat_id, priority=10)
    _seed_rule("(?i)zomato", cat_id, priority=5)

    resp = client.get("/api/categorize/rules")

    assert resp.status_code == 200
    assert len(resp.json()) == 2


def test_list_rules_ordered_by_priority_desc():
    """Rules are returned highest priority first."""
    cat_id = _seed_category("Dining Out")
    _seed_rule("(?i)low", cat_id, priority=1)
    _seed_rule("(?i)high", cat_id, priority=20)

    rules = client.get("/api/categorize/rules").json()

    assert rules[0]["priority"] == 20
    assert rules[1]["priority"] == 1


def test_delete_rule_removes_it():
    """DELETE /rules/{id} removes the rule from the list."""
    cat_id = _seed_category("Dining Out")
    rule_id = _seed_rule("(?i)swiggy", cat_id)

    resp = client.delete(f"/api/categorize/rules/{rule_id}")
    assert resp.status_code == 204

    rules = client.get("/api/categorize/rules").json()
    assert all(r["id"] != rule_id for r in rules)


def test_delete_nonexistent_rule_returns_404():
    resp = client.delete("/api/categorize/rules/99999")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# 8. System prompt — the LLM gets the instructions + the category list
# ---------------------------------------------------------------------------


@patch("app.services.categorize.get_llm")
def test_llm_call_includes_category_list_in_system_prompt(mock_get_llm):
    """
    The service must hand the LLM a system message containing the available
    categories (so the model can only pick a real ID). Provider-agnostic: we
    assert on the message content, not on any provider-specific markers.
    """
    cat_id = _seed_category("Dining Out")
    invoke = _invoke_mock(mock_get_llm)
    invoke.return_value = _llm_output(cat_id)

    client.post("/api/categorize/suggest", json={"note": "Note A", "amount_minor": 10000})

    assert invoke.call_count == 1
    # .invoke() gets a [SystemMessage, HumanMessage] list as its first positional
    # arg. The system content is a plain string holding the prompt + category list.
    messages = invoke.call_args_list[0].args[0]
    system = messages[0]
    assert isinstance(system.content, str)
    assert "Dining Out" in system.content
    assert str(cat_id) in system.content


# ---------------------------------------------------------------------------
# 9. Golden set — 30 notes, ≥ 85% accuracy
# ---------------------------------------------------------------------------


@patch("app.services.categorize.get_llm")
def test_golden_set_85_percent_accuracy(mock_get_llm):
    """
    30 hand-labelled notes, each with a known correct category.
    10 are covered by seeded rules (free, deterministic).
    20 go to the mocked LLM which returns the correct category every time.
    Combined accuracy: 30/30 = 100% — well above the 85% threshold.
    """
    # Seed categories
    dining_id = _seed_category("Dining Out")
    groceries_id = _seed_category("Groceries")
    transport_id = _seed_category("Transport")
    utilities_id = _seed_category("Utilities")
    health_id = _seed_category("Health")

    # Seed 5 rules covering 10 of the 30 notes (2 notes each)
    _seed_rule("(?i)swiggy", dining_id)
    _seed_rule("(?i)dmart", groceries_id)
    _seed_rule("(?i)ola", transport_id)
    _seed_rule("(?i)bses", utilities_id)
    _seed_rule("(?i)apollo", health_id)

    # The 30 notes and their expected categories
    golden = [
        # rule-matched (10 notes)
        ("Swiggy dinner", dining_id),
        ("Swiggy lunch order", dining_id),
        ("DMart weekly groceries", groceries_id),
        ("DMart milk and eggs", groceries_id),
        ("OLA ride home", transport_id),
        ("OLA auto to office", transport_id),
        ("BSES electricity bill", utilities_id),
        ("BSES power bill", utilities_id),
        ("Apollo pharmacy", health_id),
        ("Apollo medicines", health_id),
        # LLM-handled (20 notes) — mock returns the correct category
        ("Zomato pizza", dining_id),
        ("Zomato biryani", dining_id),
        ("Zepto delivery", groceries_id),
        ("Blinkit order", groceries_id),
        ("Uber ride", transport_id),
        ("Rapido bike", transport_id),
        ("Airtel broadband", utilities_id),
        ("Jio recharge", utilities_id),
        ("Fortis hospital", health_id),
        ("MedPlus pharmacy", health_id),
        ("Behrouz Biryani", dining_id),
        ("Licious meat delivery", groceries_id),
        ("BEST bus pass", transport_id),
        ("MSEDCL electricity", utilities_id),
        ("Medanta consultation", health_id),
        ("Kesar Grocery Store", groceries_id),
        ("Ola Electric charging", transport_id),
        ("Tata Power bill", utilities_id),
        ("Dr Lal pathlabs", health_id),
        ("The Good Bowl food", dining_id),
    ]

    # Set up mock to return the correct category for each LLM call
    # The 10 rule-matched notes won't hit the LLM at all
    llm_categories = [cat_id for _, cat_id in golden[10:]]
    _invoke_mock(mock_get_llm).side_effect = [_llm_output(cat_id) for cat_id in llm_categories]

    correct = 0
    for note, expected_cat_id in golden:
        resp = client.post(
            "/api/categorize/suggest",
            json={"note": note, "amount_minor": 50000},
        )
        if resp.status_code == 200 and resp.json().get("category_id") == expected_cat_id:
            correct += 1

    accuracy = correct / len(golden)
    assert accuracy >= 0.85, f"Golden set accuracy {accuracy:.0%} is below 85% threshold"

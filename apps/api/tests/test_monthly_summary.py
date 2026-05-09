# Tests for the Monthly Cashflow Summary endpoint.
#
# Uses a 3-month fixture with known values so every field can be asserted exactly.
#
# Fixture (April, May, June 2026):
#   April:  income=500000, expense=300000, invest=200000
#           savings=0,     expense_pct=0.60, invest_pct=0.40, savings_pct=0.00
#   May:    income=500000, expense=150000, invest=100000
#           savings=250000, expense_pct=0.30, invest_pct=0.20, savings_pct=0.50
#   June:   income=0,      expense=50000,  invest=0
#           savings=-50000, all pcts=None (income==0)

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

def _create_account(name="HDFC Savings", account_type="bank"):
    resp = client.post("/api/accounts", json={"name": name, "type": account_type})
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def _create_category(name, kind):
    resp = client.post("/api/categories", json={"name": name, "kind": kind})
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def _create_txn(account_id, category_id, kind, amount_minor, occurred_on):
    resp = client.post("/api/transactions", json={
        "account_id": account_id,
        "category_id": category_id,
        "kind": kind,
        "amount_minor": amount_minor,
        "occurred_on": occurred_on,
    })
    assert resp.status_code == 201, resp.text


def _create_instrument(symbol="HDFCBANK"):
    resp = client.post("/api/instruments", json={
        "symbol": symbol, "name": symbol,
        "kind": "stock", "current_price_minor": 160000,
    })
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def _create_buy(account_id, instrument_id, quantity, price_minor, fee_minor, occurred_on):
    resp = client.post("/api/investment-txns", json={
        "account_id": account_id,
        "instrument_id": instrument_id,
        "side": "buy",
        "quantity": quantity,
        "price_minor": price_minor,
        "fee_minor": fee_minor,
        "occurred_on": occurred_on,
    })
    assert resp.status_code == 201, resp.text


@pytest.fixture()
def seeded(setup_db):
    """
    Seeds 3 months of known data.

    April 2026:
      income  = 500,000 paise (₹5,000)
      expense = 300,000 paise (₹3,000)
      invest  = 1×200000 + 0 fee = 200,000 paise (₹2,000 buy)
      savings = 500000 - 300000 - 200000 = 0

    May 2026:
      income  = 500,000 paise
      expense = 150,000 paise
      invest  = 1×100000 + 0 fee = 100,000 paise
      savings = 250,000 paise

    June 2026:
      income  = 0 (no income transactions)
      expense = 50,000 paise
      invest  = 0 (no buys)
      all pcts = None
    """
    account_id = _create_account()
    broker_id = _create_account(name="Zerodha", account_type="broker")
    salary_id = _create_category("Salary", "income")
    food_id = _create_category("Food", "expense")
    instr_id = _create_instrument()

    # April
    _create_txn(account_id, salary_id, "income", 500_000, "2026-04-01")
    _create_txn(account_id, food_id, "expense", 300_000, "2026-04-15")
    _create_buy(broker_id, instr_id, 1, 200_000, 0, "2026-04-20")

    # May
    _create_txn(account_id, salary_id, "income", 500_000, "2026-05-01")
    _create_txn(account_id, food_id, "expense", 150_000, "2026-05-15")
    _create_buy(broker_id, instr_id, 1, 100_000, 0, "2026-05-20")

    # June — no income, one expense, no investment
    _create_txn(account_id, food_id, "expense", 50_000, "2026-06-10")

    return {"account_id": account_id, "broker_id": broker_id}


# ---------------------------------------------------------------------------
# Response structure
# ---------------------------------------------------------------------------

def test_returns_one_row_per_month(seeded):
    """A 3-month range should return exactly 3 rows."""
    resp = client.get("/api/analytics/monthly?from=2026-04-01&to=2026-06-30")
    assert resp.status_code == 200
    assert len(resp.json()) == 3


def test_rows_ordered_by_month_ascending(seeded):
    """Rows must be in chronological order (oldest month first)."""
    resp = client.get("/api/analytics/monthly?from=2026-04-01&to=2026-06-30")
    yms = [r["ym"] for r in resp.json()]
    assert yms == ["2026-04", "2026-05", "2026-06"]


# ---------------------------------------------------------------------------
# April — all fields non-None
# ---------------------------------------------------------------------------

def test_april_income_and_expense(seeded):
    resp = client.get("/api/analytics/monthly?from=2026-04-01&to=2026-04-30")
    row = resp.json()[0]
    assert row["ym"] == "2026-04"
    assert row["income_minor"] == 500_000
    assert row["expense_minor"] == 300_000
    assert row["invest_minor"] == 200_000
    assert row["savings_minor"] == 0  # 500000 - 300000 - 200000


def test_april_percentages(seeded):
    resp = client.get("/api/analytics/monthly?from=2026-04-01&to=2026-04-30")
    row = resp.json()[0]
    assert row["expense_pct"] == pytest.approx(0.60)   # 300000/500000
    assert row["invest_pct"] == pytest.approx(0.40)    # 200000/500000
    assert row["savings_pct"] == pytest.approx(0.0)    # 0/500000


# ---------------------------------------------------------------------------
# May — partial savings
# ---------------------------------------------------------------------------

def test_may_values(seeded):
    resp = client.get("/api/analytics/monthly?from=2026-05-01&to=2026-05-31")
    row = resp.json()[0]
    assert row["ym"] == "2026-05"
    assert row["income_minor"] == 500_000
    assert row["expense_minor"] == 150_000
    assert row["invest_minor"] == 100_000
    assert row["savings_minor"] == 250_000
    assert row["expense_pct"] == pytest.approx(0.30)
    assert row["invest_pct"] == pytest.approx(0.20)
    assert row["savings_pct"] == pytest.approx(0.50)


# ---------------------------------------------------------------------------
# June — zero income → all pcts None
# ---------------------------------------------------------------------------

def test_zero_income_month_has_null_percentages(seeded):
    """When income is 0, all *_pct fields must be None not 0.0."""
    resp = client.get("/api/analytics/monthly?from=2026-06-01&to=2026-06-30")
    row = resp.json()[0]
    assert row["ym"] == "2026-06"
    assert row["income_minor"] == 0
    assert row["expense_minor"] == 50_000
    assert row["invest_minor"] == 0
    assert row["savings_minor"] == -50_000  # 0 - 50000 - 0
    assert row["expense_pct"] is None
    assert row["invest_pct"] is None
    assert row["savings_pct"] is None


# ---------------------------------------------------------------------------
# Invest only counts buy-side (not sell/dividend)
# ---------------------------------------------------------------------------

def test_sell_and_dividend_not_counted_in_invest(seeded):
    """
    sell and dividend trades must not inflate invest_minor.
    Only buy-side cash outflows count as 'invested'.
    """
    ids = seeded
    # Add a sell and a dividend in April — these should not change invest_minor.
    instr_id = _create_instrument("RELIANCE")
    _create_buy(ids["broker_id"], instr_id, 5, 160_000, 0, "2026-04-02")
    client.post("/api/investment-txns", json={
        "account_id": ids["broker_id"],
        "instrument_id": instr_id,
        "side": "sell",
        "quantity": 2,
        "price_minor": 165_000,
        "occurred_on": "2026-04-25",
    })
    client.post("/api/investment-txns", json={
        "account_id": ids["broker_id"],
        "instrument_id": instr_id,
        "side": "dividend",
        "quantity": 1,
        "price_minor": 3_000,
        "occurred_on": "2026-04-28",
    })

    resp = client.get("/api/analytics/monthly?from=2026-04-01&to=2026-04-30")
    row = resp.json()[0]
    # Original buy (200000) + new buy (5×160000=800000) = 1,000,000
    # sell and dividend must NOT be included.
    assert row["invest_minor"] == 1_000_000


# ---------------------------------------------------------------------------
# Empty months still appear in range
# ---------------------------------------------------------------------------

def test_empty_months_in_range_still_returned(setup_db):
    """
    A date range with no data at all should still return a row per month,
    with zeros — so the frontend chart always has a complete x-axis skeleton.
    """
    resp = client.get("/api/analytics/monthly?from=2026-04-01&to=2026-06-30")
    assert resp.status_code == 200
    rows = resp.json()
    assert len(rows) == 3
    for row in rows:
        assert row["income_minor"] == 0
        assert row["expense_pct"] is None


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def test_inverted_date_range_returns_422(setup_db):
    resp = client.get("/api/analytics/monthly?from=2026-06-01&to=2026-04-01")
    assert resp.status_code == 422
    assert "from" in resp.json()["detail"].lower()


def test_missing_from_returns_422(setup_db):
    resp = client.get("/api/analytics/monthly?to=2026-06-30")
    assert resp.status_code == 422


def test_missing_to_returns_422(setup_db):
    resp = client.get("/api/analytics/monthly?from=2026-04-01")
    assert resp.status_code == 422

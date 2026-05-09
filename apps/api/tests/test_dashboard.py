# Tests for the Dashboard endpoint.
#
# All four blocks are tested with a 3-month fixture of known data so the exact
# numbers can be asserted. This is a "snapshot test" in spirit — if the math
# in analytics.py changes, these tests catch it immediately.
#
# Fixture summary (used across multiple tests):
#   April 2026:  income=500000, expense=300000  (₹5000 in, ₹3000 out)
#   May 2026:    income=500000, expense=200000  (₹5000 in, ₹2000 out)
#   June 2026:   income=500000, expense=400000  (₹5000 in, ₹4000 out)
#
#   Investment: 10 units HDFCBANK bought at ₹1,600 (current price ₹1,650)
#               5 units RELIANCE bought at ₹2,800 (current price ₹2,900)

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
    # Disable FK constraints during teardown so SQLAlchemy can drop tables in
    # any order without hitting FOREIGN KEY constraint failures.
    with _TEST_ENGINE.connect() as conn:
        conn.execute(__import__("sqlalchemy").text("PRAGMA foreign_keys=OFF"))
    Base.metadata.drop_all(bind=_TEST_ENGINE)
    with _TEST_ENGINE.connect() as conn:
        conn.execute(__import__("sqlalchemy").text("PRAGMA foreign_keys=ON"))


client = TestClient(app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------

def _seed_category(name, kind, parent_id=None):
    resp = client.post("/api/categories", json={
        "name": name, "kind": kind, "parent_id": parent_id
    })
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def _seed_account(name="HDFC Savings", account_type="bank"):
    resp = client.post("/api/accounts", json={"name": name, "type": account_type})
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def _seed_txn(account_id, category_id, kind, amount_minor, occurred_on):
    resp = client.post("/api/transactions", json={
        "account_id": account_id,
        "category_id": category_id,
        "kind": kind,
        "amount_minor": amount_minor,
        "occurred_on": occurred_on,
    })
    assert resp.status_code == 201, resp.text
    return resp.json()


def _seed_instrument(symbol, name, kind, price_minor):
    resp = client.post("/api/instruments", json={
        "symbol": symbol, "name": name, "kind": kind,
        "current_price_minor": price_minor,
    })
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def _seed_trade(account_id, instrument_id, quantity, price_minor, occurred_on):
    resp = client.post("/api/investment-txns", json={
        "account_id": account_id,
        "instrument_id": instrument_id,
        "side": "buy",
        "quantity": quantity,
        "price_minor": price_minor,
        "occurred_on": occurred_on,
    })
    assert resp.status_code == 201, resp.text
    return resp.json()


@pytest.fixture()
def seeded(setup_db):
    """
    Seeds a known 3-month dataset across all relevant tables.
    Returns a dict of IDs so individual tests can reference them.
    """
    account_id = _seed_account()
    broker_id = _seed_account(name="Zerodha", account_type="broker")

    # Categories
    salary_id = _seed_category("Salary", "income")
    food_id = _seed_category("Food", "expense")
    groceries_id = _seed_category("Groceries", "expense", parent_id=food_id)
    dining_id = _seed_category("Dining Out", "expense", parent_id=food_id)
    transport_id = _seed_category("Transport", "expense")

    # April 2026 — income ₹5,000, expense ₹3,000
    _seed_txn(account_id, salary_id, "income", 500_000, "2026-04-01")
    _seed_txn(account_id, groceries_id, "expense", 200_000, "2026-04-15")  # ₹2,000
    _seed_txn(account_id, dining_id, "expense", 100_000, "2026-04-20")     # ₹1,000

    # May 2026 — income ₹5,000, expense ₹2,000
    _seed_txn(account_id, salary_id, "income", 500_000, "2026-05-01")
    _seed_txn(account_id, groceries_id, "expense", 150_000, "2026-05-10")  # ₹1,500
    _seed_txn(account_id, transport_id, "expense", 50_000, "2026-05-20")   # ₹500

    # June 2026 — income ₹5,000, expense ₹4,000
    _seed_txn(account_id, salary_id, "income", 500_000, "2026-06-01")
    _seed_txn(account_id, groceries_id, "expense", 300_000, "2026-06-10")  # ₹3,000
    _seed_txn(account_id, dining_id, "expense", 100_000, "2026-06-25")     # ₹1,000

    # Investments
    hdfc_id = _seed_instrument("HDFCBANK", "HDFC Bank", "stock", 165_000)  # ₹1,650
    rel_id = _seed_instrument("RELIANCE", "Reliance", "stock", 290_000)    # ₹2,900
    _seed_trade(broker_id, hdfc_id, 10, 160_000, "2026-04-05")  # bought at ₹1,600
    _seed_trade(broker_id, rel_id, 5, 280_000, "2026-05-05")    # bought at ₹2,800

    return {
        "account_id": account_id,
        "broker_id": broker_id,
        "salary_id": salary_id,
        "food_id": food_id,
        "groceries_id": groceries_id,
        "dining_id": dining_id,
        "transport_id": transport_id,
        "hdfc_id": hdfc_id,
        "rel_id": rel_id,
    }


# ---------------------------------------------------------------------------
# Cashflow block
# ---------------------------------------------------------------------------

def test_cashflow_correct_for_single_month(seeded):
    """
    April: income=500000, expense=300000 → savings_rate = (500000-300000)/500000 = 0.4
    """
    resp = client.get("/api/dashboard?from=2026-04-01&to=2026-04-30")
    assert resp.status_code == 200
    cf = resp.json()["cashflow"]

    assert cf["income_minor"] == 500_000
    assert cf["expense_minor"] == 300_000
    assert cf["savings_rate"] == pytest.approx(0.4)


def test_cashflow_correct_across_three_months(seeded):
    """
    April+May+June: income=1500000, expense=900000 → savings_rate = 0.4
    """
    resp = client.get("/api/dashboard?from=2026-04-01&to=2026-06-30")
    cf = resp.json()["cashflow"]

    assert cf["income_minor"] == 1_500_000
    assert cf["expense_minor"] == 900_000
    assert cf["savings_rate"] == pytest.approx(0.4)


def test_cashflow_savings_rate_none_when_no_income(setup_db):
    """When there is no income in the period, savings_rate must be None not a divide-by-zero."""
    resp = client.get("/api/dashboard?from=2026-04-01&to=2026-04-30")
    assert resp.status_code == 200
    cf = resp.json()["cashflow"]
    assert cf["income_minor"] == 0
    assert cf["savings_rate"] is None


# ---------------------------------------------------------------------------
# Category breakdown block
# ---------------------------------------------------------------------------

def test_category_breakdown_ordered_by_spend(seeded):
    """
    Across all three months, Groceries=650000, Dining Out=200000, Transport=50000.
    Should be ordered descending.
    """
    resp = client.get("/api/dashboard?from=2026-04-01&to=2026-06-30")
    breakdown = resp.json()["by_category"]

    assert len(breakdown) == 3
    assert breakdown[0]["category_name"] == "Groceries"
    assert breakdown[0]["total_minor"] == 650_000  # 200k+150k+300k
    assert breakdown[0]["parent_name"] == "Food"

    assert breakdown[1]["category_name"] == "Dining Out"
    assert breakdown[1]["total_minor"] == 200_000  # 100k+100k
    assert breakdown[1]["parent_name"] == "Food"

    assert breakdown[2]["category_name"] == "Transport"
    assert breakdown[2]["total_minor"] == 50_000
    assert breakdown[2]["parent_name"] is None  # Transport has no parent


def test_category_breakdown_respects_date_range(seeded):
    """April only: Groceries=200000, Dining Out=100000. Transport not present."""
    resp = client.get("/api/dashboard?from=2026-04-01&to=2026-04-30")
    breakdown = resp.json()["by_category"]

    names = [b["category_name"] for b in breakdown]
    assert "Transport" not in names
    assert breakdown[0]["total_minor"] == 200_000


def test_category_breakdown_empty_when_no_expenses(setup_db):
    """No transactions → by_category should be an empty list."""
    resp = client.get("/api/dashboard?from=2026-04-01&to=2026-04-30")
    assert resp.json()["by_category"] == []


# ---------------------------------------------------------------------------
# Allocation block
# ---------------------------------------------------------------------------

def test_allocation_groups_by_instrument_kind(seeded):
    """
    Both HDFC and Reliance are stocks.
    HDFC market value: 10 × 165000 = 1,650,000
    Reliance market value: 5 × 290000 = 1,450,000
    Total: 3,100,000 → stock pct = 1.0 (100%)
    """
    resp = client.get("/api/dashboard?from=2026-04-01&to=2026-06-30")
    allocation = resp.json()["allocation"]

    assert len(allocation) == 1
    assert allocation[0]["kind"] == "stock"
    assert allocation[0]["market_value_minor"] == 3_100_000
    assert allocation[0]["pct"] == pytest.approx(1.0)


def test_allocation_multiple_kinds(seeded):
    """Add a mutual fund — allocation should split into stock and mutual_fund."""
    ids = seeded
    mf_id = _seed_instrument("PPFAS", "Parag Parikh Flexi Cap", "mutual_fund", 100_000)
    _seed_trade(ids["broker_id"], mf_id, 10, 95_000, "2026-04-10")

    resp = client.get("/api/dashboard?from=2026-04-01&to=2026-06-30")
    allocation = resp.json()["allocation"]

    kinds = {a["kind"]: a for a in allocation}
    assert "stock" in kinds
    assert "mutual_fund" in kinds
    # mutual_fund: 10 × 100000 = 1,000,000
    assert kinds["mutual_fund"]["market_value_minor"] == 1_000_000
    # All pcts should sum to ~1.0
    total_pct = sum(a["pct"] for a in allocation)
    assert total_pct == pytest.approx(1.0, abs=0.001)


def test_allocation_empty_with_no_trades(setup_db):
    """No investment trades → allocation should be an empty list."""
    resp = client.get("/api/dashboard?from=2026-04-01&to=2026-06-30")
    assert resp.json()["allocation"] == []


# ---------------------------------------------------------------------------
# Net worth series block
# ---------------------------------------------------------------------------

def test_networth_series_has_one_point_per_month(seeded):
    """A 3-month range should produce exactly 3 net-worth data points."""
    resp = client.get("/api/dashboard?from=2026-04-01&to=2026-06-30")
    series = resp.json()["networth_series"]
    assert len(series) == 3
    months = [p["month"] for p in series]
    assert months == ["2026-04", "2026-05", "2026-06"]


def test_networth_series_april_value(seeded):
    """
    April net worth:
      Cash: opening=0 + income=500000 - expense=300000 = 200000
      Holdings (using current prices for all months in V1):
        HDFC: 10 × 165000 = 1650000
        RELIANCE: 5 × 290000 = 1450000  (bought in May, but V1 uses all-time positions)
      Total = 200000 + 1650000 + 1450000 = 3300000
    """
    resp = client.get("/api/dashboard?from=2026-04-01&to=2026-06-30")
    series = resp.json()["networth_series"]
    april = next(p for p in series if p["month"] == "2026-04")
    assert april["networth_minor"] == 3_300_000


def test_networth_series_june_value(seeded):
    """
    June net worth (cumulative through June):
      Cash: 0 + (500k+500k+500k) - (300k+200k+400k) = 1500000 - 900000 = 600000
      Holdings: 1650000 + 1450000 = 3100000
      Total = 3700000
    """
    resp = client.get("/api/dashboard?from=2026-04-01&to=2026-06-30")
    series = resp.json()["networth_series"]
    june = next(p for p in series if p["month"] == "2026-06")
    assert june["networth_minor"] == 3_700_000


def test_networth_series_empty_with_no_data(setup_db):
    """No data → series should still return the month structure but with holdings=0."""
    resp = client.get("/api/dashboard?from=2026-04-01&to=2026-04-30")
    assert resp.status_code == 200
    series = resp.json()["networth_series"]
    assert len(series) == 1
    assert series[0]["month"] == "2026-04"
    assert series[0]["networth_minor"] == 0


# ---------------------------------------------------------------------------
# Missing required query params
# ---------------------------------------------------------------------------

def test_missing_from_param_returns_422(setup_db):
    """Both `from` and `to` are required — missing one should return 422."""
    resp = client.get("/api/dashboard?to=2026-04-30")
    assert resp.status_code == 422


def test_missing_to_param_returns_422(setup_db):
    resp = client.get("/api/dashboard?from=2026-04-01")
    assert resp.status_code == 422


def test_inverted_date_range_returns_422(setup_db):
    """from > to is an invalid range — should return 422 with a clear message."""
    resp = client.get("/api/dashboard?from=2026-05-09&to=2026-05-01")
    assert resp.status_code == 422
    assert "from" in resp.json()["detail"].lower()

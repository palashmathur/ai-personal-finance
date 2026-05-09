# Tests for the Unified Ledger endpoint.
#
# Key things tested:
#   1. Row count = transactions count + investment_txns count for the period (the AC).
#   2. source and kind values are correct for each row type.
#   3. Date range filter works — rows outside the range are excluded.
#   4. Ordering is occurred_on DESC.
#   5. Pagination (limit/offset) works correctly.
#   6. Inverted date range returns 422.
#   7. Investment amount_minor is computed correctly (buy = qty×price+fee, sell = qty×price-fee).

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
    # Disable FK constraints during teardown so tables drop in any order.
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
    return resp.json()


def _create_instrument(symbol, kind="stock", price=160000):
    resp = client.post("/api/instruments", json={
        "symbol": symbol, "name": symbol, "kind": kind,
        "current_price_minor": price,
    })
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def _create_trade(account_id, instrument_id, side, quantity, price_minor,
                  fee_minor=0, occurred_on="2026-04-01"):
    resp = client.post("/api/investment-txns", json={
        "account_id": account_id,
        "instrument_id": instrument_id,
        "side": side,
        "quantity": quantity,
        "price_minor": price_minor,
        "fee_minor": fee_minor,
        "occurred_on": occurred_on,
    })
    assert resp.status_code == 201, resp.text
    return resp.json()


# ---------------------------------------------------------------------------
# Row count = transactions + investment_txns (the AC)
# ---------------------------------------------------------------------------

def test_total_row_count_equals_transactions_plus_investment_txns():
    """
    The AC: row count must equal the number of transactions + investment_txns
    in the period. Seeds 3 transactions and 2 investment trades → expect 5 rows.
    """
    account_id = _create_account()
    broker_id = _create_account(name="Zerodha", account_type="broker")
    salary_id = _create_category("Salary", "income")
    food_id = _create_category("Food", "expense")
    instr_id = _create_instrument("HDFCBANK")

    _create_txn(account_id, salary_id, "income", 500_000, "2026-04-01")
    _create_txn(account_id, food_id, "expense", 100_000, "2026-04-10")
    _create_txn(account_id, food_id, "expense", 50_000, "2026-04-20")
    _create_trade(broker_id, instr_id, "buy", 10, 160_000, occurred_on="2026-04-05")
    _create_trade(broker_id, instr_id, "sell", 3, 165_000, occurred_on="2026-04-15")

    resp = client.get("/api/ledger?from=2026-04-01&to=2026-04-30&limit=200")
    assert resp.status_code == 200
    assert len(resp.json()) == 5


# ---------------------------------------------------------------------------
# source and kind values
# ---------------------------------------------------------------------------

def test_cash_rows_have_correct_source_and_kind():
    """Income and expense rows must have source='cash' and the correct kind."""
    account_id = _create_account()
    salary_id = _create_category("Salary", "income")
    food_id = _create_category("Food", "expense")

    _create_txn(account_id, salary_id, "income", 500_000, "2026-04-01")
    _create_txn(account_id, food_id, "expense", 100_000, "2026-04-10")

    resp = client.get("/api/ledger?from=2026-04-01&to=2026-04-30")
    rows = resp.json()

    sources = {r["kind"]: r for r in rows}
    assert sources["income"]["source"] == "cash"
    assert sources["expense"]["source"] == "cash"
    assert sources["income"]["category_id"] is not None
    assert sources["income"]["instrument_id"] is None


def test_investment_rows_have_correct_source_and_kind():
    """Buy/sell/dividend rows must have source='investment' and kind='inv_*'."""
    broker_id = _create_account(name="Zerodha", account_type="broker")
    instr_id = _create_instrument("HDFCBANK")

    _create_trade(broker_id, instr_id, "buy", 10, 160_000, occurred_on="2026-04-01")
    _create_trade(broker_id, instr_id, "sell", 5, 165_000, occurred_on="2026-04-10")
    client.post("/api/investment-txns", json={
        "account_id": broker_id, "instrument_id": instr_id,
        "side": "dividend", "quantity": 1, "price_minor": 5000,
        "occurred_on": "2026-04-15",
    })

    resp = client.get("/api/ledger?from=2026-04-01&to=2026-04-30")
    rows = {r["kind"]: r for r in resp.json()}

    assert rows["inv_buy"]["source"] == "investment"
    assert rows["inv_sell"]["source"] == "investment"
    assert rows["inv_dividend"]["source"] == "investment"
    # Investment rows must have instrument_id and no category_id.
    assert rows["inv_buy"]["instrument_id"] is not None
    assert rows["inv_buy"]["category_id"] is None
    assert rows["inv_buy"]["quantity"] == 10.0


# ---------------------------------------------------------------------------
# Investment amount_minor calculation
# ---------------------------------------------------------------------------

def test_buy_amount_includes_fee():
    """Buy amount = qty × price + fee."""
    broker_id = _create_account(name="Zerodha", account_type="broker")
    instr_id = _create_instrument("HDFCBANK")

    _create_trade(broker_id, instr_id, "buy", 10, 160_000, fee_minor=2000,
                  occurred_on="2026-04-01")

    resp = client.get("/api/ledger?from=2026-04-01&to=2026-04-30")
    buy_row = next(r for r in resp.json() if r["kind"] == "inv_buy")
    # 10 × 160000 + 2000 = 1,602,000
    assert buy_row["amount_minor"] == 1_602_000


def test_sell_amount_excludes_fee():
    """Sell amount = qty × price - fee (fee reduces proceeds)."""
    broker_id = _create_account(name="Zerodha", account_type="broker")
    instr_id = _create_instrument("HDFCBANK", price=165_000)

    _create_trade(broker_id, instr_id, "buy", 10, 160_000, occurred_on="2026-04-01")
    _create_trade(broker_id, instr_id, "sell", 5, 165_000, fee_minor=1000,
                  occurred_on="2026-04-10")

    resp = client.get("/api/ledger?from=2026-04-01&to=2026-04-30")
    sell_row = next(r for r in resp.json() if r["kind"] == "inv_sell")
    # 5 × 165000 - 1000 = 824,000
    assert sell_row["amount_minor"] == 824_000


# ---------------------------------------------------------------------------
# Date range filter
# ---------------------------------------------------------------------------

def test_date_range_excludes_rows_outside_period():
    """Rows outside the from/to window must not appear."""
    account_id = _create_account()
    salary_id = _create_category("Salary", "income")

    _create_txn(account_id, salary_id, "income", 500_000, "2026-03-15")  # before
    _create_txn(account_id, salary_id, "income", 500_000, "2026-04-15")  # inside
    _create_txn(account_id, salary_id, "income", 500_000, "2026-05-15")  # after

    resp = client.get("/api/ledger?from=2026-04-01&to=2026-04-30")
    rows = resp.json()
    assert len(rows) == 1
    assert rows[0]["occurred_on"] == "2026-04-15"


# ---------------------------------------------------------------------------
# Ordering
# ---------------------------------------------------------------------------

def test_rows_ordered_by_occurred_on_desc():
    """Most recent row must come first."""
    account_id = _create_account()
    salary_id = _create_category("Salary", "income")

    _create_txn(account_id, salary_id, "income", 100_000, "2026-04-01")
    _create_txn(account_id, salary_id, "income", 200_000, "2026-04-20")
    _create_txn(account_id, salary_id, "income", 300_000, "2026-04-10")

    resp = client.get("/api/ledger?from=2026-04-01&to=2026-04-30")
    dates = [r["occurred_on"] for r in resp.json()]
    assert dates == sorted(dates, reverse=True)


# ---------------------------------------------------------------------------
# Pagination
# ---------------------------------------------------------------------------

def test_limit_restricts_row_count():
    """?limit=2 should return at most 2 rows even if more exist."""
    account_id = _create_account()
    salary_id = _create_category("Salary", "income")
    for i in range(5):
        _create_txn(account_id, salary_id, "income", 100_000, f"2026-04-{i+1:02d}")

    resp = client.get("/api/ledger?from=2026-04-01&to=2026-04-30&limit=2")
    assert len(resp.json()) == 2


def test_offset_pages_correctly():
    """offset=2 with limit=2 should return rows 3 and 4 (0-indexed)."""
    account_id = _create_account()
    salary_id = _create_category("Salary", "income")
    # Create 4 transactions on different dates so ordering is deterministic.
    for day in [10, 8, 6, 4]:
        _create_txn(account_id, salary_id, "income", day * 10_000, f"2026-04-{day:02d}")

    # Page 1: rows 1-2 (most recent first → Apr 10, Apr 8)
    page1 = client.get("/api/ledger?from=2026-04-01&to=2026-04-30&limit=2&offset=0").json()
    # Page 2: rows 3-4 (Apr 6, Apr 4)
    page2 = client.get("/api/ledger?from=2026-04-01&to=2026-04-30&limit=2&offset=2").json()

    assert page1[0]["occurred_on"] == "2026-04-10"
    assert page2[0]["occurred_on"] == "2026-04-06"
    # No overlap between pages.
    page1_ids = {r["source_id"] for r in page1}
    page2_ids = {r["source_id"] for r in page2}
    assert page1_ids.isdisjoint(page2_ids)


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def test_inverted_date_range_returns_422():
    """from > to must return 422."""
    resp = client.get("/api/ledger?from=2026-04-30&to=2026-04-01")
    assert resp.status_code == 422
    assert "from" in resp.json()["detail"].lower()


def test_missing_from_returns_422():
    resp = client.get("/api/ledger?to=2026-04-30")
    assert resp.status_code == 422


def test_missing_to_returns_422():
    resp = client.get("/api/ledger?from=2026-04-01")
    assert resp.status_code == 422


def test_empty_period_returns_empty_list():
    """A valid range with no data should return [] not an error."""
    resp = client.get("/api/ledger?from=2026-04-01&to=2026-04-30")
    assert resp.status_code == 200
    assert resp.json() == []

# Tests for the Holdings endpoint.
#
# Holdings are a read-side aggregation over investment_txns — no separate table.
# The key things tested here:
#   1. qty = SUM(buy) - SUM(sell); fully sold positions (qty <= 0) are excluded.
#   2. cost_basis = SUM(buy qty × price + fee); sell-side fees don't affect cost basis.
#   3. market_value = qty × current_price_minor; None when instrument has no price.
#   4. unrealized_pnl = market_value - cost_basis; None when no price.
#   5. ?account_id= filter returns only holdings for that account.
#   6. Multiple instruments and multiple accounts are handled correctly.
#
# All monetary assertions use exact integers (paise) to catch any rounding bugs.

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
    """Apply the same PRAGMAs as production so FK constraints and WAL mode match."""
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
    """Fresh schema before every test; torn down after."""
    Base.metadata.create_all(bind=_TEST_ENGINE)
    app.dependency_overrides[get_db] = _override_get_db
    yield
    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=_TEST_ENGINE)


client = TestClient(app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _create_account(name="Zerodha", account_type="broker"):
    resp = client.post("/api/accounts", json={"name": name, "type": account_type})
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def _create_instrument(symbol="HDFCBANK", kind="stock", name="HDFC Bank Ltd", price=None):
    body = {"kind": kind, "symbol": symbol, "name": name}
    if price is not None:
        body["current_price_minor"] = price
    resp = client.post("/api/instruments", json=body)
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def _trade(account_id, instrument_id, side, quantity, price_minor, fee_minor=0,
           occurred_on="2026-04-01"):
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


def _set_price(instrument_id, price_minor):
    resp = client.patch(
        f"/api/instruments/{instrument_id}", json={"current_price_minor": price_minor}
    )
    assert resp.status_code == 200, resp.text


# ---------------------------------------------------------------------------
# Basic qty and cost_basis math
# ---------------------------------------------------------------------------

def test_single_buy_holding():
    """
    Buy 10 units at ₹1,600 with ₹20 fee.
    qty = 10, cost_basis = 10 × 160000 + 2000 = 1,602,000 paise.
    """
    account_id = _create_account()
    instrument_id = _create_instrument(price=160000)

    _trade(account_id, instrument_id, "buy", quantity=10, price_minor=160000, fee_minor=2000)

    resp = client.get("/api/holdings")
    assert resp.status_code == 200
    holdings = resp.json()
    assert len(holdings) == 1

    h = holdings[0]
    assert h["qty"] == 10.0
    assert h["cost_basis_minor"] == 1_602_000   # 10 × 160000 + 2000
    assert h["market_value_minor"] == 1_600_000  # 10 × 160000
    assert h["unrealized_pnl_minor"] == -2_000   # market_value - cost_basis (fee drag)
    assert h["instrument"]["symbol"] == "HDFCBANK"


def test_buy_then_partial_sell():
    """
    Buy 10 units, sell 3. Remaining qty = 7.
    cost_basis is only from the buy side — sell doesn't reduce it.
    """
    account_id = _create_account()
    instrument_id = _create_instrument(price=165000)

    _trade(account_id, instrument_id, "buy", quantity=10, price_minor=160000, fee_minor=0)
    _trade(account_id, instrument_id, "sell", quantity=3, price_minor=165000, fee_minor=0)

    resp = client.get("/api/holdings")
    holdings = resp.json()
    assert len(holdings) == 1

    h = holdings[0]
    assert h["qty"] == 7.0
    assert h["cost_basis_minor"] == 1_600_000   # only buy side: 10 × 160000
    assert h["market_value_minor"] == 1_155_000  # 7 × 165000
    assert h["unrealized_pnl_minor"] == -445_000  # 1_155_000 - 1_600_000


def test_fully_sold_position_excluded():
    """
    Buy 10 units, sell all 10. qty = 0 → position must not appear in holdings.
    """
    account_id = _create_account()
    instrument_id = _create_instrument(price=160000)

    _trade(account_id, instrument_id, "buy", quantity=10, price_minor=160000)
    _trade(account_id, instrument_id, "sell", quantity=10, price_minor=162000)

    resp = client.get("/api/holdings")
    assert resp.status_code == 200
    assert resp.json() == []


def test_dividend_does_not_change_qty():
    """
    Dividends are cash inflows — they must not add to or reduce the unit count.
    """
    account_id = _create_account()
    instrument_id = _create_instrument(price=160000)

    _trade(account_id, instrument_id, "buy", quantity=10, price_minor=160000)
    # Dividend: quantity=1, price_minor = total payout (convention from design doc).
    _trade(account_id, instrument_id, "dividend", quantity=1, price_minor=5000)

    resp = client.get("/api/holdings")
    holdings = resp.json()
    assert len(holdings) == 1
    # qty should still be 10, not 11 or 9.
    assert holdings[0]["qty"] == 10.0


def test_multiple_buys_accumulate_cost_basis():
    """
    Two buys at different prices — cost_basis should be the sum of both.
    SIP use case: buy 5 units in April at ₹1,600 and 5 units in May at ₹1,700.
    """
    account_id = _create_account()
    instrument_id = _create_instrument(price=170000)

    _trade(account_id, instrument_id, "buy", quantity=5, price_minor=160000,
           occurred_on="2026-04-01")
    _trade(account_id, instrument_id, "buy", quantity=5, price_minor=170000,
           occurred_on="2026-05-01")

    resp = client.get("/api/holdings")
    h = resp.json()[0]
    assert h["qty"] == 10.0
    assert h["cost_basis_minor"] == 5 * 160000 + 5 * 170000  # 1_650_000


# ---------------------------------------------------------------------------
# Instrument with no price set
# ---------------------------------------------------------------------------

def test_holding_with_no_price_returns_none_for_market_value():
    """
    When instrument.current_price_minor is NULL, market_value and unrealized_pnl
    must come back as None — not ₹0, which would be misleading.
    """
    account_id = _create_account()
    # Create instrument with no price.
    instrument_id = _create_instrument(price=None)
    # First trade bootstraps the instrument price — clear it to test the NULL path.
    _trade(account_id, instrument_id, "buy", quantity=10, price_minor=160000)
    # Manually wipe the price to simulate a stale/missing price scenario.
    client.patch(f"/api/instruments/{instrument_id}", json={"current_price_minor": None})

    resp = client.get("/api/holdings")
    h = resp.json()[0]
    assert h["qty"] == 10.0
    assert h["cost_basis_minor"] == 1_600_000
    assert h["market_value_minor"] is None
    assert h["unrealized_pnl_minor"] is None


# ---------------------------------------------------------------------------
# account_id filter
# ---------------------------------------------------------------------------

def test_filter_by_account_id():
    """
    ?account_id= should return only holdings for that account.
    Holdings in other accounts must not appear.
    """
    zerodha_id = _create_account(name="Zerodha", account_type="broker")
    groww_id = _create_account(name="Groww", account_type="broker")
    instrument_id = _create_instrument(price=160000)

    _trade(zerodha_id, instrument_id, "buy", quantity=10, price_minor=160000)
    _trade(groww_id, instrument_id, "buy", quantity=5, price_minor=160000)

    resp = client.get(f"/api/holdings?account_id={zerodha_id}")
    assert resp.status_code == 200
    holdings = resp.json()
    assert len(holdings) == 1
    assert holdings[0]["account_id"] == zerodha_id
    assert holdings[0]["qty"] == 10.0


def test_no_filter_returns_all_accounts():
    """Without ?account_id=, holdings from all accounts are returned."""
    zerodha_id = _create_account(name="Zerodha", account_type="broker")
    groww_id = _create_account(name="Groww", account_type="broker")
    instrument_id = _create_instrument(price=160000)

    _trade(zerodha_id, instrument_id, "buy", quantity=10, price_minor=160000)
    _trade(groww_id, instrument_id, "buy", quantity=5, price_minor=160000)

    resp = client.get("/api/holdings")
    assert resp.status_code == 200
    # Two rows: same instrument, two different accounts.
    assert len(resp.json()) == 2


# ---------------------------------------------------------------------------
# Multiple instruments
# ---------------------------------------------------------------------------

def test_multiple_instruments_each_get_their_own_row():
    """Each (account, instrument) pair gets its own holdings row."""
    account_id = _create_account()
    hdfc_id = _create_instrument(symbol="HDFCBANK", name="HDFC Bank", price=160000)
    reliance_id = _create_instrument(symbol="RELIANCE", name="Reliance", price=280000)

    _trade(account_id, hdfc_id, "buy", quantity=10, price_minor=160000)
    _trade(account_id, reliance_id, "buy", quantity=5, price_minor=280000)

    resp = client.get("/api/holdings")
    holdings = resp.json()
    assert len(holdings) == 2

    by_symbol = {h["instrument"]["symbol"]: h for h in holdings}
    assert by_symbol["HDFCBANK"]["qty"] == 10.0
    assert by_symbol["RELIANCE"]["qty"] == 5.0


# ---------------------------------------------------------------------------
# Empty state
# ---------------------------------------------------------------------------

def test_no_trades_returns_empty_list():
    """With no investment trades recorded, GET /api/holdings should return []."""
    resp = client.get("/api/holdings")
    assert resp.status_code == 200
    assert resp.json() == []


def test_account_id_filter_with_no_trades_returns_empty():
    """Filtering by an account that has no trades should return []."""
    account_id = _create_account()
    resp = client.get(f"/api/holdings?account_id={account_id}")
    assert resp.status_code == 200
    assert resp.json() == []

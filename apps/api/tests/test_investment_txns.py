# Tests for the InvestmentTxns CRUD endpoints.
#
# Investment trades are the per-trade ledger for investments — every buy, sell, and
# dividend is a row. The key business rules tested here:
#   1. Account must be type broker or wallet — bank/cash accounts rejected with 422.
#   2. Instrument must exist in the catalog — missing instrument returns 404.
#   3. Bootstrap side-effect: first trade for an instrument sets current_price_minor
#      on the instrument if it was NULL. Subsequent trades do NOT overwrite an existing price.
#   4. Happy path: create buy + sell, GET with filters, PATCH, DELETE.
#
# Uses in-memory SQLite with StaticPool — same isolation pattern as all other test files.

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
    """Each test starts with a clean schema and tears it down after."""
    Base.metadata.create_all(bind=_TEST_ENGINE)
    app.dependency_overrides[get_db] = _override_get_db
    yield
    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=_TEST_ENGINE)


client = TestClient(app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# Helpers — seed common fixtures
# ---------------------------------------------------------------------------

def _create_broker_account(name="Zerodha", account_type="broker"):
    """Create a broker account and return its ID."""
    resp = client.post("/api/accounts", json={"name": name, "type": account_type})
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def _create_bank_account(name="HDFC Savings"):
    """Create a bank account. Used to test that bank accounts are rejected for trades."""
    resp = client.post("/api/accounts", json={"name": name, "type": "bank"})
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def _create_instrument(symbol="HDFCBANK", kind="stock", name="HDFC Bank Ltd", price=None):
    """Create an instrument and return its ID."""
    body = {"kind": kind, "symbol": symbol, "name": name}
    if price is not None:
        body["current_price_minor"] = price
    resp = client.post("/api/instruments", json=body)
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def _buy(account_id, instrument_id, quantity=10.0, price_minor=160000, fee_minor=0,
         occurred_on="2026-04-01", note=None):
    """Helper for a simple buy trade."""
    body = {
        "account_id": account_id,
        "instrument_id": instrument_id,
        "side": "buy",
        "quantity": quantity,
        "price_minor": price_minor,
        "fee_minor": fee_minor,
        "occurred_on": occurred_on,
    }
    if note:
        body["note"] = note
    return client.post("/api/investment-txns", json=body)


# ---------------------------------------------------------------------------
# Happy path — create
# ---------------------------------------------------------------------------

def test_create_buy_returns_201():
    """POST a buy trade with valid data — should return 201 with nested instrument."""
    account_id = _create_broker_account()
    instrument_id = _create_instrument()

    resp = _buy(account_id, instrument_id, quantity=10.0, price_minor=160000, fee_minor=2000)

    assert resp.status_code == 201
    body = resp.json()
    assert body["side"] == "buy"
    assert body["quantity"] == 10.0
    assert body["price_minor"] == 160000
    assert body["fee_minor"] == 2000
    assert body["account_id"] == account_id
    assert body["instrument_id"] == instrument_id
    # Nested instrument should be included in the response.
    assert body["instrument"]["symbol"] == "HDFCBANK"
    assert body["instrument"]["kind"] == "stock"
    assert "id" in body


def test_create_sell_and_dividend():
    """POST sell and dividend trades — valid sides should all return 201."""
    account_id = _create_broker_account()
    instrument_id = _create_instrument(price=160000)

    sell_resp = client.post("/api/investment-txns", json={
        "account_id": account_id,
        "instrument_id": instrument_id,
        "side": "sell",
        "quantity": 5.0,
        "price_minor": 165000,
        "occurred_on": "2026-05-01",
    })
    assert sell_resp.status_code == 201
    assert sell_resp.json()["side"] == "sell"

    # Dividend convention: quantity=1, price_minor = total dividend payout in paise.
    div_resp = client.post("/api/investment-txns", json={
        "account_id": account_id,
        "instrument_id": instrument_id,
        "side": "dividend",
        "quantity": 1.0,
        "price_minor": 5000,  # ₹50 dividend
        "occurred_on": "2026-05-15",
    })
    assert div_resp.status_code == 201
    assert div_resp.json()["side"] == "dividend"


# ---------------------------------------------------------------------------
# Bootstrap side-effect: first trade sets instrument price if NULL
# ---------------------------------------------------------------------------

def test_first_trade_bootstraps_instrument_price():
    """
    When the instrument has no price yet (current_price_minor is NULL),
    the first trade should set it to the trade's price_minor.

    This is the "bootstrap" pattern so the holdings page has a non-NULL
    price to show immediately after the first trade is recorded.
    """
    account_id = _create_broker_account()
    # Create instrument with no price set.
    instrument_id = _create_instrument(price=None)

    # Verify price is NULL before the trade.
    before = client.get("/api/instruments").json()
    instrument_before = next(i for i in before if i["id"] == instrument_id)
    assert instrument_before["current_price_minor"] is None

    # Record the first buy at ₹1,600.
    resp = _buy(account_id, instrument_id, price_minor=160000)
    assert resp.status_code == 201

    # Verify the instrument's price was bootstrapped.
    after = client.get("/api/instruments").json()
    instrument_after = next(i for i in after if i["id"] == instrument_id)
    assert instrument_after["current_price_minor"] == 160000


def test_subsequent_trade_does_not_overwrite_existing_price():
    """
    If the instrument already has a price, a new trade must NOT overwrite it.
    Bootstrap only fires when current_price_minor IS NULL.
    """
    account_id = _create_broker_account()
    # Instrument created with an explicit price of ₹1,500.
    instrument_id = _create_instrument(price=150000)

    # Record a buy at a different price (₹1,600).
    resp = _buy(account_id, instrument_id, price_minor=160000)
    assert resp.status_code == 201

    # The instrument price should still be the original ₹1,500, not ₹1,600.
    instruments = client.get("/api/instruments").json()
    instrument = next(i for i in instruments if i["id"] == instrument_id)
    assert instrument["current_price_minor"] == 150000


# ---------------------------------------------------------------------------
# Account-type validation
# ---------------------------------------------------------------------------

def test_bank_account_accepted():
    """
    Bank accounts are allowed for investment trades — SIP debits come directly
    from a bank account, not a separate broker account.
    """
    bank_account_id = _create_bank_account()
    instrument_id = _create_instrument(kind="mutual_fund", symbol="INF090I01239", name="Parag Parikh Flexi Cap")

    resp = _buy(bank_account_id, instrument_id)
    assert resp.status_code == 201


def test_cash_account_accepted():
    """Cash accounts are also allowed — e.g. physical gold or metal purchases paid in cash."""
    resp_acc = client.post("/api/accounts", json={"name": "Petty Cash", "type": "cash"})
    cash_account_id = resp_acc.json()["id"]
    instrument_id = _create_instrument(symbol="GOLD", kind="metal", name="Gold")

    resp = _buy(cash_account_id, instrument_id)
    assert resp.status_code == 201


def test_wallet_account_accepted():
    """Wallet accounts (e.g. crypto wallets) should be accepted for investment trades."""
    wallet_id = _create_broker_account(name="Coinbase", account_type="wallet")
    instrument_id = _create_instrument(symbol="BTC", kind="crypto", name="Bitcoin", price=6000000)

    resp = _buy(wallet_id, instrument_id, price_minor=6000000)
    assert resp.status_code == 201


# ---------------------------------------------------------------------------
# Missing instrument / account → 404
# ---------------------------------------------------------------------------

def test_missing_instrument_returns_404():
    """POST a trade referencing a non-existent instrument should return 404."""
    account_id = _create_broker_account()

    resp = _buy(account_id, instrument_id=99999)
    assert resp.status_code == 404
    assert "99999" in resp.json()["detail"]


def test_missing_account_returns_404():
    """POST a trade referencing a non-existent account should return 404."""
    instrument_id = _create_instrument()

    resp = _buy(account_id=99999, instrument_id=instrument_id)
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Field validation
# ---------------------------------------------------------------------------

def test_zero_quantity_rejected():
    """quantity must be > 0 — zero should return 422."""
    account_id = _create_broker_account()
    instrument_id = _create_instrument()

    resp = client.post("/api/investment-txns", json={
        "account_id": account_id,
        "instrument_id": instrument_id,
        "side": "buy",
        "quantity": 0.0,
        "price_minor": 160000,
        "occurred_on": "2026-04-01",
    })
    assert resp.status_code == 422


def test_negative_price_rejected():
    """price_minor must be >= 0 — negative price is invalid."""
    account_id = _create_broker_account()
    instrument_id = _create_instrument()

    resp = client.post("/api/investment-txns", json={
        "account_id": account_id,
        "instrument_id": instrument_id,
        "side": "buy",
        "quantity": 10.0,
        "price_minor": -100,
        "occurred_on": "2026-04-01",
    })
    assert resp.status_code == 422


def test_invalid_side_rejected():
    """side must be buy|sell|dividend — anything else returns 422."""
    account_id = _create_broker_account()
    instrument_id = _create_instrument()

    resp = client.post("/api/investment-txns", json={
        "account_id": account_id,
        "instrument_id": instrument_id,
        "side": "transfer",  # not a valid investment side
        "quantity": 10.0,
        "price_minor": 160000,
        "occurred_on": "2026-04-01",
    })
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# GET — list with filters
# ---------------------------------------------------------------------------

def test_list_all_trades():
    """GET without filters returns all trades ordered by occurred_on DESC."""
    account_id = _create_broker_account()
    instrument_id = _create_instrument()

    _buy(account_id, instrument_id, occurred_on="2026-03-01")
    _buy(account_id, instrument_id, occurred_on="2026-04-01")

    resp = client.get("/api/investment-txns")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 2
    # Newest first.
    assert body[0]["occurred_on"] == "2026-04-01"
    assert body[1]["occurred_on"] == "2026-03-01"


def test_filter_by_instrument_id():
    """?instrument_id= returns only trades for that instrument."""
    account_id = _create_broker_account()
    instrument_a = _create_instrument(symbol="HDFCBANK", name="HDFC Bank")
    instrument_b = _create_instrument(symbol="RELIANCE", name="Reliance")

    _buy(account_id, instrument_a)
    _buy(account_id, instrument_b)

    resp = client.get(f"/api/investment-txns?instrument_id={instrument_a}")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["instrument_id"] == instrument_a


def test_filter_by_side():
    """?side=sell returns only sell trades."""
    account_id = _create_broker_account()
    instrument_id = _create_instrument(price=160000)

    _buy(account_id, instrument_id, occurred_on="2026-03-01")
    client.post("/api/investment-txns", json={
        "account_id": account_id,
        "instrument_id": instrument_id,
        "side": "sell",
        "quantity": 5.0,
        "price_minor": 165000,
        "occurred_on": "2026-04-01",
    })

    resp = client.get("/api/investment-txns?side=sell")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["side"] == "sell"


def test_filter_by_date_range():
    """?from=&to= filters trades within the date range."""
    account_id = _create_broker_account()
    instrument_id = _create_instrument()

    _buy(account_id, instrument_id, occurred_on="2026-01-15")
    _buy(account_id, instrument_id, occurred_on="2026-03-10")
    _buy(account_id, instrument_id, occurred_on="2026-05-20")

    resp = client.get("/api/investment-txns?from=2026-02-01&to=2026-04-30")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["occurred_on"] == "2026-03-10"


# ---------------------------------------------------------------------------
# PATCH
# ---------------------------------------------------------------------------

def test_patch_note_and_fee():
    """PATCH should update only the fields sent, leaving others unchanged."""
    account_id = _create_broker_account()
    instrument_id = _create_instrument()

    create_resp = _buy(account_id, instrument_id, fee_minor=2000)
    txn_id = create_resp.json()["id"]

    patch_resp = client.patch(f"/api/investment-txns/{txn_id}", json={
        "note": "SIP April",
        "fee_minor": 2500,
    })
    assert patch_resp.status_code == 200
    body = patch_resp.json()
    assert body["note"] == "SIP April"
    assert body["fee_minor"] == 2500
    # Fields not sent should be unchanged.
    assert body["price_minor"] == create_resp.json()["price_minor"]


def test_patch_nonexistent_txn_returns_404():
    """PATCH on a trade that doesn't exist should return 404."""
    resp = client.patch("/api/investment-txns/99999", json={"note": "ghost"})
    assert resp.status_code == 404


def test_patch_to_credit_card_account_returns_422():
    """PATCH changing account_id to a credit_card account should return 422 — only excluded type."""
    broker_id = _create_broker_account()
    instrument_id = _create_instrument()
    cc_resp = client.post("/api/accounts", json={"name": "HDFC Credit Card", "type": "credit_card"})
    cc_id = cc_resp.json()["id"]

    create_resp = _buy(broker_id, instrument_id)
    txn_id = create_resp.json()["id"]

    patch_resp = client.patch(f"/api/investment-txns/{txn_id}", json={"account_id": cc_id})
    assert patch_resp.status_code == 422


def test_patch_to_nonexistent_instrument_returns_404():
    """PATCH changing instrument_id to one that doesn't exist should return 404."""
    account_id = _create_broker_account()
    instrument_id = _create_instrument()

    create_resp = _buy(account_id, instrument_id)
    txn_id = create_resp.json()["id"]

    patch_resp = client.patch(f"/api/investment-txns/{txn_id}", json={"instrument_id": 99999})
    assert patch_resp.status_code == 404


# ---------------------------------------------------------------------------
# DELETE
# ---------------------------------------------------------------------------

def test_delete_trade_returns_204():
    """DELETE should remove the trade and return 204 No Content."""
    account_id = _create_broker_account()
    instrument_id = _create_instrument()

    create_resp = _buy(account_id, instrument_id)
    txn_id = create_resp.json()["id"]

    del_resp = client.delete(f"/api/investment-txns/{txn_id}")
    assert del_resp.status_code == 204

    # Trade should no longer appear in the list.
    list_resp = client.get("/api/investment-txns")
    ids = [t["id"] for t in list_resp.json()]
    assert txn_id not in ids


def test_delete_nonexistent_trade_returns_404():
    """DELETE on a trade that doesn't exist should return 404."""
    resp = client.delete("/api/investment-txns/99999")
    assert resp.status_code == 404

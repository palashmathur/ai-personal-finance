# Tests for the Instruments CRUD endpoints.
#
# Instruments are the catalog of investable things (stocks, MFs, ETFs, crypto, metals).
# The key business rules tested here:
#   1. Duplicate (kind, symbol) is rejected with 409.
#   2. Search is case-insensitive and matches both symbol and name.
#   3. PATCH only updates the fields that are sent — true PATCH semantics.
#   4. price_updated_at is stamped automatically when current_price_minor is set.
#
# Uses an in-memory SQLite DB with StaticPool — same isolation pattern as all other test files.

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
    """
    Runs before every test — creates a clean schema, wires the test DB override,
    then tears everything down afterwards. Each test gets a completely fresh DB.
    """
    Base.metadata.create_all(bind=_TEST_ENGINE)
    app.dependency_overrides[get_db] = _override_get_db
    yield
    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=_TEST_ENGINE)


client = TestClient(app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _create_instrument(kind="stock", symbol="HDFCBANK", name="HDFC Bank Ltd", **kwargs):
    """Convenience wrapper so tests don't repeat the full POST body each time."""
    return client.post("/api/instruments", json={
        "kind": kind,
        "symbol": symbol,
        "name": name,
        **kwargs,
    })


# ---------------------------------------------------------------------------
# Happy path — create
# ---------------------------------------------------------------------------

def test_create_instrument_returns_201():
    """POST with valid data should create the instrument and return 201."""
    response = _create_instrument(
        kind="stock",
        symbol="HDFCBANK",
        name="HDFC Bank Ltd",
        current_price_minor=162400,  # ₹1,624
        meta={"exchange": "NSE", "isin": "INE040A01034"},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["kind"] == "stock"
    assert body["symbol"] == "HDFCBANK"
    assert body["name"] == "HDFC Bank Ltd"
    assert body["current_price_minor"] == 162400
    assert body["meta"]["exchange"] == "NSE"
    assert "id" in body
    # price_updated_at should be set since we provided a price at creation.
    assert body["price_updated_at"] is not None


def test_create_instrument_without_price_returns_201():
    """current_price_minor is optional — creating without it should succeed."""
    response = _create_instrument(name="Some Mutual Fund", kind="mutual_fund", symbol="INF090I01239")

    assert response.status_code == 201
    body = response.json()
    assert body["current_price_minor"] is None
    # No price means price_updated_at should also be None.
    assert body["price_updated_at"] is None


# ---------------------------------------------------------------------------
# Duplicate (kind, symbol) → 409
# ---------------------------------------------------------------------------

def test_create_duplicate_kind_symbol_returns_409():
    """
    (kind, symbol) must be unique. Creating the same combo twice is rejected with 409.
    This is the primary duplicate-guard for the catalog.
    """
    _create_instrument(kind="stock", symbol="HDFCBANK", name="HDFC Bank Ltd")

    response = _create_instrument(kind="stock", symbol="HDFCBANK", name="HDFC Bank Different Name")

    assert response.status_code == 409
    body = response.json()
    assert body["code"] == "conflict"
    assert "HDFCBANK" in body["detail"]


def test_duplicate_check_is_case_insensitive():
    """Symbols 'hdfcbank' and 'HDFCBANK' with the same kind should collide."""
    _create_instrument(kind="stock", symbol="HDFCBANK", name="HDFC Bank Ltd")

    response = _create_instrument(kind="stock", symbol="hdfcbank", name="HDFC Bank lowercase")

    assert response.status_code == 409
    assert response.json()["code"] == "conflict"


def test_same_symbol_different_kind_is_allowed():
    """
    The same symbol is allowed under different kinds — e.g. NIFTYBEES could be both
    a stock ticker and classified as an ETF in different contexts.
    The uniqueness is (kind, symbol) together, not just symbol.
    """
    _create_instrument(kind="stock", symbol="NIFTYBEES", name="Nippon Nifty BeES (Stock)")
    response = _create_instrument(kind="etf", symbol="NIFTYBEES", name="Nippon Nifty BeES (ETF)")

    assert response.status_code == 201


# ---------------------------------------------------------------------------
# Search — case-insensitive, matches symbol and name
# ---------------------------------------------------------------------------

def test_search_by_symbol():
    """?q= should match on symbol, case-insensitively."""
    _create_instrument(kind="stock", symbol="HDFCBANK", name="HDFC Bank Ltd")
    _create_instrument(kind="stock", symbol="ICICIBANK", name="ICICI Bank Ltd")

    response = client.get("/api/instruments?search=hdfc")

    assert response.status_code == 200
    results = response.json()
    assert len(results) == 1
    assert results[0]["symbol"] == "HDFCBANK"


def test_search_by_name():
    """?q= should also match on name, not just symbol."""
    _create_instrument(kind="mutual_fund", symbol="INF090I01239", name="Parag Parikh Flexi Cap")
    _create_instrument(kind="mutual_fund", symbol="INF204K01EZ2", name="Axis Bluechip Fund")

    response = client.get("/api/instruments?search=parag")

    assert response.status_code == 200
    results = response.json()
    assert len(results) == 1
    assert results[0]["name"] == "Parag Parikh Flexi Cap"


def test_search_returns_results_ordered_by_name():
    """Results should be alphabetically ordered by name so the typeahead is predictable."""
    _create_instrument(kind="stock", symbol="ZOMATO", name="Zomato Ltd")
    _create_instrument(kind="stock", symbol="TATAMOTORS", name="Tata Motors Ltd")
    _create_instrument(kind="stock", symbol="AAPL", name="Apple Inc")

    # All three names contain the letter 'a' — search should return them alphabetically.
    response = client.get("/api/instruments?search=a")

    assert response.status_code == 200
    names = [r["name"] for r in response.json()]
    assert names == sorted(names)


def test_list_all_returns_all_instruments_when_no_search_param():
    """GET /api/instruments with no params should return every instrument ordered by name."""
    _create_instrument(kind="stock", symbol="ZOMATO", name="Zomato Ltd")
    _create_instrument(kind="stock", symbol="HDFCBANK", name="HDFC Bank Ltd")
    _create_instrument(kind="mutual_fund", symbol="INF090I01239", name="Parag Parikh Flexi Cap")

    response = client.get("/api/instruments")

    assert response.status_code == 200
    names = [r["name"] for r in response.json()]
    assert len(names) == 3
    assert names == sorted(names)


def test_search_empty_string_returns_all_instruments():
    """?search= (blank value) should behave like no param — returns all instruments."""
    _create_instrument(kind="stock", symbol="HDFCBANK", name="HDFC Bank Ltd")
    _create_instrument(kind="stock", symbol="ICICIBANK", name="ICICI Bank Ltd")

    response = client.get("/api/instruments?search=")

    assert response.status_code == 200
    assert len(response.json()) == 2


def test_search_no_match_returns_empty_list():
    """A search term that matches nothing should return an empty list, not a 404."""
    _create_instrument(kind="stock", symbol="HDFCBANK", name="HDFC Bank Ltd")

    response = client.get("/api/instruments?search=zzznomatch")

    assert response.status_code == 200
    assert response.json() == []


# ---------------------------------------------------------------------------
# PATCH — partial update
# ---------------------------------------------------------------------------

def test_patch_updates_only_supplied_fields():
    """
    PATCH should change only what's in the request body and leave everything else alone.
    This verifies true PATCH semantics vs PUT (which would replace the whole resource).
    """
    instrument_id = _create_instrument(
        kind="stock", symbol="HDFCBANK", name="HDFC Bank Ltd"
    ).json()["id"]

    response = client.patch(f"/api/instruments/{instrument_id}", json={"name": "HDFC Bank Limited"})

    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "HDFC Bank Limited"
    assert body["symbol"] == "HDFCBANK"   # unchanged
    assert body["kind"] == "stock"        # unchanged


def test_patch_price_stamps_price_updated_at():
    """
    When current_price_minor is updated via PATCH, price_updated_at should be
    automatically set — so the UI can track price freshness and show a stale-price badge.
    """
    instrument_id = _create_instrument(
        kind="crypto", symbol="BTC", name="Bitcoin"
    ).json()["id"]

    # No price yet — price_updated_at should be None.
    created = client.get(f"/api/instruments?q=BTC").json()[0]
    assert created["price_updated_at"] is None

    response = client.patch(
        f"/api/instruments/{instrument_id}",
        json={"current_price_minor": 6500000000},  # ₹65,000 in paise
    )

    assert response.status_code == 200
    body = response.json()
    assert body["current_price_minor"] == 6500000000
    assert body["price_updated_at"] is not None


def test_patch_meta_merges_correctly():
    """PATCH on meta should replace the whole meta dict (not deep-merge within it)."""
    instrument_id = _create_instrument(
        kind="stock",
        symbol="RELIANCE",
        name="Reliance Industries",
        meta={"exchange": "NSE", "isin": "INE002A01018"},
    ).json()["id"]

    response = client.patch(
        f"/api/instruments/{instrument_id}",
        json={"meta": {"exchange": "NSE", "isin": "INE002A01018", "sector": "Energy"}},
    )

    assert response.status_code == 200
    assert response.json()["meta"]["sector"] == "Energy"


# ---------------------------------------------------------------------------
# 404 cases
# ---------------------------------------------------------------------------

def test_patch_nonexistent_instrument_returns_404():
    response = client.patch("/api/instruments/99999", json={"name": "Ghost"})
    assert response.status_code == 404
    assert response.json()["code"] == "not_found"


# ---------------------------------------------------------------------------
# Validation — bad kind enum
# ---------------------------------------------------------------------------

def test_create_invalid_kind_returns_422():
    """An unknown instrument kind should be rejected at the schema level."""
    response = client.post("/api/instruments", json={
        "kind": "nft",  # not in the InstrumentKind enum
        "symbol": "BAYC",
        "name": "Bored Ape Yacht Club",
    })

    assert response.status_code == 422
    assert response.json()["code"] == "validation_error"

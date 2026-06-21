# Tests for the AI usage endpoint: GET /api/ai/usage
#
# We don't call any LLM API in these tests. Instead we insert AICall rows
# directly into the in-memory test database and verify the aggregation logic.
# This is the right approach because:
#   - The endpoint's job is to aggregate and format data from ai_calls, not to call the LLM.
#   - Real API calls would make tests slow, flaky, and cost money.
#
# The model id stored on each row is just opaque audit data here, so these tests
# use neutral placeholder model names — they assert on aggregation, not provider.

from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.session import get_db
from app.main import app
from app.models import AICall, Base

# ---------------------------------------------------------------------------
# Test database setup — mirrors the pattern used in all other test files.
# An in-memory SQLite database is created fresh for every test run.
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
# Helpers
# ---------------------------------------------------------------------------


def _insert_call(
    feature: str,
    model: str,
    input_tokens: int,
    output_tokens: int,
    cache_read_tokens: int = 0,
    cache_creation_tokens: int = 0,
    latency_ms: int = 100,
    created_at: datetime = None,
):
    """Insert one AICall row directly — no LLM API needed."""
    db = _TestSession()
    call = AICall(
        feature=feature,
        model=model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cache_read_tokens=cache_read_tokens,
        cache_creation_tokens=cache_creation_tokens,
        latency_ms=latency_ms,
        created_at=created_at or datetime(2026, 5, 10, 12, 0, 0),
    )
    db.add(call)
    db.commit()
    db.close()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_usage_empty_range():
    """No calls in DB returns zeros and null cache hit rate."""
    resp = client.get("/api/ai/usage?from=2026-05-01&to=2026-05-31")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_calls"] == 0
    assert body["total_input_tokens"] == 0
    assert body["estimated_cache_hit_rate"] is None
    assert body["by_feature"] == {}


def test_usage_aggregates_totals():
    """Tokens across multiple calls are summed correctly."""
    _insert_call("categorize", "model-fast", input_tokens=500, output_tokens=50)
    _insert_call("categorize", "model-fast", input_tokens=500, output_tokens=50)
    _insert_call("nl_input", "model-smart", input_tokens=800, output_tokens=200)

    resp = client.get("/api/ai/usage?from=2026-05-01&to=2026-05-31")
    assert resp.status_code == 200
    body = resp.json()

    assert body["total_calls"] == 3
    assert body["total_input_tokens"] == 1800   # 500 + 500 + 800
    assert body["total_output_tokens"] == 300   # 50 + 50 + 200


def test_usage_by_feature_breakdown():
    """Each feature appears separately in by_feature with its own totals."""
    _insert_call("categorize", "model-fast", input_tokens=400, output_tokens=40)
    _insert_call("nl_input", "model-smart", input_tokens=600, output_tokens=150)

    resp = client.get("/api/ai/usage?from=2026-05-01&to=2026-05-31")
    body = resp.json()

    assert "categorize" in body["by_feature"]
    assert "nl_input" in body["by_feature"]

    cat = body["by_feature"]["categorize"]
    assert cat["calls"] == 1
    assert cat["input_tokens"] == 400

    nl = body["by_feature"]["nl_input"]
    assert nl["calls"] == 1
    assert nl["input_tokens"] == 600


def test_usage_cache_hit_rate():
    """
    Cache hit rate = cache_read / (input + cache_read).

    Call 1 — no cache yet: 1000 input, 0 cache_read.
    Call 2 — cache hit: 100 input (the non-cached part), 900 cache_read.
    Total: input=1100, cache_read=900 → rate = 900/2000 = 0.45
    """
    _insert_call(
        "categorize", "model-fast",
        input_tokens=1000, output_tokens=50,
        cache_creation_tokens=1000,  # first call builds the cache
    )
    _insert_call(
        "categorize", "model-fast",
        input_tokens=100, output_tokens=50,
        cache_read_tokens=900,       # second call reads from cache
    )

    resp = client.get("/api/ai/usage?from=2026-05-01&to=2026-05-31")
    body = resp.json()

    assert body["total_cache_read_tokens"] == 900
    assert body["total_cache_creation_tokens"] == 1000
    # rate = 900 / (1100 + 900) = 900 / 2000 = 0.45
    assert abs(body["estimated_cache_hit_rate"] - 0.45) < 0.001


def test_usage_excludes_calls_outside_date_range():
    """Calls outside the requested date range are not counted."""
    # This call is in May — should be included.
    _insert_call(
        "categorize", "model-fast",
        input_tokens=500, output_tokens=50,
        created_at=datetime(2026, 5, 15, 10, 0, 0),
    )
    # This call is in April — should be excluded.
    _insert_call(
        "nl_input", "model-smart",
        input_tokens=800, output_tokens=100,
        created_at=datetime(2026, 4, 1, 10, 0, 0),
    )

    resp = client.get("/api/ai/usage?from=2026-05-01&to=2026-05-31")
    body = resp.json()

    assert body["total_calls"] == 1
    assert body["total_input_tokens"] == 500
    assert "nl_input" not in body["by_feature"]


def test_usage_invalid_date_range():
    """from > to returns 422."""
    resp = client.get("/api/ai/usage?from=2026-05-31&to=2026-05-01")
    assert resp.status_code == 422

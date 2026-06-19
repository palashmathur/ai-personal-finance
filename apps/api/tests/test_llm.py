# Tests for app/ai/llm.py and app/ai/audit.py.
#
# Two things to verify here:
#   1. When a LangChain LLM with our AuditCallbackHandler attached is invoked,
#      exactly one ai_calls row gets written with the right feature, model,
#      token counts and latency.
#   2. When the audit DB write blows up, the LLM call still succeeds.
#      Audit is observability — never let it break the user-facing request.
#
# We don't hit Anthropic from these tests. GenericFakeChatModel returns canned
# AIMessages with whatever usage_metadata we put on them, which is exactly what
# the audit callback reads — so we can assert exact token counts came through.

from unittest.mock import patch

import pytest
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.ai.audit import AuditCallbackHandler
from app.models import AICall, Base

# ---------------------------------------------------------------------------
# Test database setup
#
# The audit callback opens its own SessionLocal — it isn't a FastAPI route
# dependency, so app.dependency_overrides doesn't help us here. Instead we
# monkeypatch app.ai.audit.SessionLocal to point at an in-memory engine for
# each test. Same idea as overriding get_db in router tests, just at the
# import site that the callback actually uses.
# ---------------------------------------------------------------------------

_TEST_ENGINE = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)


@event.listens_for(_TEST_ENGINE, "connect")
def _set_pragmas(dbapi_conn, _):
    """Match production's pragmas so FK behaviour is consistent in tests."""
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


_TestSession = sessionmaker(bind=_TEST_ENGINE, autoflush=False, autocommit=False)


@pytest.fixture(autouse=True)
def setup_db(monkeypatch):
    """
    Recreate all tables before each test and point the audit callback's
    SessionLocal at our in-memory engine for the duration of the test.
    """
    Base.metadata.create_all(bind=_TEST_ENGINE)
    # The callback imports SessionLocal at module load time. Patching the
    # attribute on app.ai.audit (not app.db.session) is what actually swaps
    # the reference the callback uses.
    monkeypatch.setattr("app.ai.audit.SessionLocal", _TestSession)
    yield
    Base.metadata.drop_all(bind=_TEST_ENGINE)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _fake_ai_message() -> AIMessage:
    """
    A canned AIMessage with realistic usage_metadata.

    usage_metadata is LangChain's standard place for per-message token data —
    the AuditCallbackHandler reads from here, so putting known counts on this
    message is how the test controls what lands in the ai_calls row.
    """
    return AIMessage(
        content="pong",
        usage_metadata={
            "input_tokens": 12,
            "output_tokens": 3,
            "total_tokens": 15,
            "input_token_details": {
                "cache_read": 5,
                "cache_creation": 7,
            },
        },
        # response_metadata is where real chat providers stamp the resolved
        # model name. We mimic that here so the audit row's `model` column
        # is populated.
        response_metadata={"model": "fake-model-id"},
    )


def _ai_calls_count(feature: str) -> int:
    """Count rows in ai_calls for one feature. Fresh session per call."""
    with _TestSession() as session:
        return session.query(AICall).filter(AICall.feature == feature).count()


def _latest_ai_call(feature: str) -> dict:
    """
    Return the most recent ai_calls row for a feature as a plain dict.

    We materialise into a dict inside the session so the test can read the
    values after the session is closed without triggering lazy reloads.
    """
    with _TestSession() as session:
        row = (
            session.query(AICall)
            .filter(AICall.feature == feature)
            .order_by(AICall.id.desc())
            .first()
        )
        if row is None:
            return {}
        return {
            "feature": row.feature,
            "model": row.model,
            "input_tokens": row.input_tokens,
            "output_tokens": row.output_tokens,
            "cache_read_tokens": row.cache_read_tokens,
            "cache_creation_tokens": row.cache_creation_tokens,
            "latency_ms": row.latency_ms,
        }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_invoke_writes_one_ai_calls_row():
    """
    Happy path. A LangChain chat model with our audit callback attached,
    invoked once, writes exactly one ai_calls row with matching token counts.
    """
    feature = "test_invoke_audit"

    # GenericFakeChatModel never touches the network — it yields canned
    # AIMessages from the iterator we pass in. LangChain still fires the full
    # callback lifecycle around it, which is what we're actually testing.
    fake = GenericFakeChatModel(messages=iter([_fake_ai_message()]))
    fake.callbacks = [AuditCallbackHandler(feature=feature)]

    response = fake.invoke("ping")

    # Sanity: the LLM call returned cleanly.
    assert response.content == "pong"

    # Exactly one row landed, with the data we put on the fake message.
    assert _ai_calls_count(feature) == 1
    row = _latest_ai_call(feature)
    assert row["feature"] == feature
    assert row["model"] == "fake-model-id"
    assert row["input_tokens"] == 12
    assert row["output_tokens"] == 3
    assert row["cache_read_tokens"] == 5
    assert row["cache_creation_tokens"] == 7
    # latency_ms is measured by monotonic clock around the call; can be 0
    # for very fast fake calls but must never be negative.
    assert row["latency_ms"] >= 0


def test_callback_swallows_db_exceptions(caplog):
    """
    If the audit DB write fails, the LLM call must still succeed.

    Auditing is observability, not user-facing correctness. A broken audit
    table should produce a log line, never an HTTP 500 for the user.
    """
    feature = "test_db_failure"

    fake = GenericFakeChatModel(messages=iter([_fake_ai_message()]))
    fake.callbacks = [AuditCallbackHandler(feature=feature)]

    # Force SessionLocal() itself to raise — the callback should catch this,
    # log it, and let the .invoke() call continue unaffected.
    with patch(
        "app.ai.audit.SessionLocal",
        side_effect=RuntimeError("simulated db failure"),
    ):
        with caplog.at_level("ERROR", logger="app.ai.audit"):
            response = fake.invoke("ping")

    # The LLM call returned the canned response despite the audit failure.
    assert response.content == "pong"
    # The callback logged the failure rather than re-raising it.
    assert "failed to write ai_calls row" in caplog.text
    # And nothing was inserted (different feature, but also asserts the side
    # effect didn't somehow sneak through).
    assert _ai_calls_count(feature) == 0

# Tests for app/config.py — specifically the LangSmith env bridge (PF-22c).
#
# The gotcha this locks in: LangChain's tracer reads LANGCHAIN_* from os.environ
# directly, but pydantic-settings only fills the Settings object. So config.py
# bridges the values into os.environ — but only when an API key is present, so
# tracing stays off by default. These tests verify both halves of that guard.
#
# We drive _export_langsmith_env() directly with explicit Settings instances
# rather than reaching for a real .env, and we scrub the LANGCHAIN_* keys from
# os.environ before each test so one test can't leak state into another.

import os

import pytest

from app.config import Settings, _export_langsmith_env

_LANGCHAIN_KEYS = ("LANGCHAIN_API_KEY", "LANGCHAIN_TRACING_V2", "LANGCHAIN_PROJECT")


@pytest.fixture(autouse=True)
def _clean_langchain_env():
    """Remove LANGCHAIN_* before each test and restore the original after.

    The bridge uses os.environ.setdefault, so a leftover value would mask the
    behavior we're trying to assert. Saving/restoring keeps the real process
    environment untouched once the test finishes.
    """
    saved = {k: os.environ.get(k) for k in _LANGCHAIN_KEYS}
    for k in _LANGCHAIN_KEYS:
        os.environ.pop(k, None)
    yield
    for k, v in saved.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v


def test_bridge_exports_env_when_key_present():
    # A configured key means tracing is on — all three vars should land in the
    # process environment so LangChain's tracer can see them.
    cfg = Settings(
        langchain_api_key="ls-test-key",
        langchain_tracing_v2="true",
        langchain_project="personal-finance",
    )

    _export_langsmith_env(cfg)

    assert os.environ["LANGCHAIN_API_KEY"] == "ls-test-key"
    assert os.environ["LANGCHAIN_TRACING_V2"] == "true"
    assert os.environ["LANGCHAIN_PROJECT"] == "personal-finance"


def test_bridge_is_noop_when_key_blank():
    # No key means tracing must stay completely off — we must NOT force-set any
    # LANGCHAIN_* var, otherwise LangSmith would try to POST traces to nowhere.
    cfg = Settings(langchain_api_key="")

    _export_langsmith_env(cfg)

    for key in _LANGCHAIN_KEYS:
        assert key not in os.environ


def test_bridge_does_not_clobber_existing_env():
    # setdefault semantics: a real OS/shell env var always wins over the .env
    # value, so an operator who exported LANGCHAIN_PROJECT keeps their choice.
    os.environ["LANGCHAIN_PROJECT"] = "my-explicit-project"
    cfg = Settings(
        langchain_api_key="ls-test-key",
        langchain_project="personal-finance",
    )

    _export_langsmith_env(cfg)

    assert os.environ["LANGCHAIN_PROJECT"] == "my-explicit-project"
    assert os.environ["LANGCHAIN_API_KEY"] == "ls-test-key"

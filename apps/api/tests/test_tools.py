# Tests for the tool registry: app/ai/tools.py
#
# We verify that @tool auto-generates correct Anthropic schemas, registers
# tools in TOOL_REGISTRY, and that .run() validates inputs through the Pydantic
# model before calling the handler.
#
# No Anthropic API calls happen here — this is pure Python unit testing.

import pytest
from pydantic import BaseModel, Field

from app.ai.tools import TOOL_REGISTRY, Tool, tool

# ---------------------------------------------------------------------------
# Shared Pydantic models used across tests
# ---------------------------------------------------------------------------


class AddInput(BaseModel):
    a: int = Field(description="First number")
    b: int = Field(description="Second number")


class SearchInput(BaseModel):
    query: str = Field(description="Search keyword")
    limit: int = Field(default=10, description="Max results to return")


# ---------------------------------------------------------------------------
# Schema generation tests
# ---------------------------------------------------------------------------


def test_schema_has_correct_top_level_keys():
    """@tool schema has the three keys Anthropic requires: name, description, input_schema."""
    @tool(description="Add two numbers together")
    def _schema_keys_test(params: AddInput) -> int:
        return params.a + params.b

    schema = _schema_keys_test.schema
    assert schema["name"] == "_schema_keys_test"
    assert schema["description"] == "Add two numbers together"
    assert "input_schema" in schema


def test_schema_input_schema_is_object_type():
    """input_schema.type must be 'object' — Anthropic requires this for tool inputs."""
    @tool(description="Check input_schema type")
    def _object_type_test(params: AddInput) -> int:
        return 0

    assert _object_type_test.schema["input_schema"]["type"] == "object"


def test_schema_required_fields_match_fields_without_defaults():
    """Fields without defaults appear in required; fields with defaults do not."""
    @tool(description="Search with optional limit")
    def _required_test(params: SearchInput) -> list:
        return []

    schema = _required_test.schema
    required = schema["input_schema"].get("required", [])

    assert "query" in required      # no default → required
    assert "limit" not in required  # default=10 → optional


def test_schema_all_fields_appear_in_properties():
    """Every Pydantic field shows up in input_schema.properties."""
    @tool(description="Properties check")
    def _properties_test(params: AddInput) -> int:
        return 0

    props = _properties_test.schema["input_schema"]["properties"]
    assert "a" in props
    assert "b" in props


# ---------------------------------------------------------------------------
# TOOL_REGISTRY tests
# ---------------------------------------------------------------------------


def test_decorated_function_is_registered():
    """After @tool, the function name appears as a key in TOOL_REGISTRY."""
    @tool(description="Registry test")
    def _registry_entry_test(params: AddInput) -> int:
        return 0

    assert "_registry_entry_test" in TOOL_REGISTRY


def test_registry_value_is_same_tool_object():
    """TOOL_REGISTRY[name] is the same object the decorator returned."""
    @tool(description="Identity check")
    def _registry_identity_test(params: AddInput) -> int:
        return 0

    assert TOOL_REGISTRY["_registry_identity_test"] is _registry_identity_test


# ---------------------------------------------------------------------------
# Tool.run() tests
# ---------------------------------------------------------------------------


def test_run_calls_handler_with_validated_params():
    """tool.run(**kwargs) validates kwargs through Pydantic and calls the handler."""
    @tool(description="Run validation test")
    def _run_validate_test(params: AddInput) -> int:
        return params.a + params.b

    assert _run_validate_test.run(a=3, b=4) == 7


def test_run_rejects_wrong_type():
    """tool.run() raises ValidationError when an argument is the wrong type."""
    from pydantic import ValidationError

    @tool(description="Type rejection test")
    def _run_type_reject(params: AddInput) -> int:
        return params.a + params.b

    with pytest.raises(ValidationError):
        _run_type_reject.run(a="not_a_number", b=4)


def test_run_uses_default_for_missing_optional_field():
    """tool.run() works without optional fields — Pydantic fills in the default."""
    @tool(description="Default field test")
    def _run_default_test(params: SearchInput) -> dict:
        # limit should be the default 10 since we didn't pass it
        return {"limit_used": params.limit}

    result = _run_default_test.run(query="coffee")
    assert result["limit_used"] == 10


# ---------------------------------------------------------------------------
# Decorator validation tests
# ---------------------------------------------------------------------------


def test_decorator_rejects_function_with_no_params():
    """@tool on a zero-parameter function raises ValueError."""
    with pytest.raises(ValueError, match="at least one parameter"):
        @tool(description="No params")
        def _no_params_tool() -> None:
            pass


def test_decorator_rejects_non_basemodel_first_param():
    """@tool raises ValueError when the first parameter is not a Pydantic BaseModel."""
    with pytest.raises(ValueError, match="Pydantic BaseModel"):
        @tool(description="Wrong param type")
        def _string_param_tool(raw: str) -> None:
            pass


# ---------------------------------------------------------------------------
# Tool instance type check
# ---------------------------------------------------------------------------


def test_decorated_function_becomes_tool_instance():
    """The result of @tool is a Tool object, not the original function."""
    @tool(description="Type check")
    def _is_tool_test(params: AddInput) -> int:
        return 0

    assert isinstance(_is_tool_test, Tool)

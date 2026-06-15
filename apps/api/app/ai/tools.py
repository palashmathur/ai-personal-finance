# Tool registry for the AI agent layer.
#
# The @tool decorator wraps a Python function into a Tool object that carries
# both the Anthropic JSON schema (what Claude sees) and the handler (what we
# run when Claude calls it). This removes the need to maintain two separate
# data structures — schema list + handler dict — in every feature that uses tools.
#
# Think of it like Spring's @RequestBody annotation: you declare the input shape
# once (Pydantic model), and the framework derives everything else automatically.
# The Pydantic model generates the JSON schema; the function body is the handler.

import dataclasses
import inspect
from typing import Any, get_type_hints

from pydantic import BaseModel

# Global catalog of every @tool-decorated function. Features pick the tools
# they need by name rather than importing specific functions directly.
# Example: tools = [TOOL_REGISTRY["create_expense"], TOOL_REGISTRY["query_txns"]]
TOOL_REGISTRY: dict[str, "Tool"] = {}


@dataclasses.dataclass
class Tool:
    """A registered AI tool — holds the schema Claude needs and the handler we run.

    Created automatically by the @tool decorator. Callers don't instantiate this
    directly; they use the decorated function name as the Tool reference.
    """

    name: str
    description: str
    input_model: type  # Must be a pydantic.BaseModel subclass
    handler: Any       # Original function, called with a validated input_model instance

    @property
    def schema(self) -> dict:
        """Return the Anthropic tool schema dict for this tool.

        Pydantic v2's model_json_schema() produces JSON Schema that Anthropic
        accepts directly as input_schema. Field descriptions, types, and required
        fields are all derived from the Pydantic model definition automatically.
        No hand-written JSON needed.
        """
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.input_model.model_json_schema(),
        }

    def run(self, **kwargs: Any) -> Any:
        """Validate Claude's output against the Pydantic model and call the handler.

        Claude passes tool arguments as a raw dict. Validating through the Pydantic
        model first means type errors surface as clean ValidationError rather than
        crashing deep inside the handler with a confusing message.
        """
        params = self.input_model(**kwargs)
        return self.handler(params)


def tool(*, description: str):
    """Decorator that turns a Python function into a registered Tool.

    The function must take a single Pydantic BaseModel instance as its first
    (and typically only) parameter. The model's fields become the tool's
    input schema that Claude sees. The function body becomes the handler.

    Usage:
        class SearchInput(BaseModel):
            query: str = Field(description="Search text")

        @tool(description="Search transactions by keyword")
        def search_transactions(params: SearchInput) -> list:
            ...

    After decoration, search_transactions is a Tool object (not a function):
        search_transactions.schema          -> Anthropic tool schema dict
        search_transactions.run(query="x")  -> validates + calls the handler
        TOOL_REGISTRY["search_transactions"] -> same Tool object
    """
    def decorator(fn: Any) -> Tool:
        # get_type_hints resolves forward references and string annotations.
        # We need the resolved class object so we can call .model_json_schema() on it.
        hints = get_type_hints(fn)
        param_names = list(inspect.signature(fn).parameters.keys())

        if not param_names:
            raise ValueError(
                f"@tool function '{fn.__name__}' must have at least one parameter "
                "whose type annotation is a Pydantic BaseModel subclass."
            )

        first_type = hints.get(param_names[0])
        if first_type is None or not (
            isinstance(first_type, type) and issubclass(first_type, BaseModel)
        ):
            raise ValueError(
                f"@tool function '{fn.__name__}': first parameter must be annotated "
                "with a Pydantic BaseModel subclass, got: {first_type!r}."
            )

        t = Tool(
            name=fn.__name__,
            description=description,
            input_model=first_type,
            handler=fn,
        )
        TOOL_REGISTRY[t.name] = t
        return t

    return decorator

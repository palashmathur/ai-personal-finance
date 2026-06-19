# LangChain audit callback — writes one row to ai_calls per LLM call.
#
# LangChain calls subclasses of BaseCallbackHandler at well-defined lifecycle
# points. We hook on_chat_model_start / on_llm_start (to stash the start time
# and model name) and on_llm_end (to compute latency, read token usage, and
# write the audit row).
#
# A callback is the right shape for this — feature code just calls .invoke()
# and observability happens automatically. Spring analogy: this is the
# LangChain equivalent of a Spring @Around aspect — a side channel that wraps
# every call without polluting the business logic.
#
# The DB session is opened fresh inside the callback. FastAPI's request-scoped
# session (from Depends(get_db)) isn't available — callbacks run inside
# LangChain's runtime, not the FastAPI request handler.

import logging
import time
from typing import Any, Optional
from uuid import UUID

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.outputs import LLMResult

from app.db.session import SessionLocal
from app.models import AICall

# Module-level logger. If audit writes fail we log here and swallow the error
# so the user-facing request keeps working — observability must never break
# correctness.
_log = logging.getLogger(__name__)


class AuditCallbackHandler(BaseCallbackHandler):
    """
    Records every LLM invocation to the ai_calls table.

    One handler is attached per LLM instance (via get_llm()), but the same
    handler may legitimately see many concurrent calls in flight at once.
    We key per-call state by run_id — LangChain's unique UUID for a single
    invocation — so concurrent calls don't trample each other's start times.
    """

    def __init__(self, *, feature: str):
        # Slug used to group cost stats per feature in GET /api/ai/usage.
        # e.g. "categorize", "nl_input", "chat".
        self.feature = feature

        # run_id → time.monotonic() at the moment the call started.
        # We pop the entry in on_llm_end, so the dict can't grow unboundedly.
        self._start_times: dict[UUID, float] = {}

        # run_id → model name captured at start. Used as a fallback when the
        # response itself doesn't carry the model name (e.g. fake test models).
        # Real providers usually stamp it on the response too, so this fallback
        # mostly matters under unit tests.
        self._models: dict[UUID, str] = {}

    # Chat models fire on_chat_model_start; plain LLMs fire on_llm_start. We
    # override both because the lifecycle event ("about to send a request") is
    # what matters, not which flavour of model emitted it.
    def on_chat_model_start(
        self,
        serialized: Optional[dict],
        messages: Any,
        *,
        run_id: UUID,
        **kwargs: Any,
    ) -> None:
        self._capture_start(serialized, run_id, kwargs)

    def on_llm_start(
        self,
        serialized: Optional[dict],
        prompts: list,
        *,
        run_id: UUID,
        **kwargs: Any,
    ) -> None:
        self._capture_start(serialized, run_id, kwargs)

    def _capture_start(
        self,
        serialized: Optional[dict],
        run_id: UUID,
        kwargs: dict,
    ) -> None:
        """Record the start time and best-guess model name for this call."""
        self._start_times[run_id] = time.monotonic()

        # invocation_params is the LangChain-standard place to find the live
        # inference params (model, temperature, max_tokens). serialized.kwargs
        # is a fallback for when the LLM was configured at construction time
        # but didn't pass anything per-call.
        invocation_params = kwargs.get("invocation_params") or {}
        serialized = serialized or {}
        model = (
            invocation_params.get("model")
            or invocation_params.get("model_name")
            or serialized.get("kwargs", {}).get("model")
            or serialized.get("kwargs", {}).get("model_name")
            or "unknown"
        )
        self._models[run_id] = model

    def on_llm_end(
        self,
        response: LLMResult,
        *,
        run_id: UUID,
        **kwargs: Any,
    ) -> None:
        """
        Compute latency, read token counts, and persist a single ai_calls row.

        Wrapped in a broad try/except so a DB hiccup during audit never breaks
        the user-facing request. Auditing is observability — it must fail
        silently and log rather than bubbling an exception up the stack.
        """
        try:
            start = self._start_times.pop(run_id, None)
            latency_ms = int((time.monotonic() - start) * 1000) if start is not None else 0

            captured_model = self._models.pop(run_id, "unknown")
            (
                input_tokens,
                output_tokens,
                cache_read,
                cache_creation,
                response_model,
            ) = self._extract_usage(response)
            # Prefer the model name the response advertised — it's authoritative.
            # Fall back to whatever we captured in on_chat_model_start otherwise.
            model = response_model or captured_model

            session = SessionLocal()
            try:
                row = AICall(
                    feature=self.feature,
                    model=model,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    cache_read_tokens=cache_read,
                    cache_creation_tokens=cache_creation,
                    latency_ms=latency_ms,
                )
                session.add(row)
                session.commit()
            finally:
                # Always release the connection back to the pool, even if commit raised.
                session.close()
        except Exception:
            # log.exception captures the traceback for debugging without
            # propagating. The user request keeps going as if nothing happened.
            _log.exception(
                "AuditCallbackHandler: failed to write ai_calls row for feature=%s",
                self.feature,
            )

    @staticmethod
    def _extract_usage(
        response: LLMResult,
    ) -> tuple[int, int, int, int, Optional[str]]:
        """
        Pull token counts and model name out of an LLMResult.

        LangChain's standard place for per-message token data is
        AIMessage.usage_metadata, with cache details nested under
        input_token_details. Older integrations sometimes stash counts on
        response.llm_output instead, so we treat that as a fallback.

        Returns: (input_tokens, output_tokens, cache_read, cache_creation, model)
        """
        input_tokens = 0
        output_tokens = 0
        cache_read = 0
        cache_creation = 0
        model: Optional[str] = None

        # generations is list[list[Generation]] — outer list for batched prompts,
        # inner list for multiple candidates per prompt. Our usage is always
        # one prompt → one candidate, but the loop is correct for both shapes.
        for gen_list in response.generations or []:
            for gen in gen_list:
                message = getattr(gen, "message", None)
                if message is None:
                    continue
                usage = getattr(message, "usage_metadata", None) or {}
                input_tokens += int(usage.get("input_tokens", 0) or 0)
                output_tokens += int(usage.get("output_tokens", 0) or 0)
                details = usage.get("input_token_details") or {}
                cache_read += int(details.get("cache_read", 0) or 0)
                cache_creation += int(details.get("cache_creation", 0) or 0)
                # Chat providers stamp the resolved model on
                # message.response_metadata. Take the first one we see.
                if not model:
                    meta = getattr(message, "response_metadata", None) or {}
                    model = meta.get("model") or meta.get("model_name")

        # Fallback: very old LangChain integrations only populated llm_output.
        llm_output = response.llm_output or {}
        if not model:
            model = llm_output.get("model_name") or llm_output.get("model")

        return input_tokens, output_tokens, cache_read, cache_creation, model

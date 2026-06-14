# Pydantic schemas for the AI usage endpoint.
# These define the exact shape of GET /api/ai/usage responses.

from typing import Optional

from pydantic import BaseModel


class FeatureUsageSummary(BaseModel):
    """
    Token and call stats for a single feature (e.g. "categorize" or "nl_input").
    Nested inside UsageResponse.by_feature so you can see cost per feature at a glance.
    """

    calls: int
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int
    cache_creation_tokens: int


class UsageResponse(BaseModel):
    """
    Aggregated token usage for all AI calls in a date range.

    Use the by_feature breakdown to answer "why did my bill go up?" —
    if categorize is responsible for 90% of tokens, that's where to look first.

    estimated_cache_hit_rate is the fraction of input tokens that hit the prompt cache.
    A high rate (>0.8) means the caching is working as intended.
    It's None when there were no calls in the period (avoids division by zero).
    """

    total_calls: int
    total_input_tokens: int
    total_output_tokens: int
    total_cache_read_tokens: int
    total_cache_creation_tokens: int

    # cache_read / (input + cache_read) — closer to 1.0 is better.
    # None when there are no calls (can't compute the ratio).
    estimated_cache_hit_rate: Optional[float]

    # Breakdown of totals by feature slug.
    by_feature: dict[str, FeatureUsageSummary]

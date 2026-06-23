/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { FeatureUsageSummary } from './FeatureUsageSummary';
/**
 * Aggregated token usage for all AI calls in a date range.
 *
 * Use the by_feature breakdown to answer "why did my bill go up?" —
 * if categorize is responsible for 90% of tokens, that's where to look first.
 *
 * estimated_cache_hit_rate is the fraction of input tokens that hit the prompt cache.
 * A high rate (>0.8) means the caching is working as intended.
 * It's None when there were no calls in the period (avoids division by zero).
 */
export type UsageResponse = {
    total_calls: number;
    total_input_tokens: number;
    total_output_tokens: number;
    total_cache_read_tokens: number;
    total_cache_creation_tokens: number;
    estimated_cache_hit_rate: (number | null);
    by_feature: Record<string, FeatureUsageSummary>;
};


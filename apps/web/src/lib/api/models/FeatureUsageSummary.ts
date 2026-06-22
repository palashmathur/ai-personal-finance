/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
/**
 * Token and call stats for a single feature (e.g. "categorize" or "nl_input").
 * Nested inside UsageResponse.by_feature so you can see cost per feature at a glance.
 */
export type FeatureUsageSummary = {
    calls: number;
    input_tokens: number;
    output_tokens: number;
    cache_read_tokens: number;
    cache_creation_tokens: number;
};


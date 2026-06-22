/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { UsageResponse } from '../models/UsageResponse';
import type { CancelablePromise } from '../core/CancelablePromise';
import { OpenAPI } from '../core/OpenAPI';
import { request as __request } from '../core/request';
export class AiService {
    /**
     * Get Usage
     * Return aggregated AI token usage for a date range.
     *
     * Both `from` and `to` are required. Results are inclusive of both endpoints.
     * The response breaks totals down by feature so you can see which part of the
     * app is responsible for most of the token spend.
     *
     * Typical use: monitor AI costs after adding a new feature, or check whether
     * prompt caching is actually working (estimated_cache_hit_rate should be > 0.8
     * for high-frequency features like auto-categorization).
     * @returns UsageResponse Successful Response
     * @throws ApiError
     */
    public static getUsageApiAiUsageGet({
        from,
        to,
    }: {
        from: string,
        to: string,
    }): CancelablePromise<UsageResponse> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/ai/usage',
            query: {
                'from': from,
                'to': to,
            },
            errors: {
                422: `Validation Error`,
            },
        });
    }
}

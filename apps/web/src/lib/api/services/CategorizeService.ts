/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { CategorizeAcceptRequest } from '../models/CategorizeAcceptRequest';
import type { CategorizeBatchRequest } from '../models/CategorizeBatchRequest';
import type { CategorizeRuleResponse } from '../models/CategorizeRuleResponse';
import type { CategorizeSuggestRequest } from '../models/CategorizeSuggestRequest';
import type { CategorizeSuggestResponse } from '../models/CategorizeSuggestResponse';
import type { CancelablePromise } from '../core/CancelablePromise';
import { OpenAPI } from '../core/OpenAPI';
import { request as __request } from '../core/request';
export class CategorizeService {
    /**
     * Suggest
     * Return a category suggestion for a single transaction note.
     *
     * Checks saved rules first (free, instant). Falls back to the LLM only
     * when no rule matches. The source field in the response tells you which path
     * was taken: "rule" or "llm".
     * @returns CategorizeSuggestResponse Successful Response
     * @throws ApiError
     */
    public static suggestApiCategorizeSuggestPost({
        requestBody,
    }: {
        requestBody: CategorizeSuggestRequest,
    }): CancelablePromise<CategorizeSuggestResponse> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/api/categorize/suggest',
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Suggest Batch
     * Return one suggestion per row, in the same order as the input.
     *
     * Designed for the CSV import preview step — rules are loaded once for the
     * whole batch, so a 200-row import only hits the LLM for rows that don't
     * match any saved rule. Much cheaper than calling /suggest 200 times.
     * @returns CategorizeSuggestResponse Successful Response
     * @throws ApiError
     */
    public static suggestBatchApiCategorizeSuggestBatchPost({
        requestBody,
    }: {
        requestBody: CategorizeBatchRequest,
    }): CancelablePromise<Array<CategorizeSuggestResponse>> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/api/categorize/suggest-batch',
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Accept
     * Save a categorization rule so future matching transactions skip the LLM.
     *
     * If transaction_id is provided, that transaction's category_id is also
     * updated immediately so the user sees the correct category straight away.
     * @returns CategorizeRuleResponse Successful Response
     * @throws ApiError
     */
    public static acceptApiCategorizeAcceptPost({
        requestBody,
    }: {
        requestBody: CategorizeAcceptRequest,
    }): CancelablePromise<CategorizeRuleResponse> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/api/categorize/accept',
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * List Rules
     * Return all saved categorization rules, highest priority first.
     * @returns CategorizeRuleResponse Successful Response
     * @throws ApiError
     */
    public static listRulesApiCategorizeRulesGet(): CancelablePromise<Array<CategorizeRuleResponse>> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/categorize/rules',
        });
    }
    /**
     * Delete Rule
     * Hard-delete a categorization rule. Returns 404 if not found.
     * @returns void
     * @throws ApiError
     */
    public static deleteRuleApiCategorizeRulesRuleIdDelete({
        ruleId,
    }: {
        ruleId: number,
    }): CancelablePromise<void> {
        return __request(OpenAPI, {
            method: 'DELETE',
            url: '/api/categorize/rules/{rule_id}',
            path: {
                'rule_id': ruleId,
            },
            errors: {
                422: `Validation Error`,
            },
        });
    }
}

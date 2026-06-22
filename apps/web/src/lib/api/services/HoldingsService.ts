/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { HoldingResponse } from '../models/HoldingResponse';
import type { CancelablePromise } from '../core/CancelablePromise';
import { OpenAPI } from '../core/OpenAPI';
import { request as __request } from '../core/request';
export class HoldingsService {
    /**
     * Get Holdings
     * Return current holdings — one row per (account, instrument) pair with qty > 0.
     *
     * Computed live from the investment_txns ledger — no separate holdings table.
     * Positions that have been fully sold (qty <= 0) are excluded automatically.
     *
     * - No filter: all holdings across all accounts.
     * - ?account_id=3: holdings in one specific broker/bank account only.
     *
     * Each row includes: qty, cost_basis_minor, market_value_minor (None if no price),
     * unrealized_pnl_minor (None if no price), and a nested instrument summary.
     * @returns HoldingResponse Successful Response
     * @throws ApiError
     */
    public static getHoldingsApiHoldingsGet({
        accountId,
    }: {
        accountId?: (number | null),
    }): CancelablePromise<Array<HoldingResponse>> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/holdings',
            query: {
                'account_id': accountId,
            },
            errors: {
                422: `Validation Error`,
            },
        });
    }
}

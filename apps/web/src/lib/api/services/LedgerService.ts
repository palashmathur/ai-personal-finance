/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { LedgerEntryResponse } from '../models/LedgerEntryResponse';
import type { CancelablePromise } from '../core/CancelablePromise';
import { OpenAPI } from '../core/OpenAPI';
import { request as __request } from '../core/request';
export class LedgerService {
    /**
     * List Ledger
     * Return a unified, paginated ledger merging cash transactions and investment trades.
     *
     * Both `from` and `to` are required. Results are ordered by occurred_on DESC
     * (most recent first), then created_at DESC for same-day entries.
     *
     * Each row has a `source` field ("cash" or "investment") and a `kind` field:
     * - cash rows: income | expense | transfer
     * - investment rows: inv_buy | inv_sell | inv_dividend
     *
     * Pagination: use `limit` (max 200, default 50) and `offset` for paging.
     * @returns LedgerEntryResponse Successful Response
     * @throws ApiError
     */
    public static listLedgerApiLedgerGet({
        from,
        to,
        limit = 50,
        offset,
    }: {
        from: string,
        to: string,
        limit?: number,
        offset?: number,
    }): CancelablePromise<Array<LedgerEntryResponse>> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/ledger',
            query: {
                'from': from,
                'to': to,
                'limit': limit,
                'offset': offset,
            },
            errors: {
                422: `Validation Error`,
            },
        });
    }
}

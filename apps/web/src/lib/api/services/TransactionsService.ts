/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { TransactionCreate } from '../models/TransactionCreate';
import type { TransactionResponse } from '../models/TransactionResponse';
import type { TransactionUpdate } from '../models/TransactionUpdate';
import type { CancelablePromise } from '../core/CancelablePromise';
import { OpenAPI } from '../core/OpenAPI';
import { request as __request } from '../core/request';
export class TransactionsService {
    /**
     * List Transactions
     * List transactions with optional filters. Ordered by occurred_on DESC, created_at DESC.
     *
     * - `from` / `to`: filter by economic date range (both inclusive).
     * - `account_id`: only transactions from this account.
     * - `category_id`: only transactions with this category.
     * - `kind`: income | expense | transfer.
     * - `q`: case-insensitive substring match on the note field.
     * - `limit` / `offset`: pagination (default 50 per page, max 500).
     * @returns TransactionResponse Successful Response
     * @throws ApiError
     */
    public static listTransactionsApiTransactionsGet({
        from,
        to,
        accountId,
        categoryId,
        kind,
        q,
        limit = 50,
        offset,
    }: {
        from?: (string | null),
        to?: (string | null),
        accountId?: (number | null),
        categoryId?: (number | null),
        kind?: (string | null),
        q?: (string | null),
        limit?: number,
        offset?: number,
    }): CancelablePromise<Array<TransactionResponse>> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/transactions',
            query: {
                'from': from,
                'to': to,
                'account_id': accountId,
                'category_id': categoryId,
                'kind': kind,
                'q': q,
                'limit': limit,
                'offset': offset,
            },
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Create Transaction
     * Create a transaction.
     *
     * For income/expense: returns a list with 1 item.
     * For transfer: returns a list with 2 items (debit row first, credit row second).
     *
     * The response is always a list so the caller doesn't need to check the kind
     * to know whether to unpack one or two items.
     * @returns TransactionResponse Successful Response
     * @throws ApiError
     */
    public static createTransactionApiTransactionsPost({
        requestBody,
    }: {
        requestBody: TransactionCreate,
    }): CancelablePromise<Array<TransactionResponse>> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/api/transactions',
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Update Transaction
     * Partially update a transaction. For transfer rows, updates both halves atomically.
     *
     * Returns a list with the same shape as create: 1 item for regular transactions,
     * 2 items for transfer rows (the row you updated + its partner).
     * @returns TransactionResponse Successful Response
     * @throws ApiError
     */
    public static updateTransactionApiTransactionsTxnIdPatch({
        txnId,
        requestBody,
    }: {
        txnId: number,
        requestBody: TransactionUpdate,
    }): CancelablePromise<Array<TransactionResponse>> {
        return __request(OpenAPI, {
            method: 'PATCH',
            url: '/api/transactions/{txn_id}',
            path: {
                'txn_id': txnId,
            },
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Delete Transaction
     * Delete a transaction. For transfer rows, deletes both halves in one atomic operation.
     * Returns 204 No Content on success.
     * @returns void
     * @throws ApiError
     */
    public static deleteTransactionApiTransactionsTxnIdDelete({
        txnId,
    }: {
        txnId: number,
    }): CancelablePromise<void> {
        return __request(OpenAPI, {
            method: 'DELETE',
            url: '/api/transactions/{txn_id}',
            path: {
                'txn_id': txnId,
            },
            errors: {
                422: `Validation Error`,
            },
        });
    }
}

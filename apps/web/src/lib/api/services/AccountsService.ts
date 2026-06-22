/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { AccountCreate } from '../models/AccountCreate';
import type { AccountResponse } from '../models/AccountResponse';
import type { AccountUpdate } from '../models/AccountUpdate';
import type { CancelablePromise } from '../core/CancelablePromise';
import { OpenAPI } from '../core/OpenAPI';
import { request as __request } from '../core/request';
export class AccountsService {
    /**
     * List Accounts
     * List all accounts.
     *
     * By default returns only active (non-archived) accounts — what you'd show in
     * any dropdown or dashboard widget. Pass ?archived=true to include soft-deleted
     * accounts as well (useful for audit or to restore one).
     * @returns AccountResponse Successful Response
     * @throws ApiError
     */
    public static listAccountsApiAccountsGet({
        archived = false,
    }: {
        archived?: boolean,
    }): CancelablePromise<Array<AccountResponse>> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/accounts',
            query: {
                'archived': archived,
            },
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Create Account
     * Create a new account.
     *
     * Returns 201 with the created account. The `type` field must be one of:
     * cash | bank | broker | wallet | credit_card — anything else is a 422.
     * `opening_balance_minor` is the account's balance in paise before you started
     * tracking it in this app. Defaults to 0.
     * @returns AccountResponse Successful Response
     * @throws ApiError
     */
    public static createAccountApiAccountsPost({
        requestBody,
    }: {
        requestBody: AccountCreate,
    }): CancelablePromise<AccountResponse> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/api/accounts',
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Update Account
     * Partially update an account. Only the fields you include in the body are changed.
     *
     * This doubles as the soft-delete endpoint: send {"archived": true} to hide the
     * account from active lists while preserving all its transaction history.
     * Send {"archived": false} to restore it.
     * @returns AccountResponse Successful Response
     * @throws ApiError
     */
    public static updateAccountApiAccountsAccountIdPatch({
        accountId,
        requestBody,
    }: {
        accountId: number,
        requestBody: AccountUpdate,
    }): CancelablePromise<AccountResponse> {
        return __request(OpenAPI, {
            method: 'PATCH',
            url: '/api/accounts/{account_id}',
            path: {
                'account_id': accountId,
            },
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Delete Account
     * Hard-delete an account. Returns 204 No Content on success.
     *
     * Returns 409 Conflict if any transactions or investment trades reference this account.
     * In that case, use PATCH with {"archived": true} to soft-delete instead.
     * @returns void
     * @throws ApiError
     */
    public static deleteAccountApiAccountsAccountIdDelete({
        accountId,
    }: {
        accountId: number,
    }): CancelablePromise<void> {
        return __request(OpenAPI, {
            method: 'DELETE',
            url: '/api/accounts/{account_id}',
            path: {
                'account_id': accountId,
            },
            errors: {
                422: `Validation Error`,
            },
        });
    }
}

/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { InvestmentTxnCreate } from '../models/InvestmentTxnCreate';
import type { InvestmentTxnResponse } from '../models/InvestmentTxnResponse';
import type { InvestmentTxnUpdate } from '../models/InvestmentTxnUpdate';
import type { TxnSide } from '../models/TxnSide';
import type { CancelablePromise } from '../core/CancelablePromise';
import { OpenAPI } from '../core/OpenAPI';
import { request as __request } from '../core/request';
export class InvestmentTxnsService {
    /**
     * Create Investment Txn
     * Record a new investment trade (buy, sell, or dividend).
     *
     * The account must be type broker, wallet, bank, or cash — credit_card is the only rejected type.
     * Bank/cash are allowed because SIP debits come directly from a bank account.
     * The instrument must already exist in the catalog — create it first via POST /api/instruments.
     * On the very first trade for an instrument, its current_price_minor is bootstrapped
     * from this trade's price so the holdings page has a non-NULL price immediately.
     * @returns InvestmentTxnResponse Successful Response
     * @throws ApiError
     */
    public static createInvestmentTxnApiInvestmentTxnsPost({
        requestBody,
    }: {
        requestBody: InvestmentTxnCreate,
    }): CancelablePromise<InvestmentTxnResponse> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/api/investment-txns',
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * List Investment Txns
     * List investment trades, newest first. All filters are optional and AND-combined.
     *
     * - ?from=2026-01-01&to=2026-03-31   — date range filter
     * - ?instrument_id=7                  — only trades for one instrument
     * - ?account_id=3                     — only trades in one broker account
     * - ?side=buy                         — only buys (or sell, dividend)
     * @returns InvestmentTxnResponse Successful Response
     * @throws ApiError
     */
    public static listInvestmentTxnsApiInvestmentTxnsGet({
        from,
        to,
        instrumentId,
        accountId,
        side,
    }: {
        from?: (string | null),
        to?: (string | null),
        instrumentId?: (number | null),
        accountId?: (number | null),
        side?: (TxnSide | null),
    }): CancelablePromise<Array<InvestmentTxnResponse>> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/investment-txns',
            query: {
                'from': from,
                'to': to,
                'instrument_id': instrumentId,
                'account_id': accountId,
                'side': side,
            },
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Update Investment Txn
     * Partially update a trade. Only the fields you send are changed.
     *
     * Useful for correcting a price, fee, or date after the fact.
     * If you change account_id or instrument_id, the new values are validated (404 if missing,
     * 422 if the account type is wrong).
     * @returns InvestmentTxnResponse Successful Response
     * @throws ApiError
     */
    public static updateInvestmentTxnApiInvestmentTxnsTxnIdPatch({
        txnId,
        requestBody,
    }: {
        txnId: number,
        requestBody: InvestmentTxnUpdate,
    }): CancelablePromise<InvestmentTxnResponse> {
        return __request(OpenAPI, {
            method: 'PATCH',
            url: '/api/investment-txns/{txn_id}',
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
     * Delete Investment Txn
     * Hard-delete a trade by ID.
     *
     * The holdings aggregation recalculates from remaining rows — no other cleanup needed.
     * Returns 204 No Content on success.
     * @returns void
     * @throws ApiError
     */
    public static deleteInvestmentTxnApiInvestmentTxnsTxnIdDelete({
        txnId,
    }: {
        txnId: number,
    }): CancelablePromise<void> {
        return __request(OpenAPI, {
            method: 'DELETE',
            url: '/api/investment-txns/{txn_id}',
            path: {
                'txn_id': txnId,
            },
            errors: {
                422: `Validation Error`,
            },
        });
    }
}

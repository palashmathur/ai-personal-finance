/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { TxnSide } from './TxnSide';
/**
 * Request body for POST /api/investment-txns.
 *
 * Both account_id and instrument_id must reference existing rows — the service
 * validates this and returns 404 if either is missing.
 * account_id must also be type broker or wallet — the service returns 422 otherwise.
 */
export type InvestmentTxnCreate = {
    account_id: number;
    instrument_id: number;
    side: TxnSide;
    quantity: number;
    price_minor: number;
    fee_minor?: number;
    occurred_on: string;
    note?: (string | null);
    source?: string;
};


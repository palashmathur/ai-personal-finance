/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { InstrumentSummary } from './InstrumentSummary';
import type { TxnSide } from './TxnSide';
/**
 * Response shape returned by every investment-txns endpoint.
 * Embeds a nested instrument summary so the frontend holdings table
 * can show instrument details alongside trade details in a single response.
 */
export type InvestmentTxnResponse = {
    id: number;
    account_id: number;
    instrument_id: number;
    instrument: InstrumentSummary;
    side: TxnSide;
    quantity: number;
    price_minor: number;
    fee_minor: number;
    occurred_on: string;
    note: (string | null);
    source: string;
    created_at: string;
    updated_at: string;
};


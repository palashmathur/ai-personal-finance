/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
/**
 * Minimal instrument info embedded in every InvestmentTxnResponse.
 * Gives the caller enough context to display "what was this trade for"
 * without needing a separate GET /api/instruments/{id} call.
 */
export type InstrumentSummary = {
    id: number;
    kind: string;
    symbol: string;
    name: string;
    current_price_minor: (number | null);
};


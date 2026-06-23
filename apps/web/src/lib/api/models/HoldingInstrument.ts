/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
/**
 * Minimal instrument info embedded in every HoldingResponse.
 * Gives the caller the display name, kind (for allocation grouping),
 * and current price (for market value) without a separate API call.
 */
export type HoldingInstrument = {
    id: number;
    kind: string;
    symbol: string;
    name: string;
    current_price_minor: (number | null);
};


/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
/**
 * One slice of the portfolio allocation donut.
 * Groups holdings by instrument.kind (stock, mutual_fund, etf, crypto, metal, other).
 */
export type AllocationItem = {
    kind: string;
    market_value_minor: number;
    pct: number;
};


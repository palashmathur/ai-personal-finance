/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
/**
 * The asset class of the instrument. Drives two things:
 * 1. Which price-fetch API is used in V2 (AMFI for mutual_fund, yfinance for stock/etf, etc.)
 * 2. How holdings are grouped in the allocation donut chart on the dashboard.
 */
export type InstrumentKind = 'mutual_fund' | 'stock' | 'etf' | 'crypto' | 'metal' | 'other';

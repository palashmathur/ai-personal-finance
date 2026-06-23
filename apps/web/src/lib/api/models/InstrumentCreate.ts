/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { InstrumentKind } from './InstrumentKind';
/**
 * Request body for POST /api/instruments.
 *
 * `symbol` is the machine-readable identifier — NSE ticker for stocks,
 * AMFI scheme code for mutual funds, CoinGecko ID for crypto, etc.
 * The uniqueness constraint is on (kind, symbol) together, not symbol alone,
 * because the same ticker can exist on multiple exchanges with different kinds
 * (e.g. a Nifty ETF has both an NSE symbol and an AMFI code).
 */
export type InstrumentCreate = {
    kind: InstrumentKind;
    symbol: string;
    name: string;
    current_price_minor?: (number | null);
    meta?: (Record<string, any> | null);
};


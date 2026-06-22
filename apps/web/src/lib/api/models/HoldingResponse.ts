/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { HoldingInstrument } from './HoldingInstrument';
/**
 * One row in the holdings response — represents a single (account, instrument) position.
 *
 * All monetary values are in paise (integers). The frontend divides by 100 to display ₹.
 *
 * market_value_minor and unrealized_pnl_minor will be None when current_price_minor
 * is NULL on the instrument — the UI should show a "price missing" state in that case.
 */
export type HoldingResponse = {
    instrument_id: number;
    instrument: HoldingInstrument;
    account_id: number;
    qty: number;
    cost_basis_minor: number;
    market_value_minor: (number | null);
    unrealized_pnl_minor: (number | null);
};


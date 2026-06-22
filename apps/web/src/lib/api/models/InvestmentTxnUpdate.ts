/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { TxnSide } from './TxnSide';
/**
 * Request body for PATCH /api/investment-txns/{id}.
 * All fields optional — only the ones you send are changed (true PATCH semantics).
 *
 * Most common update: correcting a price or fee after entry.
 */
export type InvestmentTxnUpdate = {
    account_id?: (number | null);
    instrument_id?: (number | null);
    side?: (TxnSide | null);
    quantity?: (number | null);
    price_minor?: (number | null);
    fee_minor?: (number | null);
    occurred_on?: (string | null);
    note?: (string | null);
    source?: (string | null);
};


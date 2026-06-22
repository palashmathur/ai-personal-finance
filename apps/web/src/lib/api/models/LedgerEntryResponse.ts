/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
/**
 * One row in the unified ledger — could be a cash transaction or an investment trade.
 *
 * Fields that don't apply to a particular row type are None.
 * Use `source` + `kind` to decide how to render the row in the UI.
 */
export type LedgerEntryResponse = {
    source: string;
    source_id: number;
    kind: string;
    account_id: number;
    category_id: (number | null);
    instrument_id: (number | null);
    quantity: (number | null);
    amount_minor: number;
    occurred_on: string;
    note: (string | null);
    created_at: string;
};


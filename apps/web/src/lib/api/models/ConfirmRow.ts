/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
/**
 * One row in the confirm request body.
 * account_id is NOT here — it is a single top-level field on ConfirmRequest,
 * applied to all rows. The user picks the account once, not per row.
 */
export type ConfirmRow = {
    occurred_on: string;
    amount_minor: number;
    kind: string;
    note: string;
    category_id?: (number | null);
};


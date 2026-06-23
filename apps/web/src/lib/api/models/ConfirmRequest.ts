/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { ConfirmRow } from './ConfirmRow';
/**
 * Full confirm request body.
 * account_id is supplied once here and stamped on every row during insert —
 * the user selects the account from a single dropdown, not per row.
 */
export type ConfirmRequest = {
    account_id: number;
    rows: Array<ConfirmRow>;
};


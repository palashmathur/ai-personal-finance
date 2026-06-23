/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
/**
 * Request body for PATCH /api/transactions/{id}.
 * Every field is optional — callers send only what they want to change.
 *
 * `kind` is intentionally absent: changing a transaction's kind (e.g. expense → transfer)
 * is a destructive semantic change that requires delete + re-create, not a patch.
 *
 * `extra="ignore"` means unknown keys in the request body are silently dropped
 * rather than causing a 422 — same pattern as AccountUpdate and CategoryUpdate.
 */
export type TransactionUpdate = {
    amount_minor?: (number | null);
    occurred_on?: (string | null);
    note?: (string | null);
    category_id?: (number | null);
    from_account_id?: (number | null);
    to_account_id?: (number | null);
};


/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { AccountType } from './AccountType';
/**
 * Request body for PATCH /api/accounts/{id}.
 * Every field is optional so callers can update just the fields they care about
 * — same pattern as a Spring Boot @PatchMapping where you merge only non-null fields.
 *
 * Setting archived=True is how you soft-delete an account (hides it from dropdowns
 * but keeps all its transaction history intact).
 */
export type AccountUpdate = {
    name?: (string | null);
    type?: (AccountType | null);
    opening_balance_minor?: (number | null);
    archived?: (boolean | null);
};


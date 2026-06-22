/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
/**
 * The allowed account types. Stored as a string in the DB, but validated as an
 * enum at the API boundary so callers get a clear 422 if they pass an unknown type.
 *
 * - cash/bank/wallet: liquid accounts tracked in the cash ledger.
 * - broker: investment accounts — only appear on investment transaction forms.
 * - credit_card: treated as a liability in net worth calculations.
 */
export type AccountType = 'cash' | 'bank' | 'broker' | 'wallet' | 'credit_card';

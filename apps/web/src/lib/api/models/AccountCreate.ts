/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { AccountType } from './AccountType';
/**
 * Request body for POST /api/accounts.
 * All fields are required except opening_balance_minor, which defaults to 0
 * (sensible default when you start tracking an account mid-life).
 */
export type AccountCreate = {
    name: string;
    type: AccountType;
    opening_balance_minor?: number;
};


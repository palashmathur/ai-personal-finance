/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { TransactionKind } from './TransactionKind';
import type { TransactionSource } from './TransactionSource';
/**
 * Request body for POST /api/transactions.
 *
 * One schema handles both regular transactions and transfers. All kind-specific
 * fields are optional at the schema level; the service enforces the cross-field
 * rules and raises HTTPException(422) if they are violated.
 *
 * - income/expense: needs account_id + category_id; from/to_account_id must be absent.
 * - transfer: needs from_account_id + to_account_id (different); account_id + category_id must be absent.
 */
export type TransactionCreate = {
    kind: TransactionKind;
    /**
     * Amount in paise (1 INR = 100 paise). Must be > 0.
     */
    amount_minor: number;
    occurred_on: string;
    note?: (string | null);
    source?: TransactionSource;
    account_id?: (number | null);
    category_id?: (number | null);
    from_account_id?: (number | null);
    to_account_id?: (number | null);
};


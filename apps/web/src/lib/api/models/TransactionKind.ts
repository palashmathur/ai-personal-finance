/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
/**
 * The allowed transaction kinds. Drives validation rules and sign logic.
 * - income: money coming in — requires account_id + category_id (income kind).
 * - expense: money going out — requires account_id + category_id (expense kind).
 * - transfer: money moving between your own accounts — no category, uses from/to accounts.
 */
export type TransactionKind = 'income' | 'expense' | 'transfer';

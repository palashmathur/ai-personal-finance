/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { TransactionKind } from './TransactionKind';
import type { TransactionSource } from './TransactionSource';
/**
 * Response shape for all transaction endpoints.
 *
 * Includes `account_name` and `category_name` as denormalized display fields —
 * the service attaches these as transient Python attributes before returning, so the
 * frontend doesn't need to make separate account/category lookups for every row.
 *
 * from_attributes=True (Pydantic v2's orm_mode equivalent) lets Pydantic read directly
 * from SQLAlchemy ORM instances, including the transient attrs set by the service.
 */
export type TransactionResponse = {
    id: number;
    account_id: number;
    account_name: string;
    category_id: (number | null);
    category_name: (string | null);
    kind: TransactionKind;
    amount_minor: number;
    occurred_on: string;
    note: (string | null);
    source: TransactionSource;
    created_at: string;
    updated_at: string;
};


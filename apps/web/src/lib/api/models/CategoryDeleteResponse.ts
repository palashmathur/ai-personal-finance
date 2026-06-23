/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
/**
 * Response body for DELETE /api/categories/{id}.
 * Returns how many transactions were updated to category_id=NULL as a result
 * of the deletion, so the caller knows how many items are now "Uncategorized".
 */
export type CategoryDeleteResponse = {
    id: number;
    name: string;
    deleted_transactions_count: number;
};


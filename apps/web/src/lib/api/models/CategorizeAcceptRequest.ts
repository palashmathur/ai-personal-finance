/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
/**
 * Save a categorization rule after accepting a suggestion.
 *
 * pattern     — the regex to save (usually the suggested_rule from the suggest response).
 * category_id — the category this pattern should map to.
 * priority    — higher = checked first. Default 0 is fine for most rules.
 * transaction_id — if provided, also updates that transaction's category_id right now.
 */
export type CategorizeAcceptRequest = {
    pattern: string;
    category_id: number;
    priority?: number;
    transaction_id?: (number | null);
};


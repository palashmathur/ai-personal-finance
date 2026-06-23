/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
/**
 * A single saved categorization rule, as returned by the list-rules endpoint.
 */
export type CategorizeRuleResponse = {
    id: number;
    pattern: string;
    field: string;
    category_id: number;
    category_name: string;
    priority: number;
    created_at: string;
};


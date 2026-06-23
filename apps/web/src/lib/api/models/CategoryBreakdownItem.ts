/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
/**
 * One row in the expense breakdown — how much was spent in a given category
 * during the period. Used to render the horizontal bar chart on the dashboard.
 */
export type CategoryBreakdownItem = {
    category_id: number;
    category_name: string;
    parent_name: (string | null);
    total_minor: number;
};


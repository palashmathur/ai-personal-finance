/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { CategorizeSuggestRequest } from './CategorizeSuggestRequest';
/**
 * Input for batch categorization — used by the CSV import preview step.
 * Send up to N rows; get back one suggestion per row in the same order.
 */
export type CategorizeBatchRequest = {
    rows: Array<CategorizeSuggestRequest>;
};


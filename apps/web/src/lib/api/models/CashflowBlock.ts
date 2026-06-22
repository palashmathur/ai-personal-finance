/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
/**
 * Period income, expenses, and the resulting savings rate.
 * savings_rate is None when income is 0 — dividing by zero would give nonsense.
 */
export type CashflowBlock = {
    income_minor: number;
    expense_minor: number;
    savings_rate: (number | null);
};


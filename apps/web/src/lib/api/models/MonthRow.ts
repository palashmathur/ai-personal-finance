/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
/**
 * One month's cashflow breakdown.
 *
 * All *_minor fields are in paise (integers).
 * All *_pct fields are floats in the range [0, 1] — e.g. 0.60 means 60%.
 * *_pct fields are None when income_minor == 0 to avoid meaningless percentages.
 */
export type MonthRow = {
    ym: string;
    income_minor: number;
    expense_minor: number;
    invest_minor: number;
    expense_pct: (number | null);
    invest_pct: (number | null);
    savings_minor: number;
    savings_pct: (number | null);
};


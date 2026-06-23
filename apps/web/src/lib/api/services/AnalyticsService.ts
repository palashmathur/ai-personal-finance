/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { MonthRow } from '../models/MonthRow';
import type { CancelablePromise } from '../core/CancelablePromise';
import { OpenAPI } from '../core/OpenAPI';
import { request as __request } from '../core/request';
export class AnalyticsService {
    /**
     * Monthly Cashflow Summary
     * Return per-month income, expense, investment, and savings breakdown.
     *
     * One row per calendar month in the requested range. Both `from` and `to`
     * are required and `from` must not be after `to`.
     *
     * Percentages (expense_pct, invest_pct, savings_pct) are null for any month
     * where income is zero — dividing by zero would produce a meaningless value.
     *
     * Typical use: drive a monthly bar chart on the dashboard showing income vs
     * expenses vs investments side by side across a 3–12 month window.
     * @returns MonthRow Successful Response
     * @throws ApiError
     */
    public static monthlyCashflowSummaryApiAnalyticsMonthlyGet({
        from,
        to,
    }: {
        from: string,
        to: string,
    }): CancelablePromise<Array<MonthRow>> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/analytics/monthly',
            query: {
                'from': from,
                'to': to,
            },
            errors: {
                422: `Validation Error`,
            },
        });
    }
}

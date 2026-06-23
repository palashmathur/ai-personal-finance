/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { DashboardResponse } from '../models/DashboardResponse';
import type { CancelablePromise } from '../core/CancelablePromise';
import { OpenAPI } from '../core/OpenAPI';
import { request as __request } from '../core/request';
export class DashboardService {
    /**
     * Get Dashboard
     * Return all four dashboard blocks for the given date range.
     *
     * Both `from` and `to` are required — the dashboard always shows a specific period.
     * `from` must be on or before `to`, otherwise a 422 is returned.
     * Typical values: first and last day of the current month, or a 3-month window.
     *
     * Blocks:
     * - cashflow: income, expenses, savings rate for the period.
     * - by_category: expense breakdown per category, ordered by spend descending.
     * - allocation: current portfolio split by asset class (stock, mutual_fund, etc.).
     * - networth_series: month-end net worth snapshots across the period.
     * @returns DashboardResponse Successful Response
     * @throws ApiError
     */
    public static getDashboardApiDashboardGet({
        from,
        to,
    }: {
        from: string,
        to: string,
    }): CancelablePromise<DashboardResponse> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/dashboard',
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

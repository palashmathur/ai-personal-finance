/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { AllocationItem } from './AllocationItem';
import type { CashflowBlock } from './CashflowBlock';
import type { CategoryBreakdownItem } from './CategoryBreakdownItem';
import type { NetWorthPoint } from './NetWorthPoint';
/**
 * The full dashboard payload — all four blocks in one response.
 *
 * The frontend receives this single JSON object and fans it out to four chart components.
 * Keeping it as one call means one loading spinner, not four independent spinners.
 */
export type DashboardResponse = {
    cashflow: CashflowBlock;
    by_category: Array<CategoryBreakdownItem>;
    allocation: Array<AllocationItem>;
    networth_series: Array<NetWorthPoint>;
};


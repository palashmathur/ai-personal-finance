/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
/**
 * Whether this category classifies income or expense transactions.
 * A child's kind must always match its parent's — you can't put a Salary
 * subcategory under a Food parent. Enforced in the service layer.
 */
export type CategoryKind = 'income' | 'expense';

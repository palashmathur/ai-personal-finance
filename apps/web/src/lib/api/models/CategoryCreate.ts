/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { CategoryKind } from './CategoryKind';
/**
 * Request body for POST /api/categories.
 * Leave parent_id as null to create a top-level (parent) category.
 * Set parent_id to an existing parent's id to create a subcategory (child).
 */
export type CategoryCreate = {
    name: string;
    kind: CategoryKind;
    parent_id?: (number | null);
    color?: (string | null);
    icon?: (string | null);
};


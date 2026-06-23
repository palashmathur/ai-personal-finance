/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { CategoryChildResponse } from './CategoryChildResponse';
import type { CategoryKind } from './CategoryKind';
/**
 * Response shape for any category, with children embedded.
 * Used by GET /api/categories (parents have children populated, children have []).
 * Also used by POST and PATCH — parent_id will be None for roots, int for children.
 */
export type CategoryResponse = {
    id: number;
    name: string;
    kind: CategoryKind;
    parent_id: (number | null);
    color: (string | null);
    icon: (string | null);
    archived: boolean;
    children?: Array<CategoryChildResponse>;
};


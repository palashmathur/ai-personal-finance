/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { CategoryKind } from './CategoryKind';
/**
 * Response shape for a child (leaf) category.
 * No `children` field here because children cannot have children — max depth is 2.
 */
export type CategoryChildResponse = {
    id: number;
    name: string;
    kind: CategoryKind;
    parent_id: number;
    color: (string | null);
    icon: (string | null);
    archived: boolean;
};


/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { CategoryKind } from './CategoryKind';
/**
 * Request body for PATCH /api/categories/{id}.
 * All fields are optional — only the ones you include are changed.
 *
 * Setting archived=True soft-deletes the category (and cascades to its children).
 * Setting archived=False restores it (children stay archived — restore them individually).
 */
export type CategoryUpdate = {
    name?: (string | null);
    kind?: (CategoryKind | null);
    parent_id?: (number | null);
    color?: (string | null);
    icon?: (string | null);
    archived?: (boolean | null);
};


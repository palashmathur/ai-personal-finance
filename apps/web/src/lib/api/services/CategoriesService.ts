/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { CategoryCreate } from '../models/CategoryCreate';
import type { CategoryDeleteResponse } from '../models/CategoryDeleteResponse';
import type { CategoryResponse } from '../models/CategoryResponse';
import type { CategoryUpdate } from '../models/CategoryUpdate';
import type { CancelablePromise } from '../core/CancelablePromise';
import { OpenAPI } from '../core/OpenAPI';
import { request as __request } from '../core/request';
export class CategoriesService {
    /**
     * List Categories
     * List all parent categories, each with their children embedded.
     *
     * Optional filters:
     * - ?kind=income   — only income categories (useful for the income transaction form)
     * - ?kind=expense  — only expense categories (useful for the expense transaction form)
     * - ?archived=true — include soft-deleted categories
     * @returns CategoryResponse Successful Response
     * @throws ApiError
     */
    public static listCategoriesApiCategoriesGet({
        kind,
        archived = false,
    }: {
        kind?: (string | null),
        archived?: boolean,
    }): CancelablePromise<Array<CategoryResponse>> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/categories',
            query: {
                'kind': kind,
                'archived': archived,
            },
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Create Category
     * Create a new category.
     *
     * - Leave parent_id null to create a top-level (parent) category.
     * - Set parent_id to create a subcategory. The child's kind must match the parent's.
     * - Returns 422 if kind mismatches or parent is itself a child.
     * - Returns 409 if a category with the same name + kind + parent already exists.
     *
     * Note: the response is always CategoryResponse (with a children field), but a
     * newly created child will be returned wrapped in its parent context only via GET.
     * For POST we return the created row directly — the children array will be empty.
     * @returns CategoryResponse Successful Response
     * @throws ApiError
     */
    public static createCategoryApiCategoriesPost({
        requestBody,
    }: {
        requestBody: CategoryCreate,
    }): CancelablePromise<CategoryResponse> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/api/categories',
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Update Category
     * Partially update a category.
     *
     * - Setting archived=true soft-deletes it and cascades to all its children.
     * - Setting archived=false restores only this category (children stay archived).
     * - Changing parent_id is validated for cycles, depth, and kind mismatch.
     * @returns CategoryResponse Successful Response
     * @throws ApiError
     */
    public static updateCategoryApiCategoriesCategoryIdPatch({
        categoryId,
        requestBody,
    }: {
        categoryId: number,
        requestBody: CategoryUpdate,
    }): CancelablePromise<CategoryResponse> {
        return __request(OpenAPI, {
            method: 'PATCH',
            url: '/api/categories/{category_id}',
            path: {
                'category_id': categoryId,
            },
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Delete Category
     * Hard-delete a category.
     *
     * - Returns 409 if the category has children. Delete or archive them first.
     * - On success, returns the count of transactions that are now "Uncategorized"
     * (their category_id was set to NULL automatically by the DB).
     * - The transactions themselves are untouched — only their category reference is cleared.
     * @returns CategoryDeleteResponse Successful Response
     * @throws ApiError
     */
    public static deleteCategoryApiCategoriesCategoryIdDelete({
        categoryId,
    }: {
        categoryId: number,
    }): CancelablePromise<CategoryDeleteResponse> {
        return __request(OpenAPI, {
            method: 'DELETE',
            url: '/api/categories/{category_id}',
            path: {
                'category_id': categoryId,
            },
            errors: {
                422: `Validation Error`,
            },
        });
    }
}

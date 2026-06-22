/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { Body_preview_import_api_imports_transactions_preview_post } from '../models/Body_preview_import_api_imports_transactions_preview_post';
import type { ConfirmRequest } from '../models/ConfirmRequest';
import type { ImportPreviewResponse } from '../models/ImportPreviewResponse';
import type { ImportResult } from '../models/ImportResult';
import type { CancelablePromise } from '../core/CancelablePromise';
import { OpenAPI } from '../core/OpenAPI';
import { request as __request } from '../core/request';
export class ImportsService {
    /**
     * Preview Import
     * Parse a CSV file and return the rows that would be inserted — without writing anything.
     *
     * The CSV must follow the canonical format:
     * date (YYYY-MM-DD), amount (positive decimal), type (debit|credit),
     * narration (text), category (optional name hint)
     *
     * Returns 422 if the file is malformed, missing required columns, or has invalid values.
     * Use this response to review and assign account_id / category_id before calling confirm.
     * @returns ImportPreviewResponse Successful Response
     * @throws ApiError
     */
    public static previewImportApiImportsTransactionsPreviewPost({
        formData,
    }: {
        formData: Body_preview_import_api_imports_transactions_preview_post,
    }): CancelablePromise<ImportPreviewResponse> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/api/imports/transactions/preview',
            formData: formData,
            mediaType: 'multipart/form-data',
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Confirm Import
     * Bulk-insert the confirmed rows into the transactions table.
     *
     * account_id is a single top-level field — the user picks the account once
     * and it is applied to all rows. Send back the rows from the preview response
     * with category_id filled in per row (optional — can be null).
     *
     * Rows that already exist in the DB (matched on amount_minor + occurred_on + note)
     * are silently skipped. Returns the count of inserted and skipped rows.
     * @returns ImportResult Successful Response
     * @throws ApiError
     */
    public static confirmImportApiImportsTransactionsConfirmPost({
        requestBody,
    }: {
        requestBody: ConfirmRequest,
    }): CancelablePromise<ImportResult> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/api/imports/transactions/confirm',
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
}

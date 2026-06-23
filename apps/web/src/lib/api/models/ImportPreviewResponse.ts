/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { PreviewRow } from './PreviewRow';
/**
 * Full response from the preview endpoint.
 * Wraps the list of parsed rows alongside a summary so the UI can show
 * "X rows parsed, Y will be skipped (already exist)" before the user confirms.
 */
export type ImportPreviewResponse = {
    rows: Array<PreviewRow>;
    total: number;
};


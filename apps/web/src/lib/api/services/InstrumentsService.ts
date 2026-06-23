/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { InstrumentCreate } from '../models/InstrumentCreate';
import type { InstrumentResponse } from '../models/InstrumentResponse';
import type { InstrumentUpdate } from '../models/InstrumentUpdate';
import type { CancelablePromise } from '../core/CancelablePromise';
import { OpenAPI } from '../core/OpenAPI';
import { request as __request } from '../core/request';
export class InstrumentsService {
    /**
     * List Instruments
     * List instruments, with optional search filtering by symbol or name.
     *
     * - No `search` param → returns all instruments, ordered by name.
     * - `?search=hdfc` → returns up to 20 instruments whose symbol or name contains
     * "hdfc" (case-insensitive). Used by the typeahead on the Add Investment form.
     * @returns InstrumentResponse Successful Response
     * @throws ApiError
     */
    public static listInstrumentsApiInstrumentsGet({
        search,
    }: {
        search?: (string | null),
    }): CancelablePromise<Array<InstrumentResponse>> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/instruments',
            query: {
                'search': search,
            },
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Create Instrument
     * Add a new instrument to the catalog.
     *
     * Returns 409 if an instrument with the same (kind, symbol) already exists.
     * The same symbol can exist under different kinds — e.g. "NIFTYBEES" can be
     * both a stock and an ETF — so the uniqueness check is on the combination.
     * @returns InstrumentResponse Successful Response
     * @throws ApiError
     */
    public static createInstrumentApiInstrumentsPost({
        requestBody,
    }: {
        requestBody: InstrumentCreate,
    }): CancelablePromise<InstrumentResponse> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/api/instruments',
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Update Instrument
     * Partially update an instrument. Only fields included in the body are changed.
     *
     * Most commonly used to refresh `current_price_minor` manually before the V2
     * price-fetch cron is built. When a new price is provided, `price_updated_at`
     * is automatically stamped so the UI can track price freshness.
     * @returns InstrumentResponse Successful Response
     * @throws ApiError
     */
    public static updateInstrumentApiInstrumentsInstrumentIdPatch({
        instrumentId,
        requestBody,
    }: {
        instrumentId: number,
        requestBody: InstrumentUpdate,
    }): CancelablePromise<InstrumentResponse> {
        return __request(OpenAPI, {
            method: 'PATCH',
            url: '/api/instruments/{instrument_id}',
            path: {
                'instrument_id': instrumentId,
            },
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
}

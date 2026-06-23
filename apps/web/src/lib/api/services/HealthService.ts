/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { CancelablePromise } from '../core/CancelablePromise';
import { OpenAPI } from '../core/OpenAPI';
import { request as __request } from '../core/request';
export class HealthService {
    /**
     * Health
     * Ping the server and the database in one call.
     *
     * Runs a lightweight SELECT 1 against SQLite to confirm the DB file is reachable
     * and the connection is healthy. If the DB call throws for any reason, FastAPI
     * surfaces it as a 500 — which is correct behaviour (the server is up but broken).
     *
     * Returns {"status": "ok", "db": "connected"} on success.
     * @returns any Successful Response
     * @throws ApiError
     */
    public static healthHealthGet(): CancelablePromise<any> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/health',
        });
    }
}

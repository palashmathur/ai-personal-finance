/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
/**
 * Request body for PATCH /api/instruments/{id}.
 * All fields optional — only the fields you send are updated (PATCH semantics).
 *
 * `current_price_minor` is the most common update: when you manually refresh a price
 * before the V2 price-fetch cron is built, this is how you do it.
 */
export type InstrumentUpdate = {
    name?: (string | null);
    current_price_minor?: (number | null);
    meta?: (Record<string, any> | null);
};


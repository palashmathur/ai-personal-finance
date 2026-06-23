/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { InstrumentKind } from './InstrumentKind';
/**
 * Response shape returned by every instruments endpoint.
 * `from_attributes=True` lets Pydantic read directly from SQLAlchemy model instances
 * — the same as orm_mode in Pydantic v1.
 */
export type InstrumentResponse = {
    id: number;
    kind: InstrumentKind;
    symbol: string;
    name: string;
    current_price_minor: (number | null);
    price_updated_at: (string | null);
    meta: (Record<string, any> | null);
};


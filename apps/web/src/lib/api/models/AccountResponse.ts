/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { AccountType } from './AccountType';
/**
 * Response shape for every account endpoint. Maps 1:1 to the DB row.
 * orm_mode (from_attributes in Pydantic v2) lets Pydantic read directly
 * from SQLAlchemy model instances without needing to convert to a dict first.
 * Think of it like Jackson's @JsonProperty reading from a JPA entity.
 */
export type AccountResponse = {
    id: number;
    name: string;
    type: AccountType;
    opening_balance_minor: number;
    archived: boolean;
    created_at: string;
};


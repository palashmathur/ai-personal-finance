/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
/**
 * Direction of the trade. Drives how the row is interpreted in holdings math.
 * buy: you spent cash and received units. sell: you received cash and gave up units.
 * dividend: you received cash with no change in units (quantity=1, price_minor=total amount).
 */
export type TxnSide = 'buy' | 'sell' | 'dividend';

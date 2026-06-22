/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
/**
 * One parsed row returned by the preview endpoint.
 * Nothing is written to the DB at this stage — this is just the parsed result
 * so the user can review it, assign an account, and adjust categories before confirming.
 *
 * category_source tells you where the suggestion came from:
 * "csv"  — the CSV file already had a category name that matched a DB category.
 * "rule" — a saved regex rule matched the note instantly (no LLM needed).
 * "llm"  — the LLM made the suggestion.
 * None   — no suggestion could be made (category_id will also be None).
 */
export type PreviewRow = {
    occurred_on: string;
    amount_minor: number;
    kind: string;
    note: string;
    category_id: (number | null);
    category_name: (string | null);
    category_source: (string | null);
};


/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
/**
 * The categorization suggestion returned by the suggest endpoints.
 *
 * source="rule"  → matched a saved regex rule instantly; no AI call was made.
 * source="llm"   → no rule matched; the LLM was asked.
 *
 * category_id is null when no suitable category was found (the LLM returned null
 * rather than guess — better than a wrong category silently applied).
 */
export type CategorizeSuggestResponse = {
    category_id: (number | null);
    category_name: (string | null);
    confidence: number;
    suggested_rule: (string | null);
    source: string;
};


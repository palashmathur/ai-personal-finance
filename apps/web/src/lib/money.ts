/**
 * The ONE money util (cross-cutting rule). Money is stored everywhere as integer
 * paise (1 INR = 100 paise) — never floats. This module is the single boundary
 * where paise become rupees for display and rupee inputs become paise for the API.
 * Every page and form imports from here so the conversion lives in exactly one place.
 *
 * Java analogy: like a single MoneyFormatter/`BigDecimal`-at-the-edge utility — the
 * domain keeps integer minor units; formatting to "₹1,500.00" happens only at the UI.
 */

// Intl.NumberFormat is the browser's built-in i18n formatter. 'en-IN' gives the
// Indian digit grouping (1,50,000 not 150,000) and the ₹ symbol.
const inr = new Intl.NumberFormat("en-IN", {
  style: "currency",
  currency: "INR",
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

// Compact form for chart axes / tight spaces: ₹1.5L, ₹1.2Cr (Indian scale).
const inrCompact = new Intl.NumberFormat("en-IN", {
  style: "currency",
  currency: "INR",
  notation: "compact",
  maximumFractionDigits: 1,
});

/** paise -> "₹1,500.00". null/undefined renders as an em dash (e.g. missing price). */
export function formatMoney(paise: number | null | undefined): string {
  if (paise == null) return "—";
  return inr.format(paise / 100);
}

/** paise -> "₹1.5L". For axis labels and dense chart tooltips. */
export function formatMoneyCompact(paise: number | null | undefined): string {
  if (paise == null) return "—";
  return inrCompact.format(paise / 100);
}

/**
 * Rupees (what the user types in a form, e.g. 1500.5) -> integer paise (150050).
 * Math.round guards against float drift: 19.99 * 100 is 1998.9999999 in JS.
 */
export function rupeesToPaise(rupees: number): number {
  return Math.round(rupees * 100);
}

/** Integer paise -> rupees number, for pre-filling an edit form's amount field. */
export function paiseToRupees(paise: number): number {
  return paise / 100;
}

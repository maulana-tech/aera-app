/* Formatting the three charts share. Kept out of the chart files so the
 * demand, cover and arrival charts cannot drift into reading the same date two
 * different ways. */

/** A date-only stamp read as local midnight. `new Date("2026-08-07")` is UTC
 *  midnight, which renders as 6 August anywhere west of Greenwich — so an axis
 *  would label the day before the day the data is about. */
export const parseDay = (iso: string) => {
  const [y, m, d] = iso.slice(0, 10).split("-").map(Number);
  return new Date(y || 1970, (m || 1) - 1, d || 1);
};

/** 9 Aug — short enough to sit under a tick without touching its neighbour. */
export const shortDay = (d: Date) =>
  d.toLocaleDateString("en-GB", { day: "numeric", month: "short" });

/** A scale hands back more precision than any of these values can justify. */
export const num = (v: number) => String(+v.toFixed(2));

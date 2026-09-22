/**
 * The two calendar choices left to the priest (CAL-004). Each is one setting; nothing else in the
 * UI needs to change when one of them does.
 */

/**
 * When the calendar day turns over for the visitor.
 * - "midnight": the civil day (default).
 * - "sunset": the liturgical day, which begins at sunset. Without the visitor's location we use a
 *   fixed local hour as an approximation of sunset.
 */
export const DAY_BOUNDARY: "midnight" | "sunset" = "midnight";
export const SUNSET_APPROXIMATE_HOUR = 18;

/**
 * Which commemoration the Today banner shows first when a day has several ("and N more").
 * - "source": the order the synaxarium source lists them in (Katameros).
 * - "linked-first": saints we can link to our saints index first, then the source order.
 * Monthly commemorations and events always come after the day's saints.
 */
export const BANNER_SAINT_ORDER: "source" | "linked-first" = "source";

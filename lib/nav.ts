/** The cookie that remembers a collapsed sidebar; read on the server so the first paint is right.
 *  Kept out of the client component: a server file importing a value from a "use client" module
 *  gets a client reference, not the string. */
export const NAV_COOKIE = "aera_nav";

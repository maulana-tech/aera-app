/* Which business a request is for.
 *
 * One install runs the flagship business (AERA_API) and, when the hub is on (AERA_HUB, hub.py), every business
 * people created here, each its own agent service. A signed-in person's business is the `aera_ws` cookie (set at
 * sign-in, httpOnly); a public page names its business with `?b=<slug>`. No cookie and no `b`: the flagship.
 * A wrong or forged cookie only sends the request to a business whose token secret is different, where the
 * session is not valid. */

export const FLAGSHIP = process.env.AERA_API ?? "http://127.0.0.1:8787";
const HUB = process.env.AERA_HUB ?? "";
const HUB_SECRET = process.env.AERA_HUB_SECRET ?? "";
export const WS_COOKIE = "aera_ws";

export const hubOn = () => !!(HUB && HUB_SECRET);

const cache = new Map<string, { base: string; at: number }>();
const SLUG = /^[a-z0-9-]{3,40}$/;

export async function hub<T>(path: string, init: RequestInit = {}): Promise<{ status: number; data: T }> {
  const r = await fetch(`${HUB}${path}`, {
    ...init,
    cache: "no-store",
    headers: { "content-type": "application/json", "x-hub-secret": HUB_SECRET, ...(init.headers ?? {}) },
  });
  return { status: r.status, data: (await r.json()) as T };
}

/** The agent service of one business created here, or null when there is no such business. */
export async function tenantBase(slug: string): Promise<string | null> {
  if (!hubOn() || !SLUG.test(slug)) return null;
  const hit = cache.get(slug);
  if (hit && Date.now() - hit.at < 60_000) return hit.base;
  try {
    const { status, data } = await hub<{ port: number }>(`/tenants/${slug}`);
    if (status !== 200) return null;
    const base = `${new URL(HUB).protocol}//${new URL(HUB).hostname}:${data.port}`;
    cache.set(slug, { base, at: Date.now() });
    return base;
  } catch {
    return null;
  }
}

/** The service for the signed-in person's business (server side: reads the cookie). */
export async function sessionBase(): Promise<string> {
  const { cookies } = await import("next/headers");
  const slug = (await cookies()).get(WS_COOKIE)?.value;
  return (slug && (await tenantBase(slug))) || FLAGSHIP;
}

/** The service a public page reads: `?b=<slug>` when given, else the flagship. */
export async function publicBase(slug?: string | null): Promise<string> {
  return (slug && (await tenantBase(slug))) || FLAGSHIP;
}

export const cookieOptions = {
  httpOnly: true,
  sameSite: "lax" as const,
  secure: process.env.NODE_ENV === "production",
  path: "/",
  maxAge: 12 * 60 * 60,
};

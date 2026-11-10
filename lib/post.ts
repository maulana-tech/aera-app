/* Browser-side calls to the agent service, through the server proxy at
 * /api/aera, which attaches the session token from the httpOnly cookie. The
 * page never holds the token. Errors come back as the service's own words. */

async function read<T>(r: Response): Promise<T> {
  const text = await r.text();
  let body: unknown = null;
  try {
    body = text ? JSON.parse(text) : null;
  } catch {
    // An upstream proxy may answer with HTML; the status says enough.
  }
  if (!r.ok) {
    const msg = (body as { error?: string } | null)?.error;
    throw new Error(msg || `HTTP ${r.status}`);
  }
  return body as T;
}

export async function post<T = unknown>(path: string, body?: unknown): Promise<T> {
  const r = await fetch(`/api/aera/${path}`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  return read<T>(r);
}

export async function get<T = unknown>(path: string): Promise<T> {
  const r = await fetch(`/api/aera/${path}`, { cache: "no-store" });
  return read<T>(r);
}

export const errorText = (e: unknown) => (e instanceof Error ? e.message : String(e));

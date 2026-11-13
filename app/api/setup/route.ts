import { cookies } from "next/headers";

const UPSTREAM = process.env.AERA_API ?? "http://127.0.0.1:8787";

/* First run only: the agent service creates the first account, as owner, while
 * no account exists, and refuses once one does. The session is set the same
 * way /api/login sets it. */
export async function GET() {
  try {
    const r = await fetch(`${UPSTREAM}/setup`, { cache: "no-store" });
    return Response.json(await r.json(), { status: r.status });
  } catch {
    return Response.json({ error: "the agent service is not responding" }, { status: 503 });
  }
}

export async function POST(req: Request) {
  let r: Response;
  try {
    r = await fetch(`${UPSTREAM}/setup`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: await req.text(),
      cache: "no-store",
    });
  } catch {
    return Response.json({ error: "the agent service is not responding" }, { status: 503 });
  }
  const data = await r.json();
  if (!r.ok) return Response.json(data, { status: r.status });
  (await cookies()).delete("aera_ws");            // the flagship: no business cookie
  (await cookies()).set("aera_session", data.token, {
    httpOnly: true,
    sameSite: "lax",
    secure: process.env.NODE_ENV === "production",
    path: "/",
    maxAge: 12 * 60 * 60,
  });
  return Response.json({ user: data.user });
}

import { cookies } from "next/headers";

const UPSTREAM = process.env.AERA_API ?? "http://127.0.0.1:8787";

/** Whether this install takes sign-ups, and what a new account may do. */
export async function GET() {
  try {
    const r = await fetch(`${UPSTREAM}/signup`, { cache: "no-store" });
    return Response.json(await r.json(), { status: r.status });
  } catch {
    return Response.json({ enabled: false }, { status: 200 });
  }
}

/** Create a tester account and sign it in, the same way /api/login does. */
export async function POST(req: Request) {
  const body = await req.text();
  let r: Response;
  try {
    r = await fetch(`${UPSTREAM}/signup`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body,
      cache: "no-store",
    });
  } catch {
    return Response.json({ error: "the agent service is not responding" }, { status: 503 });
  }
  const data = await r.json();
  if (!r.ok) return Response.json(data, { status: r.status });
  (await cookies()).set("aera_session", data.token, {
    httpOnly: true,
    sameSite: "lax",
    secure: process.env.NODE_ENV === "production",
    path: "/",
    maxAge: 12 * 60 * 60,
  });
  return Response.json({ user: data.user }, { status: 201 });
}

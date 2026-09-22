import { cookies } from "next/headers";

const UPSTREAM = process.env.SIGAP_API ?? "http://127.0.0.1:8787";

export async function POST(req: Request) {
  const body = await req.text();
  let r: Response;
  try {
    r = await fetch(`${UPSTREAM}/login`, {
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

  // httpOnly so no script on the page can read the token.
  (await cookies()).set("sigap_session", data.token, {
    httpOnly: true,
    sameSite: "lax",
    secure: process.env.NODE_ENV === "production",
    path: "/",
    maxAge: 12 * 60 * 60,
  });
  return Response.json({ user: data.user });
}

export async function DELETE() {
  (await cookies()).delete("sigap_session");
  return Response.json({ signedOut: true });
}

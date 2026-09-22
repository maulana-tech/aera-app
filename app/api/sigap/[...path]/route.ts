import { cookies } from "next/headers";

// Bridge to the agent service. The browser never calls it directly, and the
// session token is attached here — never sent from the page side.
const UPSTREAM = process.env.SIGAP_API ?? "http://127.0.0.1:8787";

async function forward(req: Request, path: string[], method: "GET" | "POST") {
  const token = (await cookies()).get("sigap_session")?.value;
  const headers: Record<string, string> = { "content-type": "application/json" };
  if (token) headers.Authorization = `Bearer ${token}`;

  try {
    const r = await fetch(`${UPSTREAM}/${path.join("/")}`, {
      method,
      headers,
      body: method === "POST" ? await req.text() : undefined,
      cache: "no-store",
    });
    return new Response(await r.text(), {
      status: r.status,
      headers: { "content-type": "application/json" },
    });
  } catch {
    return Response.json(
      { error: `the agent service is not responding at ${UPSTREAM}. Run: cd sigap/agent && python3 api.py` },
      { status: 503 },
    );
  }
}

export async function GET(req: Request, { params }: { params: Promise<{ path: string[] }> }) {
  return forward(req, (await params).path, "GET");
}
export async function POST(req: Request, { params }: { params: Promise<{ path: string[] }> }) {
  return forward(req, (await params).path, "POST");
}

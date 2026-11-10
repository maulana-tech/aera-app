import { cookies } from "next/headers";

// Bridge to the agent service. The browser never calls it directly, and the
// session token is attached here, never from the page side.
const UPSTREAM = process.env.AERA_API ?? "http://127.0.0.1:8787";

async function forward(req: Request, path: string[], method: "GET" | "POST") {
  const token = (await cookies()).get("aera_session")?.value;
  const headers: Record<string, string> = { "content-type": "application/json" };
  const accept = req.headers.get("accept");
  if (accept) headers.accept = accept;
  // /public/* is the customer-facing surface (offerings, checkout, order
  // status, ledger): it needs no session, and a visitor's request never
  // carries an operator's token even when one happens to be signed in.
  if (token && path[0] !== "public") headers.Authorization = `Bearer ${token}`;
  // The query string is part of the request, not decoration: filters such as
  // ?status=pending and ?days=30 ride there.
  const { search } = new URL(req.url);

  try {
    const r = await fetch(`${UPSTREAM}/${path.join("/")}${search}`, {
      method,
      headers,
      body: method === "POST" ? await req.text() : undefined,
      cache: "no-store",
    });

    const contentType = r.headers.get("content-type") || "application/json";
    if (contentType.includes("text/event-stream") && r.body) {
      return new Response(r.body, {
        status: r.status,
        headers: {
          "content-type": "text/event-stream; charset=utf-8",
          "cache-control": "no-cache, no-transform",
          "x-accel-buffering": "no",
          connection: "keep-alive",
        },
      });
    }

    // Bytes, not text: a deliverable may come back as a PDF or a workbook, and
    // decoding one as UTF-8 would corrupt it. The name rides on Content-Disposition.
    const disposition = r.headers.get("content-disposition");
    return new Response(await r.arrayBuffer(), {
      status: r.status,
      headers: {
        "content-type": contentType,
        ...(disposition ? { "content-disposition": disposition, "cache-control": "no-store" } : {}),
      },
    });
  } catch {
    return Response.json(
      { error: `the agent service is not responding at ${UPSTREAM}. Run: cd aera/agent && python3 api.py` },
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

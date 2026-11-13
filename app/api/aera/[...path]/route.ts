import { cookies } from "next/headers";

import { publicBase, sessionBase } from "@/lib/tenant";
import { upstream } from "@/lib/upstream";

// Bridge to the agent service. The browser never calls it directly, and the
// session token is attached here, never from the page side. Which service:
// the signed-in person's business, or for /public/* the business named by
// ?b=<slug> (lib/tenant.ts); the flagship when neither says otherwise.

async function forward(req: Request, path: string[], method: "GET" | "POST") {
  const token = (await cookies()).get("aera_session")?.value;
  const headers: Record<string, string> = { "content-type": "application/json" };
  const accept = req.headers.get("accept");
  if (accept) headers.accept = accept;
  // Mail forwarded by an e-mail host carries the shared secret the agent checks.
  const inbound = req.headers.get("x-aera-inbound-secret");
  if (inbound && path.join("/") === "public/inbound/email") headers["x-aera-inbound-secret"] = inbound;
  // /public/* is the customer-facing surface (offerings, checkout, order
  // status, ledger): it needs no session, and a visitor's request never
  // carries an operator's token even when one happens to be signed in.
  if (token && path[0] !== "public") headers.Authorization = `Bearer ${token}`;
  // The query string is part of the request, not decoration: filters such as
  // ?status=pending and ?days=30 ride there.
  const u = new URL(req.url);
  const pub = path[0] === "public";
  // a public page opened with ?b=<slug> makes its own calls without it: the page's address says which business
  let b = u.searchParams.get("b");
  if (pub && !b) {
    try { b = new URL(req.headers.get("referer") ?? "").searchParams.get("b"); } catch { b = null; }
  }
  if (pub && b) u.searchParams.delete("b");
  const search = u.searchParams.toString() ? `?${u.searchParams.toString()}` : "";
  const UPSTREAM = pub ? await publicBase(b) : await sessionBase();

  try {
    const url = `${UPSTREAM}/${path.join("/")}${search}`;
    const init: RequestInit = {
      method,
      headers,
      body: method === "POST" ? await req.text() : undefined,
      cache: "no-store",
    };
    // In turn with the pages' own reads, and a GET retried once (lib/upstream.ts).
    const r = await upstream(url, init);

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
      { error: "the agent service is not responding. Run: cd aera/agent && python3 api.py" },
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

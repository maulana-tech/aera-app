// Jembatan ke layanan agent Python. Browser tidak pernah memanggilnya langsung —
// supaya layanan agent bisa tetap tertutup di jaringan internal.
const HULU = process.env.SIGAP_API ?? "http://127.0.0.1:8787";

async function teruskan(req: Request, jalur: string[], metode: "GET" | "POST") {
  const url = `${HULU}/${jalur.join("/")}`;
  try {
    const r = await fetch(url, {
      method: metode,
      headers: { "content-type": "application/json" },
      body: metode === "POST" ? await req.text() : undefined,
      cache: "no-store",
    });
    return new Response(await r.text(), {
      status: r.status,
      headers: { "content-type": "application/json" },
    });
  } catch {
    return Response.json(
      { galat: `layanan agent tidak merespons di ${HULU}. Jalankan: cd sigap/agent && python3 api.py` },
      { status: 503 },
    );
  }
}

export async function GET(req: Request, { params }: { params: Promise<{ jalur: string[] }> }) {
  return teruskan(req, (await params).jalur, "GET");
}

export async function POST(req: Request, { params }: { params: Promise<{ jalur: string[] }> }) {
  return teruskan(req, (await params).jalur, "POST");
}

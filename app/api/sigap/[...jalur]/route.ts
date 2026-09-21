import { cookies } from "next/headers";

// Jembatan ke layanan agent. Browser tidak pernah memanggilnya langsung, dan
// token sesi ditempelkan di sini — tidak pernah dikirim dari sisi halaman.
const HULU = process.env.SIGAP_API ?? "http://127.0.0.1:8787";

async function teruskan(req: Request, jalur: string[], metode: "GET" | "POST") {
  const token = (await cookies()).get("sigap_sesi")?.value;
  const kepala: Record<string, string> = { "content-type": "application/json" };
  if (token) kepala.Authorization = `Bearer ${token}`;

  try {
    const r = await fetch(`${HULU}/${jalur.join("/")}`, {
      method: metode,
      headers: kepala,
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

import { cookies } from "next/headers";

const HULU = process.env.SIGAP_API ?? "http://127.0.0.1:8787";

export async function POST(req: Request) {
  const badan = await req.text();
  let r: Response;
  try {
    r = await fetch(`${HULU}/masuk`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: badan,
      cache: "no-store",
    });
  } catch {
    return Response.json({ galat: "layanan agent tidak merespons" }, { status: 503 });
  }

  const data = await r.json();
  if (!r.ok) return Response.json(data, { status: r.status });

  // Token disimpan httpOnly supaya tidak bisa dibaca skrip di halaman.
  (await cookies()).set("sigap_sesi", data.token, {
    httpOnly: true,
    sameSite: "lax",
    secure: process.env.NODE_ENV === "production",
    path: "/",
    maxAge: 12 * 60 * 60,
  });
  return Response.json({ pengguna: data.pengguna });
}

export async function DELETE() {
  (await cookies()).delete("sigap_sesi");
  return Response.json({ keluar: true });
}

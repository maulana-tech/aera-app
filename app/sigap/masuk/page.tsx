"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { Button } from "../ui/Twenty";

export default function Masuk() {
  const r = useRouter();
  const [email, setEmail] = useState("");
  const [sandi, setSandi] = useState("");
  const [galat, setGalat] = useState("");
  const [sibuk, setSibuk] = useState(false);

  async function kirim(e: React.FormEvent) {
    e.preventDefault();
    setSibuk(true);
    setGalat("");
    try {
      const res = await fetch("/api/masuk", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ email, sandi }),
      });
      if (!res.ok) throw new Error((await res.json()).galat ?? "gagal masuk");
      r.push("/sigap");
      r.refresh();
    } catch (err) {
      setGalat(err instanceof Error ? err.message : "gagal masuk");
    } finally {
      setSibuk(false);
    }
  }

  return (
    <main className="mx-auto flex min-h-[70vh] max-w-sm flex-col justify-center px-6">
      <p className="font-mono text-xs uppercase tracking-[0.18em] text-accent">SIGAP</p>
      <h1 className="mt-2 text-2xl font-semibold tracking-tight">Masuk</h1>
      <p className="mt-1 text-sm text-muted">
        Persetujuan tercatat atas nama akun ini.
      </p>

      <form onSubmit={kirim} className="mt-8 space-y-4">
        <label className="block">
          <span className="font-mono text-[11px] uppercase tracking-wider text-muted">Email</span>
          <input
            type="email" required value={email} onChange={(e) => setEmail(e.target.value)}
            className="mt-1.5 w-full rounded-lg border border-line bg-card px-3 py-2 text-sm outline-none focus:border-accent"
          />
        </label>
        <label className="block">
          <span className="font-mono text-[11px] uppercase tracking-wider text-muted">Kata sandi</span>
          <input
            type="password" required value={sandi} onChange={(e) => setSandi(e.target.value)}
            className="mt-1.5 w-full rounded-lg border border-line bg-card px-3 py-2 text-sm outline-none focus:border-accent"
          />
        </label>

        {galat && <p className="font-mono text-xs text-rose-300">{galat}</p>}

        <Button type="submit" variant="solid" color="accent" loading={sibuk} fullWidth>
          {sibuk ? "Memeriksa…" : "Masuk"}
        </Button>
      </form>

      <p className="mt-8 font-mono text-[11px] leading-relaxed text-muted">
        Belum punya akun? Dibuat lewat perkakas admin:
        <br />
        python3 kelola.py pengguna email nama peran sandi
      </p>
    </main>
  );
}

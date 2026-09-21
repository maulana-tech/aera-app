"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { Button } from "./Twenty";

export default function Sesi({ nama, peran }: { nama?: string; peran?: string }) {
  const r = useRouter();
  const [sibuk, setSibuk] = useState(false);

  if (!nama) {
    return (
      <Link
        href="/masuk"
        className="rounded-full border border-accent/60 px-3 py-1 font-mono text-[11px] text-accent"
      >
        masuk
      </Link>
    );
  }

  async function keluar() {
    setSibuk(true);
    await fetch("/api/masuk", { method: "DELETE" });
    r.push("/");
    r.refresh();
  }

  return (
    <span className="flex items-center gap-2">
      <span className="rounded-full border border-line px-3 py-1 font-mono text-[11px] text-muted">
        {nama} · {peran}
      </span>
      <Button variant="ghost" color="neutral" size="sm" loading={sibuk} onClick={keluar}>
        Keluar
      </Button>
    </span>
  );
}

"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

/** Segarkan halaman selama masih ada penanganan yang berjalan.
 *  Produk ini soal agent yang bekerja sendiri — pengguna tidak
 *  seharusnya menekan refresh untuk tahu sudah sampai mana. */
export function SegarkanOtomatis({ aktif, jeda = 4000 }: { aktif: boolean; jeda?: number }) {
  const r = useRouter();
  const [hidup, setHidup] = useState(true);

  useEffect(() => {
    if (!aktif || !hidup) return;
    const t = setInterval(() => r.refresh(), jeda);
    return () => clearInterval(t);
  }, [aktif, hidup, jeda, r]);

  useEffect(() => {
    const ubah = () => setHidup(document.visibilityState === "visible");
    document.addEventListener("visibilitychange", ubah);
    return () => document.removeEventListener("visibilitychange", ubah);
  }, []);

  if (!aktif) return null;
  return (
    <span className="text-muted-foreground flex items-center gap-1.5 font-mono text-[11px]">
      <span className="relative flex size-1.5">
        <span className="bg-sky-500 absolute inline-flex size-full animate-ping rounded-full opacity-75" />
        <span className="bg-sky-500 relative inline-flex size-1.5 rounded-full" />
      </span>
      memantau
    </span>
  );
}

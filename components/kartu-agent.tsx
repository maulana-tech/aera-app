import { Crown, ShieldBan } from "lucide-react";
import Link from "next/link";

import type { Agent } from "@/app/lib";
import { Badge } from "@/components/ui/badge";

/** Warna lencana per agent, dari huruf awal namanya. Konsisten antar halaman. */
const RONA = [
  "bg-sky-500/15 text-sky-700 dark:text-sky-400",
  "bg-emerald-500/15 text-emerald-700 dark:text-emerald-400",
  "bg-violet-500/15 text-violet-700 dark:text-violet-400",
  "bg-amber-500/15 text-amber-700 dark:text-amber-400",
  "bg-rose-500/15 text-rose-700 dark:text-rose-400",
  "bg-teal-500/15 text-teal-700 dark:text-teal-400",
];
export const rona = (s: string) => RONA[s.charCodeAt(0) % RONA.length];

export function Lencana({ panggilan, besar }: { panggilan: string; besar?: boolean }) {
  return (
    <span
      className={`flex shrink-0 items-center justify-center rounded-full font-semibold ${rona(
        panggilan,
      )} ${besar ? "size-10 text-sm" : "size-8 text-xs"}`}
    >
      {panggilan.slice(0, 2)}
    </span>
  );
}

export function KartuAgent({ a }: { a: Agent }) {
  const lengkap = a.terpasang === a.total_alat;
  return (
    <Link
      href={`/agent/${a.kode}`}
      className="hover:border-foreground/30 hover:bg-muted/30 group block rounded-xl border p-4 transition-colors"
    >
      <div className="flex items-start gap-3">
        <Lencana panggilan={a.panggilan} />
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
            <h3 className="font-medium leading-none">{a.panggilan}</h3>
            <span className="text-muted-foreground text-xs">{a.nama}</span>
            {a.ketua && <Crown className="size-3.5 shrink-0" />}
            {a.veto && (
              <Badge variant="outline" className="h-5 gap-1 px-1.5 font-mono text-[9px]">
                <ShieldBan className="size-2.5" />
                veto
              </Badge>
            )}
          </div>
          <p className="text-muted-foreground mt-1.5 line-clamp-2 text-xs leading-relaxed">
            {a.peran}
          </p>
          <p
            className={`mt-2 font-mono text-[10px] ${
              lengkap ? "text-muted-foreground" : "text-amber-700 dark:text-amber-400"
            }`}
          >
            {a.terpasang}/{a.total_alat} alat
            {a.dipakai_di > 0 && ` · ${a.dipakai_di} gangguan`}
          </p>
        </div>
      </div>
    </Link>
  );
}

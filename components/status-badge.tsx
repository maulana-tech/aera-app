import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

const WARNA: Record<string, string> = {
  selesai:   "border-emerald-500/40 bg-emerald-500/10 text-emerald-700 dark:text-emerald-400",
  terkirim:  "border-emerald-500/40 bg-emerald-500/10 text-emerald-700 dark:text-emerald-400",
  disetujui: "border-emerald-500/40 bg-emerald-500/10 text-emerald-700 dark:text-emerald-400",
  berjalan:  "border-sky-500/40 bg-sky-500/10 text-sky-700 dark:text-sky-400",
  ditahan:   "border-amber-500/40 bg-amber-500/10 text-amber-700 dark:text-amber-400",
  menunggu:  "border-amber-500/40 bg-amber-500/10 text-amber-700 dark:text-amber-400",
  runut:     "border-border bg-muted text-muted-foreground",
  gagal:     "border-rose-500/40 bg-rose-500/10 text-rose-700 dark:text-rose-400",
  ditolak:   "border-rose-500/40 bg-rose-500/10 text-rose-700 dark:text-rose-400",
};

/** Penanda status. Warnanya menyampaikan arti, jadi teksnya tetap ditulis. */
export function StatusBadge({ status, className, children }: {
  status: string; className?: string; children?: React.ReactNode;
}) {
  return (
    <Badge variant="outline" className={cn("font-mono text-[10px]", WARNA[status], className)}>
      {children ?? status}
    </Badge>
  );
}

const ASAL: Record<string, { label: string; cls: string }> = {
  live:     { label: "langsung",  cls: "border-emerald-500/40 bg-emerald-500/10 text-emerald-700 dark:text-emerald-400" },
  cached:   { label: "simpanan",  cls: "border-sky-500/40 bg-sky-500/10 text-sky-700 dark:text-sky-400" },
  derived:  { label: "hitungan",  cls: "border-violet-500/40 bg-violet-500/10 text-violet-700 dark:text-violet-400" },
  modelled: { label: "contoh",    cls: "border-amber-500/40 bg-amber-500/10 text-amber-700 dark:text-amber-400" },
  missing:  { label: "tidak ada", cls: "border-rose-500/40 bg-rose-500/10 text-rose-700 dark:text-rose-400" },
};

/** Label asal data. Inilah yang membedakan angka yang boleh dipercaya dan tidak. */
export function AsalBadge({ asal, sumber }: { asal: string; sumber?: string | null }) {
  const a = ASAL[asal];
  if (!a) return null;
  return (
    <Badge variant="outline" className={cn("font-mono text-[10px] font-normal", a.cls)}>
      {a.label}
      {sumber ? ` · ${sumber}` : ""}
    </Badge>
  );
}

"use client";

import { usePathname } from "next/navigation";

const JUDUL: [RegExp, string][] = [
  [/^\/$/, "Antrean keputusan"],
  [/^\/dasbor$/, "Dasbor"],
  [/^\/chat$/, "Percakapan"],
  [/^\/data\/(\w+)/, "Data"],
  [/^\/agent$/, "Tim agent"],
  [/^\/agent\/.+/, "Percakapan agent"],
  [/^\/log$/, "Log"],
  [/^\/laporan/, "Laporan"],
  [/^\/unggah$/, "Unggah data"],
  [/^\/kontak$/, "Kontak"],
  [/^\/gangguan\/.+/, "Detail penanganan"],
];

export function JudulHalaman() {
  const jalur = usePathname();
  const judul = JUDUL.find(([r]) => r.test(jalur))?.[1] ?? "";
  return (
    <span className="text-muted-foreground font-mono text-xs uppercase tracking-[0.15em]">
      {judul}
    </span>
  );
}

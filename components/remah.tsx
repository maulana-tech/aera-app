"use client";

import { usePathname } from "next/navigation";

import {
  Breadcrumb, BreadcrumbItem, BreadcrumbLink, BreadcrumbList,
  BreadcrumbPage, BreadcrumbSeparator,
} from "@/components/ui/breadcrumb";

const NAMA: Record<string, string> = {
  dasbor: "Dasbor",
  chat: "Percakapan",
  data: "Data pasokan",
  permintaan: "Permintaan",
  stok: "Stok",
  sumber: "Sumber pasokan",
  logistik: "Logistik",
  perhitungan: "Perhitungan",
  eksekusi: "Eksekusi",
  agent: "Tim agent",
  log: "Log",
  laporan: "Laporan",
  unggah: "Unggah data",
  kontak: "Kontak",
  gangguan: "Penanganan",
};

/** Ruas yang bukan halaman sendiri — ditampilkan tapi tidak bisa diklik. */
const BUKAN_HALAMAN = new Set(["data", "gangguan"]);

export function Remah() {
  const jalur = usePathname();
  const ruas = jalur.split("/").filter(Boolean);

  return (
    <Breadcrumb>
      <BreadcrumbList>
        <BreadcrumbItem>
          {ruas.length === 0 ? (
            <BreadcrumbPage>Antrean keputusan</BreadcrumbPage>
          ) : (
            <BreadcrumbLink href="/">Antrean</BreadcrumbLink>
          )}
        </BreadcrumbItem>

        {ruas.map((r, i) => {
          const akhir = i === ruas.length - 1;
          const href = "/" + ruas.slice(0, i + 1).join("/");
          const label = NAMA[r] ?? (r.length > 14 ? r.slice(0, 10) + "…" : r);
          return (
            <span key={href} className="contents">
              <BreadcrumbSeparator />
              <BreadcrumbItem>
                {akhir || BUKAN_HALAMAN.has(r) ? (
                  <BreadcrumbPage className={akhir ? "" : "text-muted-foreground"}>
                    {label}
                  </BreadcrumbPage>
                ) : (
                  <BreadcrumbLink href={href}>{label}</BreadcrumbLink>
                )}
              </BreadcrumbItem>
            </span>
          );
        })}
      </BreadcrumbList>
    </Breadcrumb>
  );
}
